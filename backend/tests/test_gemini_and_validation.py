"""
test_gemini_and_validation.py — Tests for GeminiService and ItineraryValidator.
Covers: prompt construction, response parsing, budget validation,
        generic name detection, cost consistency, and auto-correction.
All Gemini HTTP calls are mocked.
"""

import pytest
import copy
from unittest.mock import patch, MagicMock


# ─────────────────────────────────────────────────────
# Base valid itinerary for mutation tests
# ─────────────────────────────────────────────────────
def make_valid_itinerary(total_cost=9000):
    return {
        "trip_title": "Jaipur Heritage Explorer — 3 Days",
        "total_cost": total_cost,
        "cost_breakdown": {
            "accommodation": 3150,
            "food": 2250,
            "transport": 1800,
            "activities": 1350,
            "misc": 450,
        },
        "itinerary": [
            {
                "day": 1,
                "date": "2026-10-15",
                "location": "Jaipur",
                "theme": "Heritage & Forts",
                "pacing_level": "moderate",
                "day_total": 3200,
                "travel_hours": 0,
                "intensity_score": 6,
                "image_keyword": "Amber Fort Jaipur",
                "accommodation": {
                    "name": "Hotel Pink City",
                    "type": "mid-range",
                    "cost_per_night": 1800,
                    "location": "MI Road, Jaipur",
                    "why_this": "Central location",
                    "booking_tip": "Book in advance"
                },
                "activities": [
                    {
                        "time": "09:00",
                        "time_range": "09:00-11:30",
                        "activity": "Amber Fort",
                        "description": "Magnificent hilltop fort.",
                        "why_this_fits": "Perfect for heritage lovers",
                        "local_secret": "Visit on weekdays",
                        "cost": 550,
                        "how_to_reach": "Auto from city center",
                        "crowd_level": "moderate",
                        "meal_type": None,
                        "google_maps_search_query": "Amber Fort Jaipur"
                    }
                ]
            },
            {
                "day": 2,
                "date": "2026-10-16",
                "location": "Jaipur",
                "theme": "Culture & Arts",
                "pacing_level": "relaxed",
                "day_total": 2800,
                "travel_hours": 0,
                "intensity_score": 4,
                "image_keyword": "Hawa Mahal Jaipur",
                "accommodation": {
                    "name": "Hotel Pink City",
                    "type": "mid-range",
                    "cost_per_night": 1800,
                    "location": "MI Road, Jaipur",
                    "why_this": "Central location",
                    "booking_tip": "Book in advance"
                },
                "activities": [
                    {
                        "time": "10:00",
                        "time_range": "10:00-11:00",
                        "activity": "Hawa Mahal",
                        "description": "Palace of winds.",
                        "why_this_fits": "Iconic landmark",
                        "local_secret": "Best photos from outside",
                        "cost": 200,
                        "how_to_reach": "Walk from City Palace",
                        "crowd_level": "high",
                        "meal_type": None,
                        "google_maps_search_query": "Hawa Mahal Jaipur"
                    }
                ]
            },
            {
                "day": 3,
                "date": "2026-10-17",
                "location": "Jaipur",
                "theme": "Local Flavours",
                "pacing_level": "relaxed",
                "day_total": 3000,
                "travel_hours": 0,
                "intensity_score": 3,
                "image_keyword": "Jaipur market",
                "accommodation": {
                    "name": "Hotel Pink City",
                    "type": "mid-range",
                    "cost_per_night": 1800,
                    "location": "MI Road, Jaipur",
                    "why_this": "Central location",
                    "booking_tip": "Book in advance"
                },
                "activities": []
            }
        ],
        "travel_between_cities": [],
        "smart_insights": ["Best in winter", "Carry cash"],
        "packing_tips": ["Light cotton", "Walking shoes"]
    }


# ─────────────────────────────────────────────────────
# ItineraryValidator
# ─────────────────────────────────────────────────────
class TestItineraryValidator:

    @pytest.fixture
    def validator(self):
        from backend.validation import ItineraryValidator
        return ItineraryValidator(strict=True)

    def test_valid_itinerary_passes(self, validator):
        result = validator.validate(make_valid_itinerary(9000), user_budget=9000)
        assert result["valid"] is True
        assert len(result.get("errors", [])) == 0

    # ── Required fields ──────────────────────────────
    def test_missing_trip_title_fails(self, validator):
        data = make_valid_itinerary()
        del data["trip_title"]
        result = validator.validate(data, user_budget=9000)
        assert result["valid"] is False

    def test_missing_total_cost_fails(self, validator):
        data = make_valid_itinerary()
        del data["total_cost"]
        result = validator.validate(data, user_budget=9000)
        assert result["valid"] is False

    def test_missing_itinerary_key_fails(self, validator):
        data = make_valid_itinerary()
        del data["itinerary"]
        result = validator.validate(data, user_budget=9000)
        assert result["valid"] is False

    def test_empty_itinerary_fails(self, validator):
        data = make_valid_itinerary()
        data["itinerary"] = []
        result = validator.validate(data, user_budget=9000)
        assert result["valid"] is False

    # ── Budget checks ────────────────────────────────
    def test_cost_within_5_percent_passes(self, validator):
        data = make_valid_itinerary(total_cost=9300)  # 3.3% over 9000
        result = validator.validate(data, user_budget=9000)
        assert result["valid"] is True

    def test_cost_over_5_percent_triggers_auto_scale(self, validator):
        data = make_valid_itinerary(total_cost=12000)  # 33% over budget
        result = validator.validate(data, user_budget=9000)
        # strict mode auto-scales and returns corrected itinerary
        assert result.get("corrected") is not None
        assert result["corrected"]["total_cost"] <= 9000 * 1.05

    def test_auto_scale_preserves_proportions(self, validator):
        data = make_valid_itinerary(total_cost=15000)
        result = validator.validate(data, user_budget=9000)
        corrected = result["corrected"]
        original_ratio = data["cost_breakdown"]["accommodation"] / data["total_cost"]
        corrected_ratio = corrected["cost_breakdown"]["accommodation"] / corrected["total_cost"]
        assert abs(original_ratio - corrected_ratio) < 0.05

    def test_day_totals_consistency_check(self, validator):
        """Sum of day_totals should roughly equal total_cost (±15%)."""
        data = make_valid_itinerary(total_cost=9000)
        data["itinerary"][0]["day_total"] = 100  # artificially low
        result = validator.validate(data, user_budget=9000)
        assert result["valid"] is False or result.get("warnings")

    # ── Generic name detection ────────────────────────
    def test_generic_activity_name_flagged(self, validator):
        data = make_valid_itinerary()
        data["itinerary"][0]["activities"][0]["activity"] = "local market"  # too generic
        result = validator.validate(data, user_budget=9000)
        assert not result["valid"] or len(result.get("warnings", [])) > 0

    def test_generic_names_list(self, validator):
        """These should all be flagged as generic."""
        generic_names = ["local market", "beach", "restaurant", "park", "temple",
                         "historical site", "museum", "viewpoint"]
        for name in generic_names:
            data = make_valid_itinerary()
            data["itinerary"][0]["activities"][0]["activity"] = name
            result = validator.validate(data, user_budget=9000)
            flagged = not result["valid"] or len(result.get("warnings", [])) > 0
            assert flagged, f"'{name}' should be flagged as generic"

    def test_specific_name_not_flagged(self, validator):
        data = make_valid_itinerary()
        data["itinerary"][0]["activities"][0]["activity"] = "Amber Fort"  # specific
        result = validator.validate(data, user_budget=9000)
        assert result["valid"] is True

    # ── Activity count ────────────────────────────────
    def test_overpacked_day_flagged(self, validator):
        """More than 5 activities in a single day = overpacked."""
        data = make_valid_itinerary()
        base_activity = data["itinerary"][0]["activities"][0]
        data["itinerary"][0]["activities"] = [
            {**base_activity, "activity": f"Attraction {i}"}
            for i in range(7)
        ]
        result = validator.validate(data, user_budget=9000)
        assert not result["valid"] or len(result.get("warnings", [])) > 0

    def test_5_activities_not_flagged(self, validator):
        data = make_valid_itinerary()
        base_activity = data["itinerary"][0]["activities"][0]
        data["itinerary"][0]["activities"] = [
            {**base_activity, "activity": f"Named Attraction {i}"}
            for i in range(5)
        ]
        result = validator.validate(data, user_budget=9000)
        # 5 is the cap, should not produce overpacked warning
        overpacked_warnings = [
            w for w in result.get("warnings", [])
            if "overpacked" in w.lower()
        ]
        assert len(overpacked_warnings) == 0


# ─────────────────────────────────────────────────────
# GeminiService
# ─────────────────────────────────────────────────────
class TestGeminiService:

    @pytest.fixture
    def service(self, app):
        from backend.services.gemini_service import GeminiService
        return GeminiService(api_key="fake-key-for-testing")

    @pytest.fixture
    def preferences(self):
        return {
            "destination_country": "India",
            "start_city": "Mumbai",
            "selected_destinations": [{"id": 1, "name": "Jaipur"}],
            "budget": 9000,
            "duration": 3,
            "travelers": 1,
            "style": "standard",
            "traveler_type": "solo_male",
            "start_date": "2026-10-15",
            "interests": ["heritage"]
        }

    @patch("backend.services.gemini_service.requests.post")
    def test_generate_calls_gemini_api(self, mock_post, service, preferences):
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {
            "candidates": [{
                "content": {
                    "parts": [{"text": str(make_valid_itinerary()).replace("'", '"')}]
                }
            }]
        }
        service.generate_itinerary(preferences, destination_data=[])
        assert mock_post.called

    @patch("backend.services.gemini_service.requests.post")
    def test_generate_uses_correct_model(self, mock_post, service, preferences):
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {
            "candidates": [{"content": {"parts": [{"text": "{}"}]}}]
        }
        service.generate_itinerary(preferences, destination_data=[])
        call_url = mock_post.call_args[0][0]
        assert "gemini-2.0-flash" in call_url

    @patch("backend.services.gemini_service.requests.post")
    def test_generate_retries_on_500(self, mock_post, service, preferences):
        """Should retry on server error and eventually fallback."""
        mock_post.return_value.status_code = 500
        mock_post.return_value.json.return_value = {"error": "Server error"}
        try:
            service.generate_itinerary(preferences, destination_data=[])
        except Exception:
            pass
        assert mock_post.call_count >= 2  # retried at least once

    @patch("backend.services.gemini_service.requests.post")
    def test_generate_includes_budget_in_prompt(self, mock_post, service, preferences):
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {
            "candidates": [{"content": {"parts": [{"text": "{}"}]}}]
        }
        service.generate_itinerary(preferences, destination_data=[])
        request_body = mock_post.call_args[1].get("json") or mock_post.call_args[0][1]
        prompt_text = str(request_body)
        assert "9000" in prompt_text or "budget" in prompt_text.lower()

    @patch("backend.services.gemini_service.requests.post")
    def test_generate_includes_traveler_type_in_prompt(self, mock_post, service, preferences):
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {
            "candidates": [{"content": {"parts": [{"text": "{}"}]}}]
        }
        service.generate_itinerary(preferences, destination_data=[])
        request_body = mock_post.call_args[1].get("json") or mock_post.call_args[0][1]
        prompt_text = str(request_body)
        assert "solo_male" in prompt_text or "solo male" in prompt_text.lower()

    def test_prompt_forbids_modifying_costs(self, service, preferences):
        """The generated prompt must contain the cost-lock instruction."""
        prompt = service.build_prompt(preferences, destination_data=[])
        assert "NEVER" in prompt.upper() or "do not modify" in prompt.lower() or "locked" in prompt.lower()

    @patch("backend.services.gemini_service.requests.post")
    def test_chat_returns_reply(self, mock_post, service):
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {
            "candidates": [{"content": {"parts": [{"text": "Jaipur is best in October."}]}}]
        }
        result = service.chat_with_data("When is the best time to visit Jaipur?", context=[])
        assert "reply" in result
        assert len(result["reply"]) > 0

    @patch("backend.services.gemini_service.requests.post")
    def test_fallback_to_lite_model_on_overload(self, mock_post, service, preferences):
        """If flash is overloaded (429), fall back to flash-lite."""
        responses = [
            MagicMock(status_code=429, json=MagicMock(return_value={"error": "overloaded"})),
            MagicMock(status_code=200, json=MagicMock(return_value={
                "candidates": [{"content": {"parts": [{"text": "{}"}]}}]
            })),
        ]
        mock_post.side_effect = responses
        try:
            service.generate_itinerary(preferences, destination_data=[])
        except Exception:
            pass
        assert mock_post.call_count >= 2
        fallback_url = mock_post.call_args_list[-1][0][0]
        assert "flash-lite" in fallback_url or "flash" in fallback_url


# ─────────────────────────────────────────────────────
# Image Service
# ─────────────────────────────────────────────────────
class TestImageService:

    @pytest.fixture
    def service(self):
        from backend.services.image_service import ImageService
        return ImageService()

    @patch("backend.services.image_service.requests.get")
    def test_wikipedia_image_fetched_first(self, mock_get, service):
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {
            "thumbnail": {"source": "https://upload.wikimedia.org/amber.jpg", "width": 1200, "height": 800}
        }
        result = service.get_image("Amber Fort", category="fort")
        assert result is not None
        assert "wikipedia" in result.lower() or "wikimedia" in result.lower() or "upload" in result.lower()

    @patch("backend.services.image_service.requests.get")
    def test_falls_back_to_pexels_when_wikipedia_fails(self, mock_get, service):
        # Wikipedia returns empty
        wiki_response = MagicMock(status_code=404)
        pexels_response = MagicMock(status_code=200)
        pexels_response.json.return_value = {
            "photos": [{"src": {"large": "https://images.pexels.com/amber.jpg"}}]
        }
        mock_get.side_effect = [wiki_response, pexels_response]
        result = service.get_image("Amber Fort", category="fort")
        assert result is not None

    def test_svg_placeholder_returned_as_final_fallback(self, service):
        """If all sources fail, an SVG placeholder should be returned."""
        with patch.object(service, "get_image_from_wikipedia", return_value=None), \
             patch.object(service, "get_image_from_wikidata", return_value=None), \
             patch.object(service, "get_image_from_pexels", return_value=None):
            result = service.get_image("UnknownPlace XYZ 12345", category="unknown")
            assert result is not None
            assert "svg" in result.lower() or result.startswith("data:")

    def test_image_resolution_rejected_below_threshold(self, service):
        with patch.object(service, "_fetch_image_dimensions", return_value=(400, 300)):
            result = service.is_image_acceptable("https://example.com/small.jpg")
            assert result is False

    def test_image_resolution_accepted_above_threshold(self, service):
        with patch.object(service, "_fetch_image_dimensions", return_value=(1200, 800)):
            result = service.is_image_acceptable("https://example.com/hd.jpg")
            assert result is True
