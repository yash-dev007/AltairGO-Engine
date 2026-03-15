import logging

log = logging.getLogger(__name__)

# ── Day theme heuristics (from architecture blueprint) ──────────────
DAY_THEMES = {
    frozenset(['fort', 'palace', 'historic', 'heritage']): "Heritage & Forts",
    frozenset(['museum', 'gallery', 'art', 'cultural']): "Culture & Arts",
    frozenset(['beach', 'natural', 'viewpoint', 'nature']): "Nature & Scenic",
    frozenset(['temple', 'mosque', 'church', 'religious']): "Spiritual & Sacred",
    frozenset(['market', 'restaurant', 'cafe', 'shopping', 'culinary']): "Food & Local Culture",
    frozenset(['park', 'lake', 'waterfall', 'recreation']): "Nature & Relaxation",
}


def detect_theme(attraction_types: list) -> str:
    """Detect day theme from the dominant attraction types in the cluster."""
    type_set = set(t.lower() for t in attraction_types if t)
    best_match = None
    best_overlap = 0
    for theme_types, theme_name in DAY_THEMES.items():
        overlap = len(type_set & theme_types)
        if overlap > best_overlap:
            best_overlap = overlap
            best_match = theme_name

    # Fix 17: Lower detect_theme threshold to 20%
    num_types = len(type_set)
    if num_types == 0:
        return "Explore & Discover"

    threshold = 0.20
    return best_match if (best_overlap / num_types) >= threshold else "Explore & Discover"


class Assembler:
    def assemble(self, engine_outputs: dict, preferences: dict,
                 hotel_data: dict = None, flight_data: list = None) -> dict:
        """
        Takes the outputs of the previous 4 phases and assembles the final JSON payload.

        Args:
            engine_outputs: dict with keys "clusters", "budget", "route"
            preferences: original trip payload from the user (duration, style, etc.)
            hotel_data: optional dict with hotel details (name, booking_url, cost_per_night)
            flight_data: optional list of inter-city flight/transport data

        Returns:
            dict containing "itinerary" (list of days), "total_cost", and "cost_breakdown"
        """
        route_data = engine_outputs.get("route", {})
        budget_data = engine_outputs.get("budget", {})
        clusters = engine_outputs.get("clusters", {})

        itinerary = []
        total_cost = 0
        total_breakdown = {
            "accommodation": 0,
            "food": 0,
            "transport": 0,
            "activities": 0,
            "misc": 0
        }

        # Build the day-by-day itinerary
        for day_num in range(1, preferences.get("duration", 1) + 1):
            day_key = f"day_{day_num}"

            day_route = route_data.get(day_key, {})
            day_budget = budget_data.get(day_key, {})
            day_cluster = clusters.get(day_key, [])

            # Detect theme from attraction types in this day's cluster
            day_types = [getattr(a, 'type', 'general') for a in day_cluster]
            theme = detect_theme(day_types)

            # Aggregate totals
            d_total = day_budget.get("day_total", 0)
            total_cost += d_total
            for key in total_breakdown.keys():
                total_breakdown[key] += day_budget.get(key, 0)

            # Build accommodation object
            accommodation_obj = day_budget.get("accommodation", 0)
            if hotel_data:
                accommodation_obj = {
                    "hotel_name": hotel_data.get("hotel_name", "Hotel"),
                    "cost_per_night": day_budget.get("accommodation", 0),
                    "booking_url": hotel_data.get("booking_url", ""),
                    "star_rating": hotel_data.get("star_rating"),
                    "category": hotel_data.get("category", "mid"),
                }

            # Determine city for multi-city support
            city = preferences.get("start_city", "Unknown City")
            if isinstance(day_cluster, dict) and "city" in day_cluster:
                city = day_cluster["city"]

            day_obj = {
                "day": day_num,
                "location": city,
                "theme": theme,
                "pacing_level": day_route.get("pacing_level", "moderate"),
                "activities": day_route.get("activities", []),
                "accommodation": accommodation_obj,
                "day_total": d_total
            }
            itinerary.append(day_obj)

        # Build travel_between_cities from FlightRoute data
        travel_between_cities = []
        if flight_data:
            for f in flight_data:
                travel_between_cities.append({
                    "origin": f.get("origin_iata", ""),
                    "destination": f.get("destination_iata", ""),
                    "transport_type": f.get("transport_type", "flight"),
                    "avg_price_inr": f.get("avg_one_way_inr", 0),
                    "duration_minutes": f.get("duration_minutes", 0),
                    "airlines": f.get("airlines", []),
                })

        result = {
            "itinerary": itinerary,
            "total_cost": total_cost,
            "cost_breakdown": total_breakdown,
            "smart_insights": [],
            "packing_tips": [],
        }

        if travel_between_cities:
            result["travel_between_cities"] = travel_between_cities

        return result
