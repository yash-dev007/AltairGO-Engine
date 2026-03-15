"""
Web Scraper Agent — Gemini-powered intelligent web scraping
═══════════════════════════════════════════════════════════
Inspired by: AI Agents/web_scraping_ai_agent/ai_scrapper.py (ScrapeGraphAI)

Provides a fallback data source for sync_prices.py when structured APIs
lack coverage. Uses httpx to fetch page HTML, then sends a targeted snippet
to Gemini for structured JSON extraction of prices, hours, and costs.

Usage in pipeline:
    agent = WebScraperAgent()
    price = agent.scrape_attraction_price("https://amberfort.org/tickets")
    hotel  = agent.scrape_hotel_price("https://hotelexample.com/rooms")
"""

import os
import json
import logging
import time
import requests
import httpx

log = logging.getLogger(__name__)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    "gemini-2.0-flash:generateContent"
)

# ── Rate-limiting ────────────────────────────────────────────────
_last_request_time: float = 0.0
MIN_REQUEST_INTERVAL_S = 2.0  # respect source websites


def _rate_limit():
    """Enforce minimum interval between outbound requests."""
    global _last_request_time
    elapsed = time.time() - _last_request_time
    if elapsed < MIN_REQUEST_INTERVAL_S:
        time.sleep(MIN_REQUEST_INTERVAL_S - elapsed)
    _last_request_time = time.time()


class WebScraperAgent:
    """
    Gemini-powered web scraper that extracts structured pricing data
    from attraction and hotel websites where APIs fall short.
    """

    MAX_HTML_CHARS = 8000  # truncate HTML to keep Gemini prompt lean

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or GEMINI_API_KEY

    # ── Public API ───────────────────────────────────────────────

    def scrape_attraction_price(self, url: str) -> dict | None:
        """
        Scrape an attraction website for pricing info.

        Returns:
            dict with keys: entry_cost_adult, entry_cost_child, currency,
                            opening_hours, is_free  — or None on failure.
        """
        html = self._fetch_html(url)
        if not html:
            return None

        prompt = f"""
You are a data extraction expert. Extract pricing information from this
attraction webpage HTML.

Return ONLY a JSON object with these fields:
- "entry_cost_adult": integer price in local currency (null if not found)
- "entry_cost_child": integer child price (null if not found)
- "currency": currency code like "INR", "USD" (default "INR")
- "opening_hours": string like "09:00-17:00" (null if not found)
- "is_free": boolean (true if explicitly free)

HTML content:
{html[:self.MAX_HTML_CHARS]}
"""
        return self._extract_with_gemini(prompt)

    def scrape_hotel_price(self, url: str) -> dict | None:
        """
        Scrape a hotel website for room pricing info.

        Returns:
            dict with keys: price_per_night_min, price_per_night_max,
                            currency, star_rating  — or None on failure.
        """
        html = self._fetch_html(url)
        if not html:
            return None

        prompt = f"""
You are a data extraction expert. Extract hotel pricing from this webpage HTML.

Return ONLY a JSON object with these fields:
- "price_per_night_min": integer minimum room price (null if not found)
- "price_per_night_max": integer maximum room price (null if not found)
- "currency": currency code like "INR", "USD" (default "INR")
- "star_rating": integer 1-5 (null if not found)
- "amenities": array of strings (empty array if not found)

HTML content:
{html[:self.MAX_HTML_CHARS]}
"""
        return self._extract_with_gemini(prompt)

    def scrape_custom(self, url: str, extraction_prompt: str) -> dict | None:
        """
        General-purpose scraping with a custom extraction prompt.
        The prompt should instruct Gemini to return JSON.
        """
        html = self._fetch_html(url)
        if not html:
            return None

        full_prompt = f"""
{extraction_prompt}

HTML content:
{html[:self.MAX_HTML_CHARS]}
"""
        return self._extract_with_gemini(full_prompt)

    # ── Internal helpers ─────────────────────────────────────────

    def _fetch_html(self, url: str) -> str | None:
        """Fetch HTML content from a URL with rate limiting."""
        _rate_limit()
        try:
            with httpx.Client(timeout=15, follow_redirects=True) as client:
                resp = client.get(url, headers={
                    "User-Agent": (
                        "Mozilla/5.0 (compatible; AltairGO-DataBot/1.0; "
                        "+https://altairgo.ai/bot)"
                    )
                })
                if resp.status_code == 200:
                    return resp.text
                log.warning(f"WebScraperAgent: HTTP {resp.status_code} for {url}")
                return None
        except httpx.TimeoutException:
            log.warning(f"WebScraperAgent: Timeout fetching {url}")
            return None
        except Exception as e:
            log.error(f"WebScraperAgent: Error fetching {url}: {e}")
            return None

    def _extract_with_gemini(self, prompt: str) -> dict | None:
        """Send prompt to Gemini and parse JSON response."""
        if not self.api_key:
            log.warning("WebScraperAgent: No Gemini API key, skipping extraction.")
            return None

        try:
            url = f"{GEMINI_URL}?key={self.api_key}"
            payload = {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"responseMimeType": "application/json"},
            }
            resp = requests.post(url, json=payload, timeout=15)
            if resp.status_code != 200:
                log.warning(f"WebScraperAgent: Gemini returned {resp.status_code}")
                return None

            result = resp.json()
            text = result["candidates"][0]["content"]["parts"][0]["text"]
            return json.loads(text)

        except (KeyError, IndexError, json.JSONDecodeError) as e:
            log.warning(f"WebScraperAgent: Failed to parse Gemini response: {e}")
            return None
        except Exception as e:
            log.error(f"WebScraperAgent: Gemini extraction error: {e}")
            return None
