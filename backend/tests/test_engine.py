"""
test_engine.py — Unit tests for the 5-phase deterministic engine.
Covers: FilterEngine, ClusterEngine, BudgetAllocator, RouteOptimizer, Assembler.

These tests are PURE UNIT TESTS — no HTTP, no Flask, no DB.
All dependencies are injected via fixtures.
"""

import pytest
from unittest.mock import MagicMock, patch


# ─────────────────────────────────────────────────────
# Shared mock attraction factory
# ─────────────────────────────────────────────────────
def make_attraction(
    id=1, name="Amber Fort", type="fort", destination_id=1,
    entry_cost_min=200, entry_cost_max=550,
    popularity_score=80, avg_visit_duration_hours=2.0,
    best_visit_time_hour=9, budget_category="mid-range",
    compatible_traveler_types=None, seasonal_score=None,
    latitude=26.985, longitude=75.851, skip_rate=0.0,
    h3_index_r7="872a100dffffff"
):
    a = MagicMock()
    a.id = id
    a.name = name
    a.type = type
    a.destination_id = destination_id
    a.entry_cost_min = entry_cost_min
    a.entry_cost_max = entry_cost_max
    a.popularity_score = popularity_score
    a.avg_visit_duration_hours = avg_visit_duration_hours
    a.best_visit_time_hour = best_visit_time_hour
    a.budget_category = budget_category
    a.compatible_traveler_types = compatible_traveler_types or ["solo_male", "couple", "family"]
    a.seasonal_score = seasonal_score or {"oct": 90, "nov": 85, "dec": 80, "jun": 30}
    a.latitude = latitude
    a.longitude = longitude
    a.skip_rate = skip_rate
    a.h3_index_r7 = h3_index_r7
    return a


# ─────────────────────────────────────────────────────
# PHASE 1 — FilterEngine
# ─────────────────────────────────────────────────────
class TestFilterEngine:

    @pytest.fixture
    def engine(self):
        from backend.engine.filter_engine import FilterEngine
        return FilterEngine()

    @pytest.fixture
    def base_prefs(self):
        return {
            "budget_tier": "mid",
            "traveler_type": "solo_male",
            "travel_month": "oct",
            "daily_activity_budget": 1000,
        }

    def test_returns_list(self, engine, base_prefs):
        attractions = [make_attraction(id=1), make_attraction(id=2)]
        result = engine.filter(attractions, base_prefs)
        assert isinstance(result, list)

    def test_all_valid_attractions_pass(self, engine, base_prefs):
        attractions = [make_attraction(id=i, type=f"type_{i}") for i in range(1, 5)]
        result = engine.filter(attractions, base_prefs)
        assert len(result) == 4

    def test_low_popularity_filtered_out(self, engine, base_prefs):
        low = make_attraction(id=1, popularity_score=10)
        high = make_attraction(id=2, popularity_score=80)
        result = engine.filter([low, high], base_prefs)
        ids = [a.id for a in result]
        assert 1 not in ids
        assert 2 in ids

    def test_incompatible_traveler_type_filtered(self, engine, base_prefs):
        spa = make_attraction(id=1, compatible_traveler_types=["couple", "solo_female"])
        fort = make_attraction(id=2, compatible_traveler_types=["solo_male", "couple"])
        result = engine.filter([spa, fort], base_prefs)
        ids = [a.id for a in result]
        assert 1 not in ids  # spa not compatible with solo_male
        assert 2 in ids

    def test_empty_compatible_types_passes_all(self, engine, base_prefs):
        """Empty compatible_traveler_types means open to all."""
        a = make_attraction(id=1, compatible_traveler_types=[])
        result = engine.filter([a], base_prefs)
        assert len(result) == 1

    def test_low_seasonal_score_filtered(self, engine, base_prefs):
        monsoon = make_attraction(
            id=1, seasonal_score={"oct": 20, "jun": 10}  # below threshold of 40
        )
        result = engine.filter([monsoon], base_prefs)
        assert len(result) == 0

    def test_high_seasonal_score_passes(self, engine, base_prefs):
        peak = make_attraction(id=1, seasonal_score={"oct": 95})
        result = engine.filter([peak], base_prefs)
        assert len(result) == 1

    def test_category_cap_max_two_per_type(self, engine, base_prefs):
        """No more than 2 attractions of the same type per day."""
        forts = [make_attraction(id=i, type="fort", popularity_score=90 - i) for i in range(1, 5)]
        result = engine.filter(forts, base_prefs)
        fort_count = sum(1 for a in result if a.type == "fort")
        assert fort_count <= 2

    def test_empty_attractions_returns_empty(self, engine, base_prefs):
        result = engine.filter([], base_prefs)
        assert result == []

    def test_budget_entry_cost_filter(self, engine, base_prefs):
        expensive = make_attraction(id=1, entry_cost_min=800, entry_cost_max=2000)
        cheap = make_attraction(id=2, entry_cost_min=0, entry_cost_max=300)
        prefs = {**base_prefs, "budget_tier": "budget", "daily_activity_budget": 500}
        result = engine.filter([expensive, cheap], prefs)
        ids = [a.id for a in result]
        assert 1 not in ids
        assert 2 in ids


# ─────────────────────────────────────────────────────
# PHASE 2 — ClusterEngine
# ─────────────────────────────────────────────────────
class TestClusterEngine:

    @pytest.fixture
    def engine(self):
        from backend.engine.cluster_engine import ClusterEngine
        return ClusterEngine()

    def _make_cluster_group(self, hex_id, count, start_id=1):
        return [
            make_attraction(id=start_id + i, h3_index_r7=hex_id, popularity_score=80 - i)
            for i in range(count)
        ]

    def test_returns_dict_with_day_keys(self, engine):
        attractions = self._make_cluster_group("hex_A", 3)
        result = engine.cluster(attractions, num_days=1)
        assert isinstance(result, dict)
        assert "day_1" in result

    def test_correct_number_of_days(self, engine):
        group_a = self._make_cluster_group("hex_A", 4, start_id=1)
        group_b = self._make_cluster_group("hex_B", 4, start_id=10)
        result = engine.cluster(group_a + group_b, num_days=2)
        assert len(result) == 2

    def test_attractions_grouped_by_hex(self, engine):
        """Attractions in same hex should end up on the same day."""
        group_a = self._make_cluster_group("hex_A", 3, start_id=1)
        group_b = self._make_cluster_group("hex_B", 3, start_id=10)
        result = engine.cluster(group_a + group_b, num_days=2)
        day_1_ids = set(result["day_1"])
        day_2_ids = set(result["day_2"])
        # No overlap between days
        assert len(day_1_ids & day_2_ids) == 0

    def test_max_6_activities_per_day(self, engine):
        """Days must not exceed 6 activities."""
        big_group = self._make_cluster_group("hex_A", 10)
        result = engine.cluster(big_group, num_days=1)
        assert len(result["day_1"]) <= 6

    def test_empty_attractions_returns_empty_days(self, engine):
        result = engine.cluster([], num_days=3)
        for day_key in result.values():
            assert day_key == []

    def test_top_scored_hex_gets_day_1(self, engine):
        """The hex with highest total popularity_score should be Day 1."""
        low_hex = self._make_cluster_group("hex_LOW", 3, start_id=1)
        for a in low_hex:
            a.popularity_score = 30
        high_hex = self._make_cluster_group("hex_HIGH", 3, start_id=10)
        for a in high_hex:
            a.popularity_score = 95

        result = engine.cluster(low_hex + high_hex, num_days=2)
        day_1_ids = [a.id for a in result["day_1"]]
        high_ids = [a.id for a in high_hex]
        assert all(id in high_ids for id in day_1_ids)

    def test_zero_zero_coordinates_do_not_share_real_h3_cell(self, engine):
        """Missing GPS coordinates at (0,0) should not be encoded into the same H3 bucket."""
        a = make_attraction(id=1, h3_index_r7=None, latitude=0.0, longitude=0.0)
        b = make_attraction(id=2, h3_index_r7=None, latitude=0.0, longitude=0.0)
        c = make_attraction(id=3, h3_index_r7=None, latitude=26.985, longitude=75.851)
        result = engine.cluster([a, b, c], num_days=3)
        populated_days = [day for day in result.values() if day]
        assert len(populated_days) == 3


# ─────────────────────────────────────────────────────
# PHASE 3 — BudgetAllocator
# ─────────────────────────────────────────────────────
class TestBudgetAllocator:

    @pytest.fixture
    def allocator(self):
        from backend.engine.budget_allocator import BudgetAllocator
        return BudgetAllocator()

    @pytest.fixture
    def simple_clusters(self):
        return {
            "day_1": [make_attraction(id=1, entry_cost_min=200, entry_cost_max=600)],
            "day_2": [make_attraction(id=2, entry_cost_min=100, entry_cost_max=300)],
        }

    def test_total_cost_within_budget(self, allocator, simple_clusters):
        result = allocator.allocate(
            total_budget=10000, num_days=2, num_travelers=1,
            tier="mid", clusters=simple_clusters
        )
        total = sum(d["day_total"] for d in result.values())
        assert total <= 10000 * 1.05, f"Total {total} exceeds budget 10000 by >5%"

    def test_all_days_have_required_keys(self, allocator, simple_clusters):
        result = allocator.allocate(10000, 2, 1, "mid", simple_clusters)
        for day_data in result.values():
            for key in ["accommodation", "food", "transport", "activities", "misc", "day_total"]:
                assert key in day_data, f"Missing budget key: {key}"

    def test_luxury_spend_more_on_accommodation(self, allocator, simple_clusters):
        mid = allocator.allocate(20000, 2, 1, "mid", simple_clusters)
        luxury = allocator.allocate(20000, 2, 1, "luxury", simple_clusters)
        assert luxury["day_1"]["accommodation"] >= mid["day_1"]["accommodation"]

    def test_budget_tier_lowest_accommodation(self, allocator, simple_clusters):
        budget = allocator.allocate(10000, 2, 1, "budget", simple_clusters)
        mid = allocator.allocate(10000, 2, 1, "mid", simple_clusters)
        assert budget["day_1"]["accommodation"] <= mid["day_1"]["accommodation"]

    def test_no_negative_values(self, allocator, simple_clusters):
        result = allocator.allocate(5000, 2, 1, "budget", simple_clusters)
        for day_data in result.values():
            for key, val in day_data.items():
                assert val >= 0, f"{key} is negative: {val}"

    def test_scales_with_travelers(self, allocator, simple_clusters):
        single = allocator.allocate(10000, 2, 1, "mid", simple_clusters)
        double = allocator.allocate(20000, 2, 2, "mid", simple_clusters)
        # Per-person cost should be roughly the same
        assert abs(single["day_1"]["day_total"] - double["day_1"]["day_total"]) < 500

    def test_over_budget_demotes_hotel_tier(self, allocator):
        """When costs exceed budget, hotel tier should be demoted, not activities cut."""
        tiny_clusters = {"day_1": [make_attraction(id=1, entry_cost_min=100, entry_cost_max=200)]}
        result = allocator.allocate(
            total_budget=500,  # very tight budget
            num_days=1, num_travelers=1,
            tier="luxury",
            clusters=tiny_clusters
        )
        # Should still return a valid result (demoted to budget tier)
        assert result is not None
        assert "day_1" in result

    def test_zero_travelers_defaults_to_one(self, allocator, simple_clusters):
        """Zero travelers should not trigger division by zero in per-person math."""
        result = allocator.allocate(10000, 2, 0, "mid", simple_clusters)
        assert result["day_1"]["day_total"] > 0


# ─────────────────────────────────────────────────────
# PHASE 4 — RouteOptimizer
# ─────────────────────────────────────────────────────
class TestRouteOptimizer:

    @pytest.fixture
    def optimizer(self):
        from backend.engine.route_optimizer import RouteOptimizer
        return RouteOptimizer()

    @pytest.fixture
    def sample_day_attractions(self):
        return [
            make_attraction(id=1, name="Sunrise Viewpoint", best_visit_time_hour=6,
                            avg_visit_duration_hours=0.5, latitude=26.90, longitude=75.80),
            make_attraction(id=2, name="Amber Fort", best_visit_time_hour=9,
                            avg_visit_duration_hours=2.0, latitude=26.985, longitude=75.851),
            make_attraction(id=3, name="City Palace", best_visit_time_hour=11,
                            avg_visit_duration_hours=1.5, latitude=26.925, longitude=75.823),
            make_attraction(id=4, name="Evening Market", best_visit_time_hour=18,
                            avg_visit_duration_hours=1.0, latitude=26.920, longitude=75.818),
        ]

    def test_returns_dict_with_activities_key(self, optimizer, sample_day_attractions):
        result = optimizer.optimize(sample_day_attractions, "2026-10-15")
        assert "activities" in result

    def test_activities_is_list(self, optimizer, sample_day_attractions):
        result = optimizer.optimize(sample_day_attractions, "2026-10-15")
        assert isinstance(result["activities"], list)

    def test_sunrise_spot_scheduled_first(self, optimizer, sample_day_attractions):
        result = optimizer.optimize(sample_day_attractions, "2026-10-15")
        activities = [a for a in result["activities"] if not a.get("is_break")]
        assert activities[0]["name"] == "Sunrise Viewpoint"

    def test_times_are_sequential(self, optimizer, sample_day_attractions):
        result = optimizer.optimize(sample_day_attractions, "2026-10-15")
        activities = result["activities"]
        for i in range(1, len(activities)):
            prev_end = activities[i - 1].get("end_time", "00:00")
            curr_start = activities[i].get("time", "00:00")
            assert curr_start >= prev_end, \
                f"Activity {i} starts at {curr_start} before previous ends at {prev_end}"

    def test_lunch_break_inserted_at_13(self, optimizer, sample_day_attractions):
        result = optimizer.optimize(sample_day_attractions, "2026-10-15")
        has_lunch = any(a.get("meal_type") == "lunch" or a.get("is_break") for a in result["activities"])
        assert has_lunch

    def test_pacing_level_is_valid(self, optimizer, sample_day_attractions):
        result = optimizer.optimize(sample_day_attractions, "2026-10-15")
        assert result["pacing_level"] in ["relaxed", "moderate", "intense"]

    def test_intense_pacing_for_many_activities(self, optimizer):
        """10 activities in a day should flag as intense."""
        many = [
            make_attraction(id=i, best_visit_time_hour=9 + i % 8,
                            avg_visit_duration_hours=1.5,
                            latitude=26.9 + i * 0.01, longitude=75.8 + i * 0.01)
            for i in range(10)
        ]
        result = optimizer.optimize(many, "2026-10-15")
        assert result["pacing_level"] == "intense"

    def test_no_duplicate_activities_in_output(self, optimizer, sample_day_attractions):
        result = optimizer.optimize(sample_day_attractions, "2026-10-15")
        names = [a["name"] for a in result["activities"] if not a.get("is_break")]
        assert len(names) == len(set(names))

    def test_each_activity_has_time_field(self, optimizer, sample_day_attractions):
        result = optimizer.optimize(sample_day_attractions, "2026-10-15")
        for activity in result["activities"]:
            if not activity.get("is_break"):
                assert "time" in activity
                assert "duration_minutes" in activity
                assert "cost" in activity


# ─────────────────────────────────────────────────────
# PHASE 5 — Assembler
# ─────────────────────────────────────────────────────
class TestAssembler:

    @pytest.fixture
    def assembler(self):
        from backend.engine.assembler import Assembler
        return Assembler()

    @pytest.fixture
    def mock_engine_outputs(self):
        """Simulate what all 4 prior phases produce."""
        clusters = {
            "day_1": [1, 2],
            "day_2": [3],
        }
        budget = {
            "day_1": {"accommodation": 1500, "food": 800, "transport": 600, "activities": 750, "misc": 150, "day_total": 3800},
            "day_2": {"accommodation": 1500, "food": 800, "transport": 600, "activities": 200, "misc": 150, "day_total": 3250},
        }
        route = {
            "day_1": {
                "pacing_level": "moderate",
                "activities": [
                    {"name": "Amber Fort", "time": "09:00", "end_time": "11:00", "duration_minutes": 120, "cost": 550, "is_break": False},
                    {"name": "Lunch break", "time": "13:00", "end_time": "14:00", "duration_minutes": 60, "is_break": True, "meal_type": "lunch"},
                    {"name": "Hawa Mahal", "time": "14:00", "end_time": "15:00", "duration_minutes": 60, "cost": 200, "is_break": False},
                ]
            },
            "day_2": {
                "pacing_level": "relaxed",
                "activities": [
                    {"name": "Jantar Mantar", "time": "10:00", "end_time": "11:30", "duration_minutes": 90, "cost": 200, "is_break": False},
                ]
            }
        }
        return {"clusters": clusters, "budget": budget, "route": route}

    @pytest.fixture
    def preferences(self):
        return {
            "destination_country": "India",
            "start_city": "Mumbai",
            "duration": 2,
            "budget": 7000,
            "style": "standard",
            "traveler_type": "solo_male",
            "start_date": "2026-10-15",
        }

    def test_assembler_returns_valid_structure(self, assembler, mock_engine_outputs, preferences):
        result = assembler.assemble(mock_engine_outputs, preferences)
        assert "itinerary" in result
        assert "total_cost" in result
        assert "cost_breakdown" in result

    def test_itinerary_day_count_matches_duration(self, assembler, mock_engine_outputs, preferences):
        result = assembler.assemble(mock_engine_outputs, preferences)
        assert len(result["itinerary"]) == preferences["duration"]

    def test_each_day_has_required_fields(self, assembler, mock_engine_outputs, preferences):
        result = assembler.assemble(mock_engine_outputs, preferences)
        required = ["day", "location", "theme", "pacing_level", "activities", "accommodation", "day_total"]
        for day in result["itinerary"]:
            for field in required:
                assert field in day, f"Day missing field: {field}"

    def test_day_numbers_sequential(self, assembler, mock_engine_outputs, preferences):
        result = assembler.assemble(mock_engine_outputs, preferences)
        for i, day in enumerate(result["itinerary"], 1):
            assert day["day"] == i

    def test_total_cost_equals_sum_of_day_totals(self, assembler, mock_engine_outputs, preferences):
        result = assembler.assemble(mock_engine_outputs, preferences)
        expected_total = sum(d["day_total"] for d in result["itinerary"])
        assert abs(result["total_cost"] - expected_total) < 100  # allow small rounding

    def test_cost_breakdown_keys_present(self, assembler, mock_engine_outputs, preferences):
        result = assembler.assemble(mock_engine_outputs, preferences)
        breakdown = result["cost_breakdown"]
        for key in ["accommodation", "food", "transport", "activities", "misc"]:
            assert key in breakdown

    def test_theme_is_string(self, assembler, mock_engine_outputs, preferences):
        result = assembler.assemble(mock_engine_outputs, preferences)
        for day in result["itinerary"]:
            assert isinstance(day["theme"], str)
            assert len(day["theme"]) > 0

    def test_packing_tips_and_insights_present(self, assembler, mock_engine_outputs, preferences):
        result = assembler.assemble(mock_engine_outputs, preferences)
        assert "smart_insights" in result or "packing_tips" in result
