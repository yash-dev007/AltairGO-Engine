"""
validation.py — Itinerary validation engine.
Validates Gemini-generated itineraries for structural correctness,
budget compliance, generic name detection, and activity packing.
"""

import copy
import math

# Names considered too generic for a real itinerary
GENERIC_ACTIVITY_NAMES = {
    "local market", "beach", "restaurant", "park", "temple",
    "historical site", "museum", "viewpoint", "shopping",
    "sightseeing", "lake", "garden", "fort", "palace",
    "church", "mosque", "hill", "river", "waterfall",
}

REQUIRED_TOP_KEYS = ["trip_title", "total_cost", "itinerary"]
MAX_ACTIVITIES_PER_DAY = 5
BUDGET_TOLERANCE = 0.05  # 5%
DAY_TOTAL_TOLERANCE = 0.15  # 15%


class ItineraryValidator:
    """Validates and optionally auto-corrects itineraries returned by Gemini."""

    def __init__(self, strict=False):
        self.strict = strict

    def validate(self, data: dict, user_budget: float) -> dict:
        errors = []
        warnings = []

        # 1. Required top-level keys
        for key in REQUIRED_TOP_KEYS:
            if key not in data:
                errors.append(f"Missing required key: '{key}'")

        if errors:
            return {"valid": False, "errors": errors, "warnings": warnings}

        # Empty itinerary
        if not data["itinerary"]:
            errors.append("Itinerary is empty (no days).")
            return {"valid": False, "errors": errors, "warnings": warnings}

        total_cost = data["total_cost"]

        # 2. Budget check
        corrected = None
        if total_cost > user_budget * (1 + BUDGET_TOLERANCE):
            if self.strict:
                scale = user_budget / total_cost
                corrected = self._auto_scale(data, scale)
                warnings.append(
                    f"total_cost {total_cost} exceeds budget {user_budget} by "
                    f"{((total_cost / user_budget) - 1) * 100:.1f}%. Auto-scaled."
                )
            else:
                errors.append(
                    f"total_cost {total_cost} exceeds budget {user_budget}."
                )

        # 3. Day-total consistency
        day_totals_sum = sum(d.get("day_total", 0) for d in data["itinerary"])
        if total_cost > 0:
            ratio = day_totals_sum / total_cost
            if abs(ratio - 1.0) > DAY_TOTAL_TOLERANCE:
                warnings.append(
                    f"Sum of day_totals ({day_totals_sum}) differs from "
                    f"total_cost ({total_cost}) by {abs(ratio - 1) * 100:.0f}%."
                )
                if self.strict and abs(ratio - 1.0) > DAY_TOTAL_TOLERANCE:
                    errors.append(
                        f"Day totals inconsistency: sum={day_totals_sum}, "
                        f"total_cost={total_cost}"
                    )

        # 4. Generic activity name detection
        for day in data["itinerary"]:
            for act in day.get("activities", []):
                name = act.get("activity", "")
                if name.lower().strip() in GENERIC_ACTIVITY_NAMES:
                    warnings.append(
                        f"Day {day.get('day')}: '{name}' is a generic name. "
                        "Use a specific place name."
                    )
                    if self.strict:
                        errors.append(f"Generic activity name: '{name}'")

        # 5. Over-packed day check
        for day in data["itinerary"]:
            act_count = len(day.get("activities", []))
            if act_count > MAX_ACTIVITIES_PER_DAY:
                warnings.append(
                    f"Day {day.get('day')}: {act_count} activities is overpacked "
                    f"(max recommended: {MAX_ACTIVITIES_PER_DAY})."
                )

        # 6. Geo-distance check — flag impossible routes (>100km between consecutive activities)
        for day in data["itinerary"]:
            activities = [a for a in day.get("activities", []) if not a.get("is_break")]
            for i in range(1, len(activities)):
                prev = activities[i - 1]
                curr = activities[i]
                lat1 = prev.get("latitude")
                lon1 = prev.get("longitude")
                lat2 = curr.get("latitude")
                lon2 = curr.get("longitude")
                if lat1 and lon1 and lat2 and lon2:
                    dist = self._haversine_km(lat1, lon1, lat2, lon2)
                    if dist > 100:
                        warnings.append(
                            f"Day {day.get('day')}: '{prev.get('name', '?')}' → "
                            f"'{curr.get('name', '?')}' is {dist:.0f}km apart — "
                            f"possibly impossible same-day route."
                        )

        # 7. Time-logic check — flag activities at unreasonable hours
        for day in data["itinerary"]:
            for act in day.get("activities", []):
                time_str = act.get("time", "")
                if time_str:
                    try:
                        hour = int(time_str.split(":")[0])
                        if hour >= 23 or hour < 5:
                            warnings.append(
                                f"Day {day.get('day')}: '{act.get('name', '?')}' "
                                f"scheduled at {time_str} — unreasonable hour."
                            )
                    except (ValueError, IndexError):
                        pass

        valid = len(errors) == 0
        result = {"valid": valid, "errors": errors, "warnings": warnings}
        if corrected is not None:
            result["corrected"] = corrected
        return result

    # ── Private helpers ──────────────────────────────────────────

    @staticmethod
    def _auto_scale(data: dict, scale: float) -> dict:
        """Scale all costs down proportionally."""
        corrected = copy.deepcopy(data)
        corrected["total_cost"] = int(corrected["total_cost"] * scale)

        if "cost_breakdown" in corrected:
            for k in corrected["cost_breakdown"]:
                corrected["cost_breakdown"][k] = int(
                    corrected["cost_breakdown"][k] * scale
                )

        for day in corrected.get("itinerary", []):
            day["day_total"] = int(day.get("day_total", 0) * scale)
            if "accommodation" in day and "cost_per_night" in day["accommodation"]:
                day["accommodation"]["cost_per_night"] = int(
                    day["accommodation"]["cost_per_night"] * scale
                )
            for act in day.get("activities", []):
                if "cost" in act:
                    act["cost"] = int(act["cost"] * scale)

        return corrected

    @staticmethod
    def _haversine_km(lat1, lon1, lat2, lon2) -> float:
        """Calculate the great-circle distance between two points (in km)."""
        R = 6371
        phi1, phi2 = math.radians(lat1), math.radians(lat2)
        dphi = math.radians(lat2 - lat1)
        dlambda = math.radians(lon2 - lon1)
        a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
        return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
