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


class GeminiService:
    BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models"
    DEFAULT_MODEL = "gemini-2.0-flash"
    FALLBACK_MODEL = "gemini-2.0-flash-lite"
    MAX_RETRIES = 3

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

Rewrite ONLY these fields for each activity:
- description
- why_this_fits
- local_secret
- how_to_reach

STRICT RULES:
- NEVER change activity names, destination names, accommodation names, or theme names.
- NEVER change cost, time, time_range, latitude, longitude, day_total, total_cost,
  accommodation cost, or any numeric or coordinate value.
- NEVER add or remove activities.
- NEVER reorder activities.
- Return the exact same JSON shape for the updates you provide.
- Keep each description under 60 words.
- Write in second person.

Return ONLY a JSON array of daily activity text updates.
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

Generate JSON with:
- trip_title: a vivid 5-8 word title
- smart_insights: array of 3 practical insights
- packing_tips: array of 3-5 destination-aware packing tips

STRICT RULES:
- NEVER change place names or any costs.
- Return ONLY the JSON object.
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
                    break
                if response.status_code >= 500:
                    continue
                break

        raise RuntimeError(f"Gemini API failed after retries: {last_error}")

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
        if not isinstance(polished_content, list):
            return

        for day_index, day in enumerate(itinerary_data.get("itinerary", [])):
            if day_index >= len(polished_content):
                continue
            updates = polished_content[day_index].get("activities", [])
            for activity_index, activity in enumerate(day.get("activities", [])):
                if activity_index >= len(updates):
                    continue
                update = updates[activity_index]
                activity["description"] = update.get("description", activity.get("description", ""))
                activity["why_this_fits"] = update.get("why_this_fits", activity.get("why_this_fits", "Perfect for your trip style"))
                activity["local_secret"] = update.get("local_secret", activity.get("local_secret", "Visit early to avoid crowds"))
                activity["how_to_reach"] = update.get("how_to_reach", activity.get("how_to_reach", ""))

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


_gemini_service = None


def get_gemini_service() -> GeminiService:
    global _gemini_service
    if _gemini_service is None:
        _gemini_service = GeminiService()
    return _gemini_service
