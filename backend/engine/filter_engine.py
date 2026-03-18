import logging
import json
from typing import Any

from backend.constants import (
    POPULARITY_HARD_FLOOR,
    POPULARITY_SOFT_FLOOR,
    SEASONAL_SCORE_DEFAULT,
    SEASONAL_SCORE_GATE,
    BUDGET_ENTRY_COST_MULTIPLIERS,
    INTERESTS_CATEGORY_MULTIPLIER,
)

log = logging.getLogger(__name__)


def _composite_score(attr) -> float:
    """
    Blended quality score for sorting: popularity (primary) + Google rating
    (normalised to 0-100, 20% blend) minus skip-rate penalty.

    Falls back gracefully when fields are absent so all existing fixtures work.
    """
    pop = float(getattr(attr, "popularity_score", 50) or 50)
    google_r = getattr(attr, "google_rating", None)
    skip_r = float(getattr(attr, "user_skip_rate", 0) or 0)

    score = pop
    if google_r is not None:
        # Normalise Google 1-5 → 0-100; blend at 20 % weight.
        score = score * 0.80 + (float(google_r) / 5.0 * 100.0) * 0.20

    # High skip-rate is a strong negative signal: subtract up to 50 points at 100 % skip.
    score -= skip_r * 50.0
    return score


class FilterEngine:
    def filter(self, attractions: list, preferences: dict, num_days: int = 1) -> list:
        """
        Filters a list of attraction objects based on user preferences.
        All filters are AND conditions — attraction must pass all of them.

        Category cap scales with num_days so longer trips aren't starved
        of attraction variety (e.g. Rajasthan trips with many forts/temples).

        Interest-matching and memory-preferred types get INTERESTS_CATEGORY_MULTIPLIER×
        the base category cap so the traveler's stated preferences dominate.

        Attraction types that appear in excluded_types (learned from user signals)
        are hard-filtered out.

        If the hard popularity floor produces fewer results than needed for a
        reasonable itinerary, retries with a soft floor.
        """
        result = self._run_filter(attractions, preferences, num_days, floor=POPULARITY_HARD_FLOOR)

        # Adaptive floor: widen the gate so the pipeline doesn't produce an empty itinerary.
        if len(result) == 0 and attractions:
            log.warning(
                f"FilterEngine: 0 attractions passed hard floor (HARD_FLOOR={POPULARITY_HARD_FLOOR}). "
                f"Retrying with soft floor={POPULARITY_SOFT_FLOOR}."
            )
            result = self._run_filter(attractions, preferences, num_days, floor=POPULARITY_SOFT_FLOOR)

        return result

    def _run_filter(self, attractions: list, preferences: dict, num_days: int, floor: float) -> list:
        budget_tier: str = preferences.get("budget_tier", "mid")
        traveler_type: str = preferences.get("traveler_type", "couple")
        travel_month: str = preferences.get("travel_month", "any")
        daily_activity_budget: float = preferences.get("daily_activity_budget", 5000)

        # Interests: user-declared list of topics ("history", "food", "beaches", etc.)
        raw_interests: list = preferences.get("interests", []) or []
        interests_set: set[str] = {i.lower() for i in raw_interests if i}

        # Memory-learned types from AttractionSignal behavioral data (injected by MemoryAgent)
        preferred_types: set[str] = {
            t.lower() for t in (preferences.get("preferred_attraction_types") or [])
        }
        excluded_types: set[str] = {
            t.lower() for t in (preferences.get("excluded_types") or [])
        }

        # Dietary restrictions — filter food-type attractions that can't accommodate the diet.
        # Only food/restaurant/cafe attractions with a non-empty dietary_options list are
        # checked; all others pass through (dietary_options=[] means "unknown, allow").
        _food_types = frozenset({"restaurant", "cafe", "food", "culinary", "dining"})
        raw_diet: list = preferences.get("dietary_restrictions", []) or []
        diet_required: set[str] = {d.lower() for d in raw_diet if d}

        # Combined boost set: explicit interests + memory-learned preferred types
        boosted_types: set[str] = interests_set | preferred_types

        # Category cap scales with trip length so variety is preserved across many days.
        # A 1-day trip allows 2 of any type; a 7-day trip allows up to 14.
        category_cap: int = max(2, num_days * 2)

        # Graduated entry-cost multiplier — budget travelers are capped strictly,
        # mid-range travelers can afford attractions up to 3× their daily budget,
        # luxury travelers have no cap.
        entry_cost_multiplier: float | None = BUDGET_ENTRY_COST_MULTIPLIERS.get(budget_tier)

        filtered: list = []
        category_counts: dict[str, int] = {}

        # Sort descending by composite score so best attractions take priority against the cap.
        # Composite score = popularity + google_rating blend − skip_rate penalty.
        sorted_attractions = sorted(
            attractions,
            key=_composite_score,
            reverse=True,
        )

        for attr in sorted_attractions:
            # 1. Popularity floor
            pop_score: float = float(getattr(attr, "popularity_score", 0) or 0)
            if pop_score < floor:
                continue

            # 2. Traveler compatibility
            compat: Any = getattr(attr, "compatible_traveler_types", [])
            if isinstance(compat, str):
                try:
                    compat = json.loads(compat)
                except Exception:
                    compat = []

            if compat and traveler_type not in compat:
                continue

            # 3. Seasonal gate
            seasonal_scores: dict = getattr(attr, "seasonal_score", {}) or {}
            if travel_month != "any":
                s_score: int = seasonal_scores.get(travel_month, SEASONAL_SCORE_DEFAULT)
                s_score = s_score or 0
                if s_score < SEASONAL_SCORE_GATE:
                    continue

            # 4. Graduated budget entry-cost filter.
            # budget tier:  entry_cost_max must not exceed 1× daily_activity_budget
            # mid tier:     entry_cost_max must not exceed 3× daily_activity_budget
            # luxury tier:  no cap (entry_cost_multiplier is None)
            if entry_cost_multiplier is not None:
                cost_max: int = getattr(attr, "entry_cost_max", 0) or 0
                if cost_max > daily_activity_budget * entry_cost_multiplier:
                    continue

            # 5. Memory-learned excluded types: hard-block types the user historically dislikes.
            attr_type: str = (getattr(attr, "type", "general") or "general").lower()
            if excluded_types and attr_type in excluded_types:
                continue

            # 6a. Accessibility filter — if user needs accessible attractions
            # (accessibility=1), skip attractions explicitly marked not accessible.
            required_accessibility: int = preferences.get("accessibility", 0) or 0
            if required_accessibility == 1:
                attr_access = getattr(attr, "accessibility_level", 0) or 0
                if attr_access == 3:  # explicitly not accessible
                    continue

            # 6b. Children-friendly filter — if group has children, skip attractions
            # that lack "family" in compatible_traveler_types (if it has any types at all).
            children_count: int = preferences.get("children_count", 0) or 0
            if children_count > 0:
                if compat and "family" not in compat and "couple" not in compat:
                    continue

            # 6c. Dietary restrictions — only applies to food-type venues that have
            # explicit dietary_options populated.  If the venue's options don't
            # include any of the traveler's required diets, skip it.
            if diet_required and attr_type in _food_types:
                venue_diets: list = getattr(attr, "dietary_options", None) or []
                if venue_diets:  # non-empty means the venue explicitly lists its options
                    venue_diets_set = {d.lower() for d in venue_diets}
                    if not diet_required.intersection(venue_diets_set):
                        continue

            # 6d. Senior-friendly filter — if the group has seniors, skip strenuous
            # activities.  "moderate" is allowed since most seniors can manage with
            # short breaks; "strenuous" (steep hikes, adventure sports) is blocked.
            senior_count: int = preferences.get("senior_count", 0) or 0
            if senior_count > 0:
                attr_difficulty: str = (getattr(attr, "difficulty_level", "easy") or "easy").lower()
                if attr_difficulty == "strenuous":
                    continue

            # 6e. Minimum age filter — skip attractions with an age requirement that
            # would exclude the youngest children in the group.
            children_min_age: int = preferences.get("children_min_age", 0) or 0
            if children_min_age > 0:
                attr_min_age = getattr(attr, "min_age", None)
                if attr_min_age and attr_min_age > children_min_age:
                    continue

            # 6. Category cap — scaled by num_days.
            # Boosted types (declared interests + memory-preferred) get
            # INTERESTS_CATEGORY_MULTIPLIER× the base cap so traveler preferences
            # are well-represented in the output.
            count: int = category_counts.get(attr_type, 0)

            type_is_boosted = bool(boosted_types) and any(
                boost in attr_type or attr_type in boost
                for boost in boosted_types
            )
            effective_cap = (
                category_cap * INTERESTS_CATEGORY_MULTIPLIER
                if type_is_boosted
                else category_cap
            )

            if count >= effective_cap:
                continue

            category_counts[attr_type] = count + 1
            filtered.append(attr)

        return filtered
