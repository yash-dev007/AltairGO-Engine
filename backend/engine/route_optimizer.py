import logging
import math
from datetime import datetime, timedelta
from typing import Any

from backend.constants import (
    AVG_URBAN_SPEED_KMH,
    DAY_START_HOUR,
    DAY_START_HOUR_ARRIVAL,
    SUNRISE_MAX_HOUR,
    MIN_TRAVEL_MINUTES,
)
from backend.utils.helpers import haversine_km

log = logging.getLogger(__name__)


def _reorder_for_connections(attractions: list) -> list:
    """
    Greedy reorder using connects_well_with to improve thematic flow.
    Starts from the first (westernmost) attraction and at each step prefers
    an attraction listed in the previous one's connects_well_with list.
    Falls back to next-in-list order when no connection exists.
    O(n²) but n ≤ 6 so this is negligible.
    """
    if len(attractions) <= 2:
        return attractions

    result = [attractions[0]]
    remaining = list(attractions[1:])

    while remaining:
        prev_connections = getattr(result[-1], "connects_well_with", None) or []
        prev_id = getattr(result[-1], "id", None)

        connected = [
            a for a in remaining
            if getattr(a, "id", None) in prev_connections
        ]
        next_attr = connected[0] if connected else remaining[0]
        result.append(next_attr)
        remaining.remove(next_attr)

    return result


class RouteOptimizer:
    AVG_URBAN_SPEED_KMH: int = AVG_URBAN_SPEED_KMH

    def optimize(
        self,
        day_attractions: list,
        start_date_str: str,
        day_type: str = "normal",
    ) -> dict:
        """
        Takes a list of attraction objects for a single day and schedules them.
        Returns a dictionary with 'pacing_level' and 'activities' list.

        day_type options:
          "normal"    — Full day (9am to evening). Breakfast inserted for non-sunrise days.
          "arrival"   — Traveler arrives midday. Afternoon activities only (3pm start).
                        Hotel check-in is prepended. Max 3 activities.
          "departure" — Traveler departs after checkout. Morning only (cap at noon).
                        Breakfast + checkout are inserted. Max 2 activities.

        Steps:
          1. Sunrise spots (best_visit_time_hour <= SUNRISE_MAX_HOUR) go first.
          2. Remaining attractions sorted west-to-east to minimise backtracking.
          3. day_type adjustments applied (filter/cap attractions + start hour).
          4. Breakfast inserted for normal/departure days without sunrise spots.
          5. Time slots assigned from the determined start hour.
          6. A lunch break is inserted once, the first time current hour >= 12.
          7. Departure day: schedule capped at noon, checkout entry appended.
          8. Dinner inserted if day runs past 19:00 (normal/arrival only).
          9. Pacing level derived from activity count and total hours.
        """
        if not day_attractions:
            return {"pacing_level": "relaxed", "activities": []}

        # Step 1: Force sunrise spots first
        sunrise = [
            a for a in day_attractions
            if (getattr(a, "best_visit_time_hour", 10) or 10) <= SUNRISE_MAX_HOUR
        ]
        others = [
            a for a in day_attractions
            if (getattr(a, "best_visit_time_hour", 10) or 10) > SUNRISE_MAX_HOUR
        ]

        # Step 2: Sort others west-to-east (minimise backtracking), then apply
        # connects_well_with reordering for better cultural/thematic flow.
        others_sorted = sorted(
            others,
            key=lambda a: getattr(a, "longitude", getattr(a, "lng", 0)) or 0,
        )
        others_sorted = _reorder_for_connections(others_sorted)

        # Step 3: day_type adjustments
        if day_type == "arrival":
            # Arrival day: afternoon only, max 3 activities, skip sunrise spots.
            # Prefer attractions whose best time is afternoon (≥ 12); fall back to any.
            afternoon = [
                a for a in others_sorted
                if (getattr(a, "best_visit_time_hour", 10) or 10) >= 12
            ] or others_sorted
            ordered = afternoon[:3]
            start_hour = DAY_START_HOUR_ARRIVAL
            sunrise_count = 0

        elif day_type == "departure":
            # Departure day: max 2 morning attractions.
            morning = sorted(
                sunrise + others_sorted,
                key=lambda a: getattr(a, "best_visit_time_hour", 10) or 10,
            )[:2]
            ordered = morning
            start_hour = DAY_START_HOUR
            sunrise_count = sum(
                1 for a in ordered
                if (getattr(a, "best_visit_time_hour", 10) or 10) <= SUNRISE_MAX_HOUR
            )

        else:
            # Normal day
            ordered = sunrise + others_sorted
            sunrise_count = len(sunrise)
            if sunrise and ordered:
                first_best_hour = (
                    getattr(ordered[0], "best_visit_time_hour", DAY_START_HOUR) or DAY_START_HOUR
                )
                start_hour = (
                    max(5, first_best_hour)
                    if first_best_hour <= SUNRISE_MAX_HOUR
                    else DAY_START_HOUR
                )
            else:
                start_hour = DAY_START_HOUR

        current_time = datetime.strptime(start_date_str, "%Y-%m-%d").replace(
            hour=start_hour, minute=0
        )
        schedule: list[dict] = []

        # Step 4: Pre-day entries
        has_sunrise_spots = any(
            (getattr(a, "best_visit_time_hour", 10) or 10) <= SUNRISE_MAX_HOUR
            for a in ordered
        )

        if day_type == "arrival":
            # Check-in at 2pm, activities at 3pm
            schedule.append({
                "name": "Hotel Check-in",
                "activity": "Hotel Check-in",
                "description": "Arrive and check into your accommodation",
                "type": "transport",
                "cost": 0,
                "is_break": True,
                "meal_type": None,
                "time": "14:00",
                "duration_minutes": 60,
                "end_time": "15:00",
            })

        elif day_type == "departure":
            # Early breakfast before checking out
            schedule.append({
                "name": "Breakfast",
                "activity": "Breakfast",
                "description": "Hotel breakfast before check-out",
                "type": "food",
                "cost": 0,
                "is_break": True,
                "meal_type": "breakfast",
                "time": "07:30",
                "duration_minutes": 30,
                "end_time": "08:00",
            })

        else:
            # Normal day: breakfast only when there are no sunrise spots
            # (sunrise visitors go out before breakfast)
            if not has_sunrise_spots:
                schedule.append({
                    "name": "Breakfast",
                    "activity": "Breakfast",
                    "description": "Start the day with a local breakfast",
                    "type": "food",
                    "cost": 0,
                    "is_break": True,
                    "meal_type": "breakfast",
                    "time": "08:00",
                    "duration_minutes": 30,
                    "end_time": "08:30",
                })

        # Step 5: Schedule each attraction
        for i, attraction in enumerate(ordered):
            # After the sunrise block, normalise to 9 AM so the rest of the day
            # runs from a standard morning start.
            if i == sunrise_count and sunrise_count > 0:
                nine_am = current_time.replace(hour=DAY_START_HOUR, minute=0)
                if current_time < nine_am:
                    current_time = nine_am

            duration_hours: float = getattr(attraction, "avg_visit_duration_hours", 1.5) or 1.5
            duration_minutes: int = int(duration_hours * 60)

            # Queue/security wait time: add BEFORE the attraction so the scheduled
            # arrival time reflects when the visitor actually enters, not arrives.
            queue_minutes: int = int(getattr(attraction, "queue_time_minutes", 0) or 0)

            # Travel time BEFORE the lunch check so arrival hour reflects actual position.
            travel_minutes: int = 0
            if i > 0:
                prev = ordered[i - 1]
                prev_lat = getattr(prev, "latitude", getattr(prev, "lat", None))
                prev_lon = getattr(prev, "longitude", getattr(prev, "lng", None))
                curr_lat = getattr(attraction, "latitude", getattr(attraction, "lat", None))
                curr_lon = getattr(attraction, "longitude", getattr(attraction, "lng", None))

                if (prev_lat is not None and prev_lon is not None
                        and curr_lat is not None and curr_lon is not None):
                    dist_km = haversine_km(prev_lat, prev_lon, curr_lat, curr_lon)
                    travel_minutes = max(
                        MIN_TRAVEL_MINUTES,
                        int((dist_km / self.AVG_URBAN_SPEED_KMH) * 60),
                    )
                else:
                    travel_minutes = 30  # fallback if coordinates missing

                current_time += timedelta(minutes=travel_minutes)

            # Apply queue wait — visitor queues/passes security before entering.
            if queue_minutes > 0:
                current_time += timedelta(minutes=queue_minutes)

            # Step 6: Lunch break — inserted once, first time arrival hour ≥ 12.
            has_lunch = any(
                s.get("is_break") and s.get("meal_type") == "lunch"
                for s in schedule
            )
            if current_time.hour >= 12 and not has_lunch:
                lunch_start = current_time.replace(hour=13, minute=0)
                if current_time.hour >= 13:
                    lunch_start = current_time
                schedule.append({
                    "name": "Lunch break",
                    "activity": "Lunch break",
                    "description": "Time for local cuisine",
                    "type": "food",
                    "cost": 0,
                    "is_break": True,
                    "meal_type": "lunch",
                    "time": lunch_start.strftime("%H:%M"),
                    "duration_minutes": 60,
                    "end_time": (lunch_start + timedelta(minutes=60)).strftime("%H:%M"),
                })
                current_time = lunch_start + timedelta(minutes=60)

            # Step 7: Departure day — stop scheduling activities after noon.
            if day_type == "departure" and current_time.hour >= 12:
                break

            # Entry cost (average of min and max)
            cost_min: int = getattr(attraction, "entry_cost_min", 0) or 0
            cost_max: int = getattr(attraction, "entry_cost_max", getattr(attraction, "entry_cost", 0)) or 0
            cost: int = int((cost_min + cost_max) / 2)

            # Crowd level at visit time (0-100, lower = less crowded).
            # Surfaced in the schedule output so frontend can warn travellers.
            crowd_by_hour: dict = getattr(attraction, "crowd_level_by_hour", None) or {}
            visit_hour_str = str(current_time.hour)
            crowd_at_visit = crowd_by_hour.get(visit_hour_str) or crowd_by_hour.get(current_time.hour)

            end_time = current_time + timedelta(minutes=duration_minutes)

            # Photo tip: flag if this is a photo spot and when the best shot is
            _is_photo = bool(getattr(attraction, "is_photo_spot", 0))
            _photo_hour_raw = getattr(attraction, "best_photo_hour", None)
            _photo_hour = int(_photo_hour_raw) if isinstance(_photo_hour_raw, (int, float)) else None
            _photo_tip = None
            if _is_photo and _photo_hour is not None:
                _photo_tip = (
                    f"Best photography: {_photo_hour:02d}:00"
                    if _photo_hour != current_time.hour
                    else "Ideal time for photography right now!"
                )

            schedule.append({
                "name": getattr(attraction, "name", "Unknown Activity"),
                "activity": getattr(attraction, "name", "Unknown Activity"),
                "description": getattr(attraction, "description", ""),
                "type": getattr(attraction, "type", "activity"),
                "cost": cost,
                "is_break": False,
                "time": current_time.strftime("%H:%M"),
                "end_time": end_time.strftime("%H:%M"),
                "duration_minutes": duration_minutes,
                "travel_to_next_minutes": travel_minutes,
                "queue_wait_minutes": queue_minutes,
                "latitude": getattr(attraction, "latitude", getattr(attraction, "lat", 0)),
                "longitude": getattr(attraction, "longitude", getattr(attraction, "lng", 0)),
                "images": getattr(attraction, "gallery_images", None) or [],
                "opening_hours": getattr(attraction, "opening_hours", None),
                "crowd_level_at_visit": crowd_at_visit,
                "requires_advance_booking": bool(
                    getattr(attraction, "requires_advance_booking", 0)
                ),
                # ── Traveler experience metadata ───────────────────────
                "difficulty_level": getattr(attraction, "difficulty_level", "easy") or "easy",
                "is_photo_spot": _is_photo,
                "photo_tip": _photo_tip,
                "dress_code": getattr(attraction, "dress_code", None),
                "guide_available": bool(getattr(attraction, "guide_available", 0)),
                "min_age": getattr(attraction, "min_age", None),
            })

            current_time = end_time

        # Step 8: Post-day entries
        if day_type == "departure":
            schedule.append({
                "name": "Hotel Check-out & Departure",
                "activity": "Hotel Check-out & Departure",
                "description": "Check out and head to station / airport",
                "type": "transport",
                "cost": 0,
                "is_break": True,
                "meal_type": None,
                "time": "12:00",
                "duration_minutes": 60,
                "end_time": "13:00",
            })
        else:
            # Dinner if the day runs past 7 pm
            has_dinner = any(
                s.get("is_break") and s.get("meal_type") == "dinner"
                for s in schedule
            )
            if current_time.hour >= 19 and not has_dinner:
                schedule.append({
                    "name": "Dinner",
                    "activity": "Dinner",
                    "description": "Enjoy the local cuisine for dinner",
                    "type": "food",
                    "cost": 0,
                    "is_break": True,
                    "meal_type": "dinner",
                    "time": current_time.strftime("%H:%M"),
                    "duration_minutes": 90,
                    "end_time": (current_time + timedelta(minutes=90)).strftime("%H:%M"),
                })
                current_time = current_time + timedelta(minutes=90)

        # Step 9: Pacing level — hybrid of activity count and total hours
        activity_count = len([s for s in schedule if not s.get("is_break")])
        total_hours = (current_time.hour - start_hour) + (current_time.minute / 60)

        if activity_count >= 6 or total_hours >= 9:
            pacing = "intense"
        elif activity_count >= 4 or total_hours >= 7:
            pacing = "moderate"
        else:
            pacing = "relaxed"

        return {
            "pacing_level": pacing,
            "activities": schedule,
        }
