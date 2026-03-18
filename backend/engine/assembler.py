import logging
import os

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


def _get_theme_threshold() -> float:
    """
    Read THEME_THRESHOLD at call time so runtime changes via EngineSetting
    (which writes to the env or DB) are reflected without a restart.
    Falls back to the constants.py default if env var is absent or invalid.
    """
    try:
        return float(os.getenv("THEME_THRESHOLD", "0.20"))
    except (ValueError, TypeError):
        return 0.20


def detect_theme(attraction_types: list, threshold: float | None = None) -> str:
    """
    Detect day theme from the dominant attraction types in the cluster.

    Args:
        attraction_types: list of type strings from day attractions.
        threshold: override the default overlap threshold (0.0–1.0).
                   If None, reads from THEME_THRESHOLD env var (default 0.20).
    """
    if threshold is None:
        threshold = _get_theme_threshold()

    type_set = set(t.lower() for t in attraction_types if t)
    best_match = None
    best_overlap = 0
    for theme_types, theme_name in DAY_THEMES.items():
        overlap = len(type_set & theme_types)
        if overlap > best_overlap:
            best_overlap = overlap
            best_match = theme_name

    num_types = len(type_set)
    if num_types == 0:
        return "Explore & Discover"

    return best_match if (best_overlap / num_types) >= threshold else "Explore & Discover"


def _build_document_checklist(preferences: dict) -> list[dict]:
    """
    Build a personalised document checklist based on traveler profile.
    Returns a list of {item, category, required} dicts the frontend can render
    as a check-off list.
    """
    items = [
        # ── Identity ──────────────────────────────────────────────────────────
        {"item": "Valid passport (check expiry — must be valid ≥ 6 months after return)", "category": "identity", "required": True},
        {"item": "Government-issued photo ID (Aadhar/PAN/Driving licence for domestic travel)", "category": "identity", "required": True},
        {"item": "Visa / e-Visa printout (if applicable)", "category": "identity", "required": False},
        # ── Travel ────────────────────────────────────────────────────────────
        {"item": "Flight / train tickets (digital or printed)", "category": "travel", "required": True},
        {"item": "Hotel booking confirmation", "category": "travel", "required": True},
        {"item": "Travel insurance policy document", "category": "travel", "required": False},
        {"item": "Emergency contact card (local police, ambulance, embassy)", "category": "travel", "required": True},
        # ── Health ────────────────────────────────────────────────────────────
        {"item": "Prescription medications (carry extra supply)", "category": "health", "required": False},
        {"item": "Basic first-aid kit (plasters, ORS, antacids, antihistamine)", "category": "health", "required": True},
        {"item": "Vaccination certificates (if required by destination)", "category": "health", "required": False},
        # ── Finance ───────────────────────────────────────────────────────────
        {"item": "Sufficient local currency (keep small notes for markets/autos)", "category": "finance", "required": True},
        {"item": "Credit/debit cards + UPI app (back-up payment)", "category": "finance", "required": True},
        {"item": "Trip budget breakdown printout", "category": "finance", "required": False},
    ]

    # Add children-specific items
    if (preferences.get("children_count") or 0) > 0:
        items.extend([
            {"item": "Children's birth certificates / school ID", "category": "identity", "required": True},
            {"item": "Paediatric medications and snacks", "category": "health", "required": True},
        ])

    # Add senior-specific items
    if (preferences.get("senior_count") or 0) > 0:
        items.extend([
            {"item": "Doctor's prescription letter listing all medications", "category": "health", "required": True},
            {"item": "Wheelchair / mobility aid booking confirmation (if needed)", "category": "travel", "required": False},
        ])

    # International trip extras
    if preferences.get("destination_country") and preferences["destination_country"].lower() != "india":
        items.extend([
            {"item": "International roaming / travel SIM activated", "category": "travel", "required": True},
            {"item": "Foreign currency / forex card loaded", "category": "finance", "required": True},
            {"item": "Travel adapter / power bank", "category": "essentials", "required": True},
        ])

    return items


def _build_daily_transport_guide(itinerary_days: list, preferences: dict) -> list[dict]:
    """
    Build a per-day transport cost estimate so travelers can budget for
    ground transport before they arrive.

    Estimates are based on average Indian urban cab/auto rates and are
    clearly labelled as estimates to set expectations.
    """
    style = (preferences.get("style") or "mid").lower()
    num_travelers = preferences.get("travelers") or preferences.get("num_travelers") or 1

    # Cost-per-trip estimates per traveler in INR (one-way)
    transport_costs = {
        "budget": {"cab_per_km": 8, "auto_per_km": 6, "metro_flat": 30},
        "mid":    {"cab_per_km": 12, "auto_per_km": 8, "metro_flat": 40},
        "luxury": {"cab_per_km": 18, "auto_per_km": 10, "metro_flat": 50},
    }
    tc = transport_costs.get(style, transport_costs["mid"])

    guide = []
    for day in itinerary_days:
        day_num = day.get("day", 1)
        activities = [a for a in day.get("activities", []) if not a.get("is_break")]
        pacing = day.get("pacing_level", "moderate")

        # Count inter-attraction hops and estimate distance from travel_to_next_minutes
        num_hops = max(0, len(activities) - 1)
        # Rough estimate: each hop averages 5 km in urban areas
        avg_km_per_hop = 5
        total_km = num_hops * avg_km_per_hop

        # Choose mode based on style and pacing
        if style == "luxury" or pacing == "intense":
            mode = "Private cab / chauffeur"
            cost_per_km = tc["cab_per_km"]
            airport_transfer = tc["cab_per_km"] * 25  # ~25 km to airport
        elif style == "budget":
            mode = "Auto-rickshaw / shared cab"
            cost_per_km = tc["auto_per_km"]
            airport_transfer = tc["auto_per_km"] * 25
        else:
            mode = "Ola/Uber cab"
            cost_per_km = tc["cab_per_km"]
            airport_transfer = tc["cab_per_km"] * 25

        estimated_transport = int(total_km * cost_per_km * num_travelers)

        entry: dict = {
            "day": day_num,
            "recommended_mode": mode,
            "estimated_inter_attraction_cost_inr": estimated_transport,
            "note": f"Approx. {num_hops} transit(s), ~{total_km} km total. Estimate only.",
        }

        # Arrival day: include airport pickup
        if day_num == 1:
            entry["airport_transfer_estimate_inr"] = int(airport_transfer * num_travelers)
            entry["arrival_tip"] = "Pre-book cab via app (Ola/Uber/Rapido) to avoid inflated airport cabs."

        # Departure day: include airport drop
        departure_day = preferences.get("duration") or len(itinerary_days)
        if day_num == departure_day and departure_day > 1:
            entry["airport_transfer_estimate_inr"] = int(airport_transfer * num_travelers)
            entry["departure_tip"] = "Allow 2.5–3 hours before flight. Pre-book cab the night before."

        guide.append(entry)

    return guide


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

        # Read threshold once per assembly so it's consistent across all days
        theme_threshold = _get_theme_threshold()

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
            day_types = [getattr(a, "type", "general") for a in day_cluster]
            theme = detect_theme(day_types, threshold=theme_threshold)

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

        # ── Document checklist ────────────────────────────────────────────────
        # Static checklist of what every traveler should carry.  Items are tagged
        # so the frontend can check them off.
        result["document_checklist"] = _build_document_checklist(preferences)

        # ── Daily transport guide ─────────────────────────────────────────────
        # Estimated cab/auto/metro costs per day so the traveler knows what to
        # budget for ground transport before they start booking.
        result["daily_transport_guide"] = _build_daily_transport_guide(
            itinerary, preferences
        )

        return result
