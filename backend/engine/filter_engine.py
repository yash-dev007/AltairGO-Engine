import logging
import json

log = logging.getLogger(__name__)

class FilterEngine:
    def filter(self, attractions: list, preferences: dict) -> list:
        """
        Filters a list of attraction objects based on user preferences.
        All filters are AND conditions — attraction must pass all of them.
        """
        budget_tier = preferences.get("budget_tier", "mid")
        traveler_type = preferences.get("traveler_type", "couple")
        travel_month = preferences.get("travel_month", "any")
        daily_activity_budget = preferences.get("daily_activity_budget", 5000)
        
        filtered = []
        category_counts = {}

        # 5. Category cap - requires processing in order of highest popularity first
        # Sort attractions descending by popularity score (default 0 if missing)
        sorted_attractions = sorted(
            attractions, 
            key=lambda a: getattr(a, 'popularity_score', 0) or 0, 
            reverse=True
        )

        for attr in sorted_attractions:
            # 1. Popularity floor
            # Defaults to 50 if missing entirely, but test cases inject specific scores
            # Coerce NULL score columns to zero so scoring math stays type-safe.
            pop_score = getattr(attr, 'popularity_score', 0) or 0
            if pop_score < 25:
                continue

            # 2. Traveler compatibility
            # Fix 10: JSON deserialization for traveler_type
            compat = getattr(attr, 'compatible_traveler_types', [])
            if isinstance(compat, str):
                try:
                    compat = json.loads(compat)
                except Exception:
                    compat = []
            
            if compat and traveler_type not in compat:
                continue


            # 3. Seasonal gate
            # Requires seasonal_score[travel_month] >= 40. Default 70 if month not there.
            seasonal_scores = getattr(attr, 'seasonal_score', {}) or {}
            if travel_month != "any":
                # Coerce NULL month scores to zero while preserving the default fallback of 70.
                s_score = seasonal_scores.get(travel_month, 70)
                s_score = s_score or 0
                if s_score < 40:
                    continue

            # 4. Budget entry cost
            # For "budget" tier, entry_cost_max must be <= daily_activity_budget
            if budget_tier == "budget":
                cost_max = getattr(attr, 'entry_cost_max', 0)
                if cost_max is not None and cost_max > daily_activity_budget:
                    continue

            # 5. Category cap
            # Max 2 attractions of same type per day/call
            attr_type = getattr(attr, 'type', 'general')
            count = category_counts.get(attr_type, 0)
            if count >= 2:
                continue
            
            # Passed all filters
            category_counts[attr_type] = count + 1
            filtered.append(attr)

        return filtered
