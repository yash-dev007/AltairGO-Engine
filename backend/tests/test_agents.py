"""
test_agents.py — Tests for the AltairGO AI Agents Layer.
Covers: WebScraperAgent, MemoryAgent, MCPContextAgent, TokenOptimizer, ItineraryQAAgent.
All external HTTP calls are mocked.
"""

import pytest
import json
from unittest.mock import patch, MagicMock, PropertyMock


# ─────────────────────────────────────────────────────
# Web Scraper Agent
# ─────────────────────────────────────────────────────
MOCK_HTML_ATTRACTION = """
<html><body>
<h1>Amber Fort - Tickets</h1>
<div class="pricing">
  <p>Adult Entry: ₹550</p>
  <p>Child Entry (under 12): ₹200</p>
  <p>Opening Hours: 09:00 - 17:00</p>
</div>
</body></html>
"""

MOCK_GEMINI_SCRAPE_RESPONSE = {
    "candidates": [{
        "content": {
            "parts": [{
                "text": json.dumps({
                    "entry_cost_adult": 550,
                    "entry_cost_child": 200,
                    "currency": "INR",
                    "opening_hours": "09:00-17:00",
                    "is_free": False,
                })
            }]
        }
    }]
}


class TestWebScraperAgent:

    def test_scrape_attraction_price_success(self):
        from backend.agents.web_scraper_agent import WebScraperAgent

        agent = WebScraperAgent(api_key="test-key")
        with patch.object(agent, '_fetch_html', return_value=MOCK_HTML_ATTRACTION):
            with patch("backend.agents.web_scraper_agent.requests.post") as mock_post:
                mock_post.return_value.status_code = 200
                mock_post.return_value.json.return_value = MOCK_GEMINI_SCRAPE_RESPONSE
                result = agent.scrape_attraction_price("https://amberfort.org/tickets")

                assert result is not None
                assert result["entry_cost_adult"] == 550
                assert result["entry_cost_child"] == 200
                assert result["currency"] == "INR"

    def test_scrape_returns_none_on_empty_html(self):
        from backend.agents.web_scraper_agent import WebScraperAgent

        agent = WebScraperAgent(api_key="test-key")
        with patch.object(agent, '_fetch_html', return_value=None):
            result = agent.scrape_attraction_price("https://example.com")
            assert result is None

    def test_scrape_returns_none_without_api_key(self):
        from backend.agents.web_scraper_agent import WebScraperAgent

        agent = WebScraperAgent(api_key="")
        with patch.object(agent, '_fetch_html', return_value=MOCK_HTML_ATTRACTION):
            result = agent.scrape_attraction_price("https://example.com")
            assert result is None

    def test_scrape_hotel_price_success(self):
        from backend.agents.web_scraper_agent import WebScraperAgent

        mock_hotel_response = {
            "candidates": [{
                "content": {
                    "parts": [{
                        "text": json.dumps({
                            "price_per_night_min": 3500,
                            "price_per_night_max": 8000,
                            "currency": "INR",
                            "star_rating": 4,
                            "amenities": ["WiFi", "Pool"],
                        })
                    }]
                }
            }]
        }
        agent = WebScraperAgent(api_key="test-key")
        with patch.object(agent, '_fetch_html', return_value="<html>hotel</html>"):
            with patch("backend.agents.web_scraper_agent.requests.post") as mock_post:
                mock_post.return_value.status_code = 200
                mock_post.return_value.json.return_value = mock_hotel_response
                result = agent.scrape_hotel_price("https://hotel.example.com")

                assert result is not None
                assert result["price_per_night_min"] == 3500
                assert result["star_rating"] == 4

    def test_scrape_handles_gemini_error(self):
        from backend.agents.web_scraper_agent import WebScraperAgent

        agent = WebScraperAgent(api_key="test-key")
        with patch.object(agent, '_fetch_html', return_value="<html>test</html>"):
            with patch("backend.agents.web_scraper_agent.requests.post") as mock_post:
                mock_post.return_value.status_code = 500
                result = agent.scrape_attraction_price("https://example.com")
                assert result is None


# ─────────────────────────────────────────────────────
# Memory Agent
# ─────────────────────────────────────────────────────
class TestMemoryAgent:

    def test_empty_preferences_without_db(self):
        from backend.agents.memory_agent import MemoryAgent

        agent = MemoryAgent(db_session=None)
        prefs = agent.get_user_preferences(user_id=1)
        assert prefs["signal_count"] == 0
        assert prefs["preferred_types"] == []
        assert prefs["excluded_types"] == []

    def test_inject_preferences_passthrough_below_threshold(self):
        from backend.agents.memory_agent import MemoryAgent

        agent = MemoryAgent(db_session=None)
        base = {"budget_tier": "mid", "traveler_type": "couple"}
        merged = agent.inject_preferences(user_id=1, base_preferences=base)
        # Without enough signals, base prefs should pass through unchanged
        assert merged["budget_tier"] == "mid"
        assert "_memory_applied" not in merged

    def test_inject_preferences_adds_exclusions(self):
        from backend.agents.memory_agent import MemoryAgent

        agent = MemoryAgent(db_session=None)
        # Mock learn_from_signals to return learned prefs
        learned = {
            "preferred_types": ["heritage", "fort"],
            "excluded_types": ["nightlife"],
            "preferred_budget_tier": "budget",
            "preferred_time_of_day": "morning",
            "signal_count": 20,
        }
        with patch.object(agent, 'learn_from_signals', return_value=learned):
            base = {"traveler_type": "couple", "excluded_types": ["spa"]}
            merged = agent.inject_preferences(user_id=42, base_preferences=base)

            assert "nightlife" in merged["excluded_types"]
            assert "spa" in merged["excluded_types"]
            assert merged["_memory_applied"] is True
            assert merged["preferred_attraction_types"] == ["heritage", "fort"]


# ─────────────────────────────────────────────────────
# MCP Context Agent
# ─────────────────────────────────────────────────────
MOCK_WEATHER_RESPONSE = {
    "current_condition": [{
        "temp_C": "32",
        "humidity": "45",
        "weatherDesc": [{"value": "Sunny"}],
        "windspeedKmph": "12",
        "FeelsLikeC": "35",
    }]
}


class TestMCPContextAgent:

    @patch("backend.agents.mcp_context_agent.httpx.Client")
    def test_fetch_live_context_with_weather(self, mock_client_class):
        from backend.agents.mcp_context_agent import MCPContextAgent

        mock_client = MagicMock()
        mock_client_class.return_value.__enter__ = MagicMock(return_value=mock_client)
        mock_client_class.return_value.__exit__ = MagicMock(return_value=False)
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = MOCK_WEATHER_RESPONSE
        mock_client.get.return_value = mock_response

        agent = MCPContextAgent()
        ctx = agent.fetch_live_context("Jaipur", travel_month="mar")

        assert ctx["destination"] == "Jaipur"
        assert ctx["travel_month"] == "mar"
        assert "Holi" in ctx["festivals"]
        assert ctx["weather"]["temp_c"] == "32"

    def test_fetch_context_returns_festivals_for_month(self):
        from backend.agents.mcp_context_agent import MCPContextAgent

        agent = MCPContextAgent()
        with patch.object(agent, '_fetch_weather', return_value=None):
            ctx = agent.fetch_live_context("Delhi", travel_month="oct")
            assert "Navratri" in ctx["festivals"]
            assert "Diwali" not in ctx["festivals"]  # Diwali is in Nov

    def test_build_enriched_prompt_adds_context(self):
        from backend.agents.mcp_context_agent import MCPContextAgent

        agent = MCPContextAgent()
        context = {
            "weather": {"temp_c": "32", "humidity": "45", "description": "Sunny"},
            "festivals": ["Holi"],
            "seasonal_alert": "No alerts.",
            "safety_notes": "Carry sunscreen.",
            "destination": "Jaipur",
        }
        base_prompt = "Write a travel description."
        enriched = agent.build_enriched_prompt(base_prompt, context)

        assert "LIVE CONTEXT" in enriched
        assert "Sunny" in enriched
        assert "Holi" in enriched
        assert "Write a travel description." in enriched

    def test_seasonal_alerts_for_monsoon(self):
        from backend.agents.mcp_context_agent import MCPContextAgent

        agent = MCPContextAgent()
        with patch.object(agent, '_fetch_weather', return_value=None):
            ctx = agent.fetch_live_context("Mumbai", travel_month="jul")
            assert "monsoon" in ctx["seasonal_alert"].lower()


# ─────────────────────────────────────────────────────
# Token Optimizer
# ─────────────────────────────────────────────────────
SAMPLE_ITINERARY = {
    "total_cost": 9000,
    "cost_breakdown": {"accommodation": 3150, "food": 2250},
    "itinerary": [
        {
            "day": 1,
            "theme": "Heritage & Forts",
            "pacing_level": "moderate",
            "day_total": 3200,
            "activities": [
                {
                    "activity": "Amber Fort",
                    "time": "09:00",
                    "cost": 550,
                    "latitude": 26.9855,
                    "longitude": 75.8513,
                    "popularity_score": 95,
                    "description": "Explore the fort.",
                    "why_this_fits": "Heritage lover",
                    "local_secret": "Go early",
                    "how_to_reach": "Auto-rickshaw",
                    "booking_url": "https://amberfort.org",
                }
            ],
        }
    ],
}


class TestTokenOptimizer:

    def test_compress_strips_engine_fields(self):
        from backend.agents.token_optimizer import TokenOptimizer

        optimizer = TokenOptimizer(use_key_aliases=False)
        compressed = optimizer.compress_for_gemini(SAMPLE_ITINERARY)
        parsed = json.loads(compressed)

        # Engine-internal fields should be stripped
        act = parsed["itinerary"][0]["activities"][0]
        assert "latitude" not in act
        assert "longitude" not in act
        assert "popularity_score" not in act
        assert "booking_url" not in act

        # User-facing fields should remain
        assert act["activity"] == "Amber Fort"
        assert act["cost"] == 550

    def test_compress_reduces_size(self):
        from backend.agents.token_optimizer import TokenOptimizer

        optimizer = TokenOptimizer()
        savings = optimizer.estimate_savings(SAMPLE_ITINERARY)
        assert savings["char_reduction_pct"] > 0
        assert savings["compressed_chars"] < savings["original_chars"]

    def test_build_skeleton_extracts_minimal(self):
        from backend.agents.token_optimizer import TokenOptimizer

        optimizer = TokenOptimizer()
        skeleton = optimizer.build_skeleton(SAMPLE_ITINERARY)
        assert len(skeleton) == 1
        assert skeleton[0]["day"] == 1
        assert skeleton[0]["theme"] == "Heritage & Forts"
        assert "Amber Fort" in skeleton[0]["activities"]

    def test_compress_uses_key_aliases(self):
        from backend.agents.token_optimizer import TokenOptimizer

        optimizer = TokenOptimizer(use_key_aliases=True)
        compressed = optimizer.compress_for_gemini(SAMPLE_ITINERARY)
        # Check that aliased keys appear
        assert '"acts"' in compressed or '"accom"' in compressed

    def test_original_data_not_mutated(self):
        import copy
        from backend.agents.token_optimizer import TokenOptimizer

        original = copy.deepcopy(SAMPLE_ITINERARY)
        optimizer = TokenOptimizer()
        optimizer.compress_for_gemini(SAMPLE_ITINERARY)
        # Original should be unchanged
        assert SAMPLE_ITINERARY == original


# ─────────────────────────────────────────────────────
# Itinerary QA Agent
# ─────────────────────────────────────────────────────
GOOD_ITINERARY = {
    "total_cost": 9000,
    "cost_breakdown": {"accommodation": 3150, "food": 2250},
    "smart_insights": ["Visit in winter"],
    "packing_tips": ["Light clothes"],
    "itinerary": [
        {
            "day": 1,
            "theme": "Heritage",
            "pacing_level": "moderate",
            "day_total": 3200,
            "activities": [
                {
                    "activity": "Amber Fort",
                    "time": "09:00",
                    "cost": 550,
                    "duration_minutes": 120,
                    "latitude": 26.9855,
                    "longitude": 75.8513,
                    "name": "Amber Fort",
                    "description": "A beautiful fort.",
                },
                {
                    "activity": "Hawa Mahal",
                    "time": "12:00",
                    "cost": 200,
                    "duration_minutes": 60,
                    "latitude": 26.9239,
                    "longitude": 75.8267,
                    "name": "Hawa Mahal",
                    "description": "Palace of Winds.",
                },
            ],
        }
    ],
}


class TestItineraryQAAgent:

    def test_good_itinerary_passes(self):
        from backend.agents.itinerary_qa_agent import ItineraryQAAgent

        qa = ItineraryQAAgent()
        report = qa.review_itinerary(GOOD_ITINERARY)
        assert report["passed"] is True
        assert report["score"] >= 70

    def test_missing_itinerary_fails(self):
        from backend.agents.itinerary_qa_agent import ItineraryQAAgent

        qa = ItineraryQAAgent()
        report = qa.review_itinerary({"total_cost": 0})
        assert report["passed"] is False
        assert any(i["type"] == "missing_field" for i in report["issues"])

    def test_overpacked_day_detected(self):
        from backend.agents.itinerary_qa_agent import ItineraryQAAgent

        overpacked = {
            "total_cost": 9000,
            "cost_breakdown": {},
            "smart_insights": [],
            "itinerary": [{
                "day": 1,
                "theme": "Busy",
                "day_total": 5000,
                "activities": [
                    {"activity": f"Activity {i}", "cost": 100,
                     "duration_minutes": 120, "name": f"Activity {i}"}
                    for i in range(10)
                ],
            }],
        }
        qa = ItineraryQAAgent()
        report = qa.review_itinerary(overpacked)
        assert any(i["type"] == "overpacked_day" for i in report["issues"])

    def test_cost_mismatch_detected_and_fixed(self):
        from backend.agents.itinerary_qa_agent import ItineraryQAAgent
        import copy

        bad_cost = copy.deepcopy(GOOD_ITINERARY)
        bad_cost["total_cost"] = 100  # way off from day_totals sum (3200)
        qa = ItineraryQAAgent()
        report = qa.review_itinerary(bad_cost)
        assert any(i["type"] == "cost_mismatch" for i in report["issues"])

        # Auto-fix
        fixed = qa.auto_fix(bad_cost, report)
        assert fixed["total_cost"] == 3200

    def test_geographic_backtrack_detected(self):
        from backend.agents.itinerary_qa_agent import ItineraryQAAgent

        far_apart = {
            "total_cost": 5000,
            "cost_breakdown": {},
            "smart_insights": [],
            "itinerary": [{
                "day": 1,
                "theme": "Spread Out",
                "day_total": 5000,
                "activities": [
                    {
                        "activity": "Place A", "name": "Place A",
                        "cost": 100, "duration_minutes": 60,
                        "latitude": 26.9, "longitude": 75.8,
                    },
                    {
                        "activity": "Place B", "name": "Place B",
                        "cost": 100, "duration_minutes": 60,
                        "latitude": 28.6, "longitude": 77.2,  # Delhi (~250km away)
                    },
                ],
            }],
        }
        qa = ItineraryQAAgent()
        report = qa.review_itinerary(far_apart)
        assert any(i["type"] == "geographic_backtrack" for i in report["issues"])

    def test_empty_itinerary_detected(self):
        from backend.agents.itinerary_qa_agent import ItineraryQAAgent

        qa = ItineraryQAAgent()
        report = qa.review_itinerary({"itinerary": [], "total_cost": 0})
        assert report["passed"] is False
