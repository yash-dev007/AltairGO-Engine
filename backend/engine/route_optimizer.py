import logging
import math
from datetime import datetime, timedelta
from backend.utils.helpers import haversine_km

log = logging.getLogger(__name__)


class RouteOptimizer:
    AVG_URBAN_SPEED_KMH = 25  # Urban travel speed assumption

    def optimize(self, day_attractions: list, start_date_str: str) -> dict:
        """
        Takes a list of attraction objects for a single day and schedules them.
        Returns a dictionary with 'pacing_level' and 'activities' mapping.
        """
        if not day_attractions:
            return {"pacing_level": "relaxed", "activities": []}

        # Step 1: Force sunrise spots first (best_visit_time_hour <= 7)
        sunrise = [a for a in day_attractions if getattr(a, 'best_visit_time_hour', 10) <= 7]
        others = [a for a in day_attractions if getattr(a, 'best_visit_time_hour', 10) > 7]

        # Step 2: Sort others west-to-east (minimize backtracking)
        others_sorted = sorted(others, key=lambda a: getattr(a, 'longitude', getattr(a, 'lng', 0)) or 0)
        ordered = sunrise + others_sorted

        # Step 3: Assign time slots
        current_time = datetime.strptime(start_date_str, "%Y-%m-%d").replace(hour=9, minute=0)
        schedule = []

        for i, attraction in enumerate(ordered):
            # Insert lunch break — trigger if we've passed noon
            has_lunch = any(s.get('is_break', False) and s.get('meal_type') == 'lunch' for s in schedule)
            if current_time.hour >= 12 and not has_lunch:
                # Snap to 13:00 for consistency
                lunch_start = current_time.replace(hour=13, minute=0)
                if current_time.hour >= 13:
                    lunch_start = current_time
                schedule.append({
                    "name": "Lunch break",
                    "description": "Time for local cuisine",
                    "type": "food",
                    "cost": 0,
                    "is_break": True,
                    "meal_type": "lunch",
                    "time": lunch_start.strftime('%H:%M'),
                    "duration_minutes": 60,
                    "end_time": (lunch_start + timedelta(minutes=60)).strftime('%H:%M')
                })
                current_time = lunch_start + timedelta(minutes=60)

            duration_hours = getattr(attraction, 'avg_visit_duration_hours', 1.5) or 1.5
            duration_minutes = int(duration_hours * 60)

            # Calculate real travel time using Haversine distance
            travel_minutes = 0
            if i > 0:
                prev = ordered[i - 1]
                prev_lat = getattr(prev, 'latitude', getattr(prev, 'lat', None))
                prev_lon = getattr(prev, 'longitude', getattr(prev, 'lng', None))
                curr_lat = getattr(attraction, 'latitude', getattr(attraction, 'lat', None))
                curr_lon = getattr(attraction, 'longitude', getattr(attraction, 'lng', None))

                if prev_lat and prev_lon and curr_lat and curr_lon:
                    dist_km = haversine_km(prev_lat, prev_lon, curr_lat, curr_lon)
                    travel_minutes = max(10, int((dist_km / self.AVG_URBAN_SPEED_KMH) * 60))
                else:
                    travel_minutes = 30  # Fallback if coordinates missing

                current_time += timedelta(minutes=travel_minutes)

            # Entry cost (averaging min/max)
            cost_min = getattr(attraction, "entry_cost_min", 0) or 0
            cost_max = getattr(attraction, "entry_cost_max", getattr(attraction, "entry_cost", 0)) or 0
            cost = int((cost_min + cost_max) / 2)

            end_time = current_time + timedelta(minutes=duration_minutes)

            schedule.append({
                "name": getattr(attraction, "name", "Unknown Activity"),
                "activity": getattr(attraction, "name", "Unknown Activity"),
                "description": getattr(attraction, "description", ""),
                "type": getattr(attraction, "type", "activity"),
                "cost": cost,
                "is_break": False,
                "time": current_time.strftime('%H:%M'),
                "end_time": end_time.strftime('%H:%M'),
                "duration_minutes": duration_minutes,
                "travel_to_next_minutes": travel_minutes,
                "latitude": getattr(attraction, "latitude", getattr(attraction, "lat", 0)),
                "longitude": getattr(attraction, "longitude", getattr(attraction, "lng", 0))
            })

            current_time = end_time

        # Step 4: Pacing level — hybrid of activity count and total hours
        activity_count = len([s for s in schedule if not s.get("is_break")])
        total_hours = (current_time.hour - 9) + (current_time.minute / 60)

        if activity_count >= 6 or total_hours >= 9:
            pacing = "intense"
        elif activity_count >= 4 or total_hours >= 7:
            pacing = "moderate"
        else:
            pacing = "relaxed"

        return {
            "pacing_level": pacing,
            "activities": schedule
        }
