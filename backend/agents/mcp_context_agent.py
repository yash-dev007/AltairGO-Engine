"""
MCP Context Agent — Live Context Enrichment for Gemini Polish
═════════════════════════════════════════════════════════════
Inspired by: AI Agents/ai_travel_planner_mcp_agent_team/app.py (Agno + MCP)

Fetches live contextual data (weather, festivals, seasonal alerts) right
before the Gemini text-polish phase runs.  This ensures that smart_insights
and packing_tips are grounded in current conditions rather than stale
training data.

Usage:
    agent = MCPContextAgent()
    ctx   = agent.fetch_live_context("Jaipur", travel_month="mar")
    prompt = agent.build_enriched_prompt(base_prompt, ctx)
"""

import os
import json
import logging
from datetime import datetime

import httpx

log = logging.getLogger(__name__)

# ── Free weather API (no key needed) ─────────────────────────────
WTTR_URL = "https://wttr.in/{city}?format=j1"

# ── Indian festivals / seasonal data (built-in knowledge base) ──
FESTIVAL_CALENDAR = {
    "jan": ["Makar Sankranti", "Republic Day (26th)", "Pongal (South India)"],
    "feb": ["Vasant Panchami"],
    "mar": ["Holi", "Maha Shivaratri"],
    "apr": ["Baisakhi", "Ram Navami", "Easter"],
    "may": ["Buddha Purnima"],
    "jun": ["Eid al-Adha (varies)"],
    "jul": ["Guru Purnima", "Monsoon season begins"],
    "aug": ["Independence Day (15th)", "Raksha Bandhan", "Janmashtami"],
    "sep": ["Ganesh Chaturthi", "Onam (Kerala)"],
    "oct": ["Navratri", "Durga Puja", "Dussehra", "Gandhi Jayanti (2nd)"],
    "nov": ["Diwali", "Chhath Puja", "Guru Nanak Jayanti"],
    "dec": ["Christmas", "New Year celebrations"],
}

SEASONAL_ALERTS = {
    "jun": "☔ Monsoon season — carry waterproof gear and umbrella.",
    "jul": "☔ Heavy monsoon — some outdoor attractions may close. Roads can flood.",
    "aug": "☔ Monsoon continues — humid conditions, carry light rain jacket.",
    "sep": "🌤️ Late monsoon — occasional showers, humidity dropping.",
    "apr": "🔥 Peak summer — temperatures can exceed 45°C in North India.",
    "may": "🔥 Extreme heat — carry sun protection, stay hydrated.",
    "dec": "❄️ Winter — fog can delay flights in North India.",
    "jan": "❄️ Cold mornings in northern cities — layer up.",
}

MONTH_ABBR = {
    1: "jan", 2: "feb", 3: "mar", 4: "apr", 5: "may", 6: "jun",
    7: "jul", 8: "aug", 9: "sep", 10: "oct", 11: "nov", 12: "dec",
}


class MCPContextAgent:
    """
    Enriches the Gemini polish prompt with live, real-time context
    so that smart_insights and packing_tips are current and accurate.
    """

    def __init__(self):
        pass

    # ── Public API ───────────────────────────────────────────────

    def fetch_live_context(
        self, destination: str, travel_month: str | None = None
    ) -> dict:
        """
        Gather all available live context for a destination.

        Args:
            destination: city name (e.g. "Jaipur")
            travel_month: 3-letter month (e.g. "mar"). Defaults to current.

        Returns:
            dict with keys: weather, festivals, seasonal_alert, safety_notes
        """
        if not travel_month:
            travel_month = MONTH_ABBR.get(datetime.now().month, "jan")

        weather = self._fetch_weather(destination)
        festivals = FESTIVAL_CALENDAR.get(travel_month, [])
        seasonal_alert = SEASONAL_ALERTS.get(travel_month, "")

        # Build safety notes based on season
        safety_notes = self._build_safety_notes(destination, travel_month)

        context = {
            "weather": weather,
            "festivals": festivals,
            "seasonal_alert": seasonal_alert,
            "safety_notes": safety_notes,
            "travel_month": travel_month,
            "destination": destination,
        }

        log.info(
            f"MCPContextAgent: Fetched context for {destination} ({travel_month}): "
            f"weather={'yes' if weather else 'no'}, "
            f"{len(festivals)} festivals."
        )
        return context

    def build_enriched_prompt(
        self, base_prompt: str, context: dict
    ) -> str:
        """
        Inject live context into the Gemini polish prompt.

        Args:
            base_prompt: the original prompt for Gemini
            context: dict from fetch_live_context()

        Returns:
            Enriched prompt string with context section prepended.
        """
        context_section = "\n--- LIVE CONTEXT (use for insights & packing tips) ---\n"

        if context.get("weather"):
            w = context["weather"]
            context_section += (
                f"Current weather in {context['destination']}: "
                f"{w.get('description', 'N/A')}, "
                f"Temp: {w.get('temp_c', 'N/A')}°C, "
                f"Humidity: {w.get('humidity', 'N/A')}%\n"
            )

        if context.get("festivals"):
            context_section += (
                f"Upcoming festivals: {', '.join(context['festivals'])}\n"
            )

        if context.get("seasonal_alert"):
            context_section += f"Seasonal alert: {context['seasonal_alert']}\n"

        if context.get("safety_notes"):
            context_section += f"Safety: {context['safety_notes']}\n"

        context_section += "--- END LIVE CONTEXT ---\n\n"

        return context_section + base_prompt

    # ── Weather fetcher ──────────────────────────────────────────

    def _fetch_weather(self, city: str) -> dict | None:
        """Fetch current weather from wttr.in (free, no API key)."""
        try:
            url = WTTR_URL.format(city=city.replace(" ", "+"))
            with httpx.Client(timeout=8) as client:
                resp = client.get(url)
                if resp.status_code != 200:
                    log.warning(f"MCPContextAgent: Weather API returned {resp.status_code}")
                    return None

                data = resp.json()
                current = data.get("current_condition", [{}])[0]

                return {
                    "temp_c": current.get("temp_C", "N/A"),
                    "humidity": current.get("humidity", "N/A"),
                    "description": (
                        current.get("weatherDesc", [{}])[0].get("value", "N/A")
                    ),
                    "wind_kmph": current.get("windspeedKmph", "N/A"),
                    "feels_like_c": current.get("FeelsLikeC", "N/A"),
                }

        except httpx.TimeoutException:
            log.warning(f"MCPContextAgent: Weather API timeout for {city}")
            return None
        except Exception as e:
            log.warning(f"MCPContextAgent: Weather fetch error: {e}")
            return None

    # ── Safety notes builder ─────────────────────────────────────

    @staticmethod
    def _build_safety_notes(destination: str, month: str) -> str:
        """Build destination + season specific safety notes."""
        notes = []

        # Monsoon-specific
        if month in ("jun", "jul", "aug", "sep"):
            notes.append("Roads may be slippery; carry non-slip footwear.")
            if destination.lower() in ("goa", "kochi", "mumbai"):
                notes.append("Coastal areas may have rough seas — avoid swimming.")

        # Summer-specific
        if month in ("apr", "may", "jun"):
            notes.append("Carry sunscreen (SPF 50+) and a water bottle at all times.")
            if destination.lower() in ("jaipur", "delhi", "agra", "varanasi"):
                notes.append(
                    "Plan outdoor activities before 10 AM or after 4 PM to avoid heat."
                )

        # Winter-specific
        if month in ("dec", "jan", "feb"):
            if destination.lower() in ("delhi", "agra", "varanasi"):
                notes.append("Dense fog possible — confirm flight status in advance.")

        return " ".join(notes) if notes else "No special safety alerts."
