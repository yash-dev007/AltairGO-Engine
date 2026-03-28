import ast
import json
import os
import time

import requests
import structlog

from backend.services.metrics_service import incr_daily_counter, mark_status

log = structlog.get_logger(__name__)

try:
    from backend.agents.token_optimizer import TokenOptimizer
    _token_optimizer = TokenOptimizer()
except ImportError:
    _token_optimizer = None

try:
    from backend.agents.mcp_context_agent import MCPContextAgent
    _context_agent = MCPContextAgent()
except ImportError:
    _context_agent = None

try:
    from backend.agents.itinerary_qa_agent import ItineraryQAAgent
    _qa_agent = ItineraryQAAgent()
except ImportError:
    _qa_agent = None


def _repair_ollama_json(text: str) -> str:
    """
    Fix common Ollama JSON malformation where an array of objects is returned as:
      ["key": val, ...]  →  [{"key": val, ...}]
    or a single object missing braces:
      "key": val, ...    →  {"key": val, ...}
    Returns the original string unchanged if pattern is not detected.
    """
    import re
    s = text.strip()

    # Pattern: starts with [ followed by "key": (not {)
    # e.g. ["day": 1, "activities": [...]]
    if s.startswith('[') and not s.startswith('[{') and not s.startswith('["') is False:
        # Check if it looks like object content immediately after [
        inner = s[1:].lstrip()
        if inner and inner[0] == '"':
            # Wrap each top-level object: split on }, { boundaries is complex —
            # simpler: replace leading [ with [{ and trailing ] with }]
            # only when the content doesn't start with another [
            candidate = '[{' + s[1:-1] + '}]'
            try:
                json.loads(candidate)
                return candidate
            except json.JSONDecodeError:
                pass

    # Pattern: bare object without braces at top level
    # e.g.  "trip_title": "foo", "smart_insights": [...]
    if s and s[0] == '"':
        candidate = '{' + s + '}'
        try:
            json.loads(candidate)
            return candidate
        except json.JSONDecodeError:
            pass

    return text


class GeminiService:
    BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models"
    DEFAULT_MODEL = "gemini-2.0-flash"
    FALLBACK_MODEL = "gemini-2.0-flash-lite"
    MAX_RETRIES = 3
    OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
    OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2:3b")

    def __init__(self, api_key=None):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY", "")
        self.prompts_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "prompts")

    def _load_template(self, filename: str) -> str:
        path = os.path.join(self.prompts_dir, filename)
        if not os.path.exists(path):
            log.warning(f"Prompt template {filename} not found at {path}")
            return ""
        try:
            with open(path, "r", encoding="utf-8") as f:
                return f.read().strip()
        except Exception as exc:
            log.error(f"Error reading prompt template {filename}: {exc}")
            return ""

    def build_prompt(self, user_prefs, destination_data=None):
        template = self._load_template("itinerary_base.txt")
        if not template:
            # Fallback to hardcoded if template read fails
            parts = [
                f"Plan a {user_prefs.get('duration', 3)}-day trip for a "
                f"{user_prefs.get('traveler_type', 'couple')} to "
                f"{user_prefs.get('start_city', 'India')}.",
                f"Budget: {user_prefs.get('budget', 10000)} INR.",
                f"Style: {user_prefs.get('style', 'standard')}.",
                "NEVER change activity names, destination names, accommodation names, or any locked numeric values.",
                "NEVER modify costs, durations, coordinates, dates, or counts.",
                "Return a valid JSON itinerary.",
            ]
            if destination_data:
                parts.append(f"Destination data: {json.dumps(destination_data[:3])}")
            return " ".join(parts)

        return template.format(
            duration=user_prefs.get("duration", 3),
            traveler_type=user_prefs.get("traveler_type", "couple"),
            start_city=user_prefs.get("start_city", "India"),
            budget=user_prefs.get("budget", 10000),
            style=user_prefs.get("style", "standard"),
            destination_data=f"Destination data: {json.dumps(destination_data[:3])}" if destination_data else ""
        )

    def generate_itinerary(self, user_prefs, destination_data=None):
        prompt = self.build_prompt(user_prefs, destination_data)
        return self._request_json(prompt, timeout=15)

    def polish_itinerary_text(self, itinerary_data: dict, user_prefs: dict) -> dict:
        if not self.api_key:
            log.warning("No Gemini API key, skipping polish.")
            return itinerary_data

        skeleton = self._build_skeleton(itinerary_data)
        context = None

        template = self._load_template("itinerary_polish.txt")
        if template:
            prompt = template.format(
                traveler_type=user_prefs.get("traveler_type", "couple"),
                city=user_prefs.get("city", "India"),
                days=user_prefs.get("days", 3),
                skeleton=json.dumps(skeleton)
            )
        else:
            prompt = f"""
You are a luxury travel writer polishing a deterministic itinerary for a
{user_prefs.get('traveler_type', 'couple')} visiting {user_prefs.get('city', 'India')}
for {user_prefs.get('days', 3)} days.

Skeleton: {json.dumps(skeleton)}

Rewrite ONLY these 4 text fields for each activity:
- description  (vivid, sensory, under 60 words, second person)
- why_this_fits  (1 sentence explaining why it suits this traveler type)
- local_secret  (1 insider tip — best time, hidden entrance, local trick)
- how_to_reach  (concise directions from previous stop or hotel)

STRICT RULES:
- NEVER change activity names, destination names, accommodation names, or theme names.
- NEVER change cost, time, latitude, longitude, day_total, total_cost, or any numeric value.
- NEVER add, remove, or reorder activities.
- Return ONLY a JSON array — one object per day — matching this exact structure:
[
  {{
    "day": 1,
    "activities": [
      {{
        "description": "...",
        "why_this_fits": "...",
        "local_secret": "...",
        "how_to_reach": "..."
      }}
    ]
  }}
]
- The array must have exactly {user_prefs.get('days', 3)} elements (one per day).
- Each day's activities array must match the number of activities in the skeleton.
""".strip()

        if _context_agent:
            travel_month = user_prefs.get("travel_month")
            city = user_prefs.get("city", user_prefs.get("start_city", "India"))
            context = _context_agent.fetch_live_context(city, travel_month)
            prompt = _context_agent.build_enriched_prompt(prompt, context)
            mark_status("agent", "mcp_context", "ok", {"city": city, "travel_month": travel_month})

        try:
            polished_content = self._request_json(prompt, timeout=15)
            self._merge_polish_updates(itinerary_data, polished_content)
        except Exception as exc:
            log.error(f"Gemini polish failed: {exc}")
            return itinerary_data

        try:
            template = self._load_template("itinerary_meta.txt")
            if template:
                meta_prompt = template.format(
                    traveler_type=user_prefs.get("traveler_type", "couple"),
                    city=user_prefs.get("city", "India"),
                    days=user_prefs.get("days", 3),
                    skeleton=json.dumps(skeleton)
                )
            else:
                meta_prompt = f"""
Given this itinerary for a {user_prefs.get('traveler_type', 'couple')}
visiting {user_prefs.get('city', 'India')} for {user_prefs.get('days', 3)} days:
{json.dumps(skeleton)}

Return ONLY a JSON object with exactly this structure:
{{
  "trip_title": "<vivid 5-8 word title capturing the trip's essence>",
  "smart_insights": [
    "<practical insight 1 — money-saving tip, local custom, or timing advice>",
    "<practical insight 2>",
    "<practical insight 3>"
  ],
  "packing_tips": [
    "<destination-specific packing tip 1>",
    "<packing tip 2>",
    "<packing tip 3>",
    "<packing tip 4>"
  ]
}}

STRICT RULES:
- smart_insights must be EXACTLY 3 strings.
- packing_tips must be EXACTLY 4 strings.
- NEVER change place names or any numeric values.
- Return ONLY the JSON object, no markdown.
""".strip()
            if _context_agent and context:
                meta_prompt = _context_agent.build_enriched_prompt(meta_prompt, context)
            meta_data = self._request_json(meta_prompt, timeout=15)
            if meta_data.get("trip_title"):
                itinerary_data["trip_title"] = meta_data["trip_title"]
            if meta_data.get("smart_insights"):
                itinerary_data["smart_insights"] = meta_data["smart_insights"]
            if meta_data.get("packing_tips"):
                itinerary_data["packing_tips"] = meta_data["packing_tips"]
        except Exception as exc:
            log.warning(f"Gemini meta generation skipped: {exc}")

        if _qa_agent:
            qa_report = _qa_agent.review_itinerary(itinerary_data)
            log.info(
                f"ItineraryQA: score={qa_report['score']}/100, "
                f"issues={qa_report['total_issues']}, warnings={qa_report['total_warnings']}"
            )
            mark_status("agent", "itinerary_qa", "ok", {
                "score": qa_report["score"],
                "issues": qa_report["total_issues"],
                "warnings": qa_report["total_warnings"],
            })
            if not qa_report["passed"]:
                itinerary_data = _qa_agent.auto_fix(itinerary_data, qa_report)
                log.info("ItineraryQA: Auto-fix applied to failing itinerary.")

        return itinerary_data

    def chat_with_data(self, prompt, context=None):
        if not self.api_key:
            return {"reply": ""}

        full_prompt = f"Context: {json.dumps(context or [])}. Question: {prompt}"
        try:
            result = self._request_raw(full_prompt, timeout=10, response_mime_type=None)
        except Exception as exc:
            log.warning(f"Gemini chat failed: {exc}")
            return {"reply": ""}

        return {"reply": self._extract_text(result)}

    def _request_json(self, prompt: str, timeout: int = 15):
        result = self._request_raw(prompt, timeout=timeout, response_mime_type="application/json")
        text = self._extract_text(result)
        if not text:
            return {}
        return self._parse_jsonish_text(text)

    def _request_raw(self, prompt: str, timeout: int = 15, response_mime_type: str | None = "application/json"):
        if not self.api_key:
            raise RuntimeError("Gemini API key is not configured")

        payload = {"contents": [{"parts": [{"text": prompt}]}]}
        if response_mime_type:
            payload["generationConfig"] = {"responseMimeType": response_mime_type}

        last_error = None
        for model in (self.DEFAULT_MODEL, self.FALLBACK_MODEL):
            url = f"{self.BASE_URL}/{model}:generateContent?key={self.api_key}"
            for _attempt in range(self.MAX_RETRIES):
                incr_daily_counter("gemini:calls")
                started = time.monotonic()
                try:
                    response = requests.post(url, json=payload, timeout=timeout)
                except requests.RequestException as exc:
                    last_error = exc
                    incr_daily_counter("gemini:errors")
                    log.warning(f"Gemini request exception on {model}: {exc}")
                    continue

                elapsed_ms = int((time.monotonic() - started) * 1000)
                if response.status_code == 200:
                    result = response.json()
                    self._record_usage(result)
                    log.info(f"Gemini call succeeded on {model} in {elapsed_ms}ms")
                    return result

                last_error = RuntimeError(f"Gemini returned HTTP {response.status_code}")
                incr_daily_counter("gemini:errors")
                log.warning(f"Gemini call failed on {model} with {response.status_code} in {elapsed_ms}ms")

                if response.status_code == 429:
                    wait_s = 2 ** (_attempt + 1)
                    log.warning(f"Gemini rate limited on {model}, waiting {wait_s}s before fallback")
                    time.sleep(wait_s)
                    break
                if response.status_code >= 500:
                    continue
                break

        # All Gemini models failed — try local Ollama as final fallback
        ollama_result = self._request_ollama(prompt, response_mime_type)
        if ollama_result is not None:
            return ollama_result

        raise RuntimeError(f"Gemini API failed after retries: {last_error}")

    def _request_ollama(self, prompt: str, response_mime_type: str | None) -> dict | None:
        """Call a local Ollama model as fallback. Returns None if Ollama is unavailable."""
        try:
            json_instruction = (
                "\n\nIMPORTANT: Respond with ONLY valid JSON, no markdown, no explanation."
                if response_mime_type == "application/json" else ""
            )
            payload = {
                "model": self.OLLAMA_MODEL,
                "prompt": prompt + json_instruction,
                "stream": False,
            }
            response = requests.post(
                f"{self.OLLAMA_URL}/api/generate",
                json=payload,
                timeout=60,
            )
            if response.status_code != 200:
                log.warning("ollama.request_failed", status=response.status_code)
                return None
            text = response.json().get("response", "")
            if not text:
                return None
            log.info("ollama.request_succeeded", model=self.OLLAMA_MODEL)
            # Wrap in Gemini-compatible response shape so _extract_text works
            return {"candidates": [{"content": {"parts": [{"text": text}]}, "finishReason": "STOP"}]}
        except Exception as exc:
            log.warning("ollama.unavailable", error=str(exc))
            return None

    @staticmethod
    def _extract_text(result: dict) -> str:
        try:
            candidates = result.get("candidates") or []
            if not candidates:
                block_reason = (result.get("promptFeedback") or {}).get("blockReason")
                log.warning("gemini.no_candidates", block_reason=block_reason)
                return ""
            candidate = candidates[0]
            finish_reason = candidate.get("finishReason", "")
            if finish_reason == "SAFETY":
                safety_ratings = candidate.get("safetyRatings", [])
                log.warning("gemini.safety_blocked", ratings=safety_ratings)
                return ""
            return candidate["content"]["parts"][0]["text"]
        except (KeyError, IndexError, TypeError) as exc:
            log.warning("gemini.extract_text_failed", error=str(exc))
            return ""

    @staticmethod
    def _parse_jsonish_text(text: str):
        cleaned = (text or "").strip()
        if not cleaned:
            return {}

        if cleaned.startswith("```"):
            cleaned = cleaned.strip("`")
            if "\n" in cleaned:
                cleaned = cleaned.split("\n", 1)[1]
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]
            cleaned = cleaned.strip()

        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            pass

        # Repair common Ollama malformation: ["key": val, ...] instead of [{"key": val}]
        # Detected when text starts with `["` and has `:` before the first `{`
        repaired = _repair_ollama_json(cleaned)
        if repaired != cleaned:
            try:
                return json.loads(repaired)
            except json.JSONDecodeError:
                pass

        # Gemini mocks and some providers occasionally return Python-literal-style
        # dicts/lists. Accept those as a fallback for robustness.
        try:
            return ast.literal_eval(cleaned)
        except (ValueError, SyntaxError) as exc:
            raise json.JSONDecodeError("Unable to parse Gemini response", cleaned, 0) from exc

    @staticmethod
    def _record_usage(result: dict):
        usage = result.get("usageMetadata") or {}
        total_tokens = usage.get("totalTokenCount")
        if total_tokens:
            incr_daily_counter("gemini:tokens", amount=total_tokens)

    @staticmethod
    def _merge_polish_updates(itinerary_data: dict, polished_content):
        # Fix 4: surface non-list responses instead of silently bailing
        if not isinstance(polished_content, list):
            if isinstance(polished_content, dict):
                # Gemini sometimes wraps the array under a key — try all common ones
                for key in ("itinerary", "days", "updates", "response", "data", "result", "polished", "output"):
                    candidate = polished_content.get(key)
                    if isinstance(candidate, list):
                        log.info(f"_merge_polish_updates: extracted list from dict key '{key}'")
                        polished_content = candidate
                        break
                else:
                    log.warning(
                        f"_merge_polish_updates: expected list, got dict with keys "
                        f"{list(polished_content.keys())}. Polish merge skipped."
                    )
                    return
            else:
                log.warning(
                    f"_merge_polish_updates: expected list, got "
                    f"{type(polished_content).__name__}. Polish merge skipped."
                )
                return

        for day_index, day in enumerate(itinerary_data.get("itinerary", [])):
            if day_index >= len(polished_content):
                continue
            updates = polished_content[day_index].get("activities", [])
            for activity_index, activity in enumerate(day.get("activities", [])):
                if activity_index >= len(updates):
                    continue
                update = updates[activity_index]
                # Fix 2: only write fields Gemini actually returned — never overwrite
                # with hardcoded generic strings like "Perfect for your trip style"
                for field in ("description", "why_this_fits", "local_secret", "how_to_reach"):
                    val = update.get(field)
                    if val:
                        activity[field] = val

    @staticmethod
    def _fallback_skeleton(itinerary_data: dict):
        skeleton = []
        for day in itinerary_data.get("itinerary", []):
            skeleton.append({
                "day": day.get("day"),
                "theme": day.get("theme"),
                "activities": [activity.get("activity") for activity in day.get("activities", [])],
            })
        return skeleton

    def _build_skeleton(self, itinerary_data: dict):
        if _token_optimizer:
            savings = _token_optimizer.estimate_savings(itinerary_data)
            log.info(
                f"TokenOptimizer: {savings['char_reduction_pct']}% char reduction, "
                f"~{savings['estimated_token_reduction_pct']}% token savings"
            )
            mark_status("agent", "token_optimizer", "ok", savings)
            return _token_optimizer.build_skeleton(itinerary_data)
        return self._fallback_skeleton(itinerary_data)


import threading as _threading

_gemini_service: GeminiService | None = None
_gemini_service_lock = _threading.Lock()


def get_gemini_service() -> GeminiService:
    global _gemini_service
    if _gemini_service is None:
        with _gemini_service_lock:
            if _gemini_service is None:
                _gemini_service = GeminiService()
    return _gemini_service
