import logging
import math
import os
import time
from datetime import datetime, timedelta

from backend.agents.memory_agent import MemoryAgent
from backend.database import db
from backend.engine.assembler import Assembler
from backend.engine.budget_allocator import BudgetAllocator
from backend.engine.cluster_engine import ClusterEngine
from backend.engine.filter_engine import FilterEngine
from backend.engine.route_optimizer import RouteOptimizer
from backend.models import (
    Attraction, CurrencyRate, Destination, DestinationInfo, FlightRoute,
    HotelPrice, LocalEvent, POIClosure, WeatherAlert,
)
from backend.services.cache_service import get_cached_hotels, set_cached_hotels, get_cached_flights, set_cached_flights
from backend.services.metrics_service import add_stream_event, get_metrics_redis, mark_status, set_metric
from backend.validation import ItineraryValidator
from backend.utils.helpers import _extract_destination_names, _is_truthy

log = logging.getLogger(__name__)

# Cap attraction rows loaded per generation to prevent OOM on large DB imports.
# Ordered by popularity_score DESC so the best attractions are always included.
_MAX_ATTRACTIONS = int(os.getenv("MAX_ATTRACTIONS_PER_GENERATION", "500"))

# Budget tier demotion thresholds (INR per person per day)
_LUXURY_MIN_DAILY_PP = 2000
_MID_MIN_DAILY_PP = 1000


class TripGenerationOrchestrator:
    """
    Lightweight synchronous orchestrator for deterministic generation plus
    Gemini polish and pipeline metrics.
    """

    def __init__(self, db_session=None, gemini_service=None):
        self.db = db_session or db.session
        self.gemini = gemini_service

    def generate(
        self,
        request_data: dict,
        request_user_id=None,
        strict_validation: bool = False,
        emit_metrics: bool = True,
        _max_per_day_override: int | None = None,
    ) -> dict:
        destination_names = _extract_destination_names(request_data)
        if not destination_names:
            raise ValueError("At least one selected destination is required")

        timings = {}
        primary_destination_name = destination_names[0]

        # ── Destination lookup ────────────────────────────────────────────────
        destinations = self.db.query(Destination).filter(
            Destination.name.in_(destination_names)
        ).all()
        if not destinations:
            raise ValueError("Selected destinations not found")

        # Fix 5: Warn explicitly about any destination names not found in DB
        found_names = {d.name for d in destinations}
        missing_names = [n for n in destination_names if n not in found_names]
        if missing_names:
            log.warning(f"Destinations not found in DB (skipped): {missing_names}")

        destination_by_name = {d.name: d for d in destinations}
        primary_destination = destination_by_name.get(primary_destination_name)
        destination_ids = [d.id for d in destinations]

        # Fix 1: Cap attraction rows loaded — order by popularity so top-N are best ones
        attractions = (
            self.db.query(Attraction)
            .filter(Attraction.destination_id.in_(destination_ids))
            .order_by(Attraction.popularity_score.desc())
            .limit(_MAX_ATTRACTIONS)
            .all()
        ) if destination_ids else []

        # Resolve trip duration and start date early — needed for POIClosure filtering
        num_days = request_data["duration"]
        base_date_str = request_data.get("start_date", "2026-01-01")
        try:
            base_date = datetime.strptime(base_date_str, "%Y-%m-%d")
        except ValueError:
            base_date = datetime(2026, 1, 1)

        # ── POIClosure: remove attractions closed during the travel window ────
        trip_end_date = base_date + timedelta(days=num_days - 1)
        try:
            closures = self.db.query(POIClosure).filter(
                POIClosure.start_date <= trip_end_date,
            ).filter(
                (POIClosure.end_date.is_(None)) | (POIClosure.end_date >= base_date)
            ).all()
            closed_ids = {c.attraction_id for c in closures}
            if closed_ids:
                pre_count = len(attractions)
                attractions = [a for a in attractions if a.id not in closed_ids]
                log.info(
                    f"POIClosure: removed {pre_count - len(attractions)} "
                    f"closed attraction(s) for {base_date_str}–{trip_end_date.strftime('%Y-%m-%d')}."
                )
        except Exception as e:
            log.warning(f"POIClosure query failed: {e}")

        # ── Repeat traveler: skip attractions already visited on past trips ────
        # Reads the last 10 trips for this user and excludes any attraction
        # whose name appears in a previous itinerary.
        if request_user_id:
            try:
                from backend.models import Trip as _Trip
                past_trips = (
                    self.db.query(_Trip)
                    .filter(_Trip.user_id == request_user_id)
                    .order_by(_Trip.created_at.desc())
                    .limit(10)
                    .all()
                )
                visited_names: set[str] = set()
                for pt in past_trips:
                    if pt.itinerary_json and isinstance(pt.itinerary_json, dict):
                        for day in pt.itinerary_json.get("itinerary", []):
                            for act in day.get("activities", []):
                                if not act.get("is_break") and act.get("name"):
                                    visited_names.add(act["name"].lower().strip())
                if visited_names:
                    pre_count = len(attractions)
                    attractions = [
                        a for a in attractions
                        if (getattr(a, "name", "") or "").lower().strip() not in visited_names
                    ]
                    removed = pre_count - len(attractions)
                    if removed:
                        log.info(f"Repeat traveler: skipped {removed} already-visited attraction(s).")
            except Exception as e:
                log.warning(f"Repeat traveler check failed: {e}")

        senior_count = request_data.get("senior_count", 0) or 0
        children_count = request_data.get("children_count", 0) or 0

        user_prefs = {
            "budget_tier": request_data.get("style", "mid"),
            "traveler_type": request_data.get("traveler_type", "couple"),
            "travel_month": request_data.get("travel_month", "any"),
            "daily_activity_budget": request_data["budget"] * 0.2 / request_data["duration"],
            # Pass declared interests so FilterEngine can boost matching attraction types
            "interests": request_data.get("interests", []) or [],
            "children_count": children_count,
            "children_min_age": request_data.get("children_min_age", 0) or 0,
            "senior_count": senior_count,
            "accessibility": request_data.get("accessibility", 0) or 0,
            "dietary_restrictions": request_data.get("dietary_restrictions", []) or [],
            "special_occasion": request_data.get("special_occasion") or None,
            "fitness_level": request_data.get("fitness_level", "moderate") or "moderate",
        }

        # ── Senior pacing: reduce activities per day so the schedule is less tiring ──
        # seniors: max 3 activities/day (relaxed pace); mixed group (senior + others): 4.
        # This is applied as a _max_per_day_override only when senior_count is set and
        # no explicit override was already passed by generate_variants.
        if senior_count > 0 and _max_per_day_override is None:
            _max_per_day_override = 3 if senior_count >= request_data.get("travelers", 1) else 4

        started = time.monotonic()
        if request_user_id:
            memory_started = time.monotonic()
            memory_agent = MemoryAgent(self.db)
            user_prefs = memory_agent.inject_preferences(request_user_id, user_prefs)
            timings["memory_ms"] = int((time.monotonic() - memory_started) * 1000)
            mark_status(
                "agent",
                "memory",
                "ok",
                {"user_id": request_user_id, "signal_count": user_prefs.get("_memory_signal_count", 0)},
            )

        engine_started = time.monotonic()
        filtered = FilterEngine().filter(attractions, user_prefs, num_days=num_days)
        clusters = ClusterEngine().cluster(
            filtered, num_days,
            max_per_day=_max_per_day_override,
        )

        # ── closed_days: remove attractions closed on each specific travel day ──
        # Runs post-cluster so we know which day each attraction is assigned to.
        for day_key, day_acts in list(clusters.items()):
            day_index = int(day_key.split("_")[1]) - 1
            day_weekday = (base_date + timedelta(days=day_index)).weekday()  # 0=Mon … 6=Sun
            open_acts = [
                a for a in day_acts
                if day_weekday not in (getattr(a, "closed_days", None) or [])
            ]
            removed = len(day_acts) - len(open_acts)
            if removed:
                log.info(f"{day_key}: removed {removed} attraction(s) closed on weekday {day_weekday}.")
            clusters[day_key] = open_acts

        # ── Hotel data fetch (moved before BudgetAllocator) ───────────────────
        # Fetching early lets BudgetAllocator use the real per-night price
        # instead of a theoretical % of total_budget.
        hotel_data = None
        actual_hotel_cost_per_night = None
        if primary_destination:
            tier = request_data.get("style", "mid")
            hotel_data = get_cached_hotels(primary_destination.id, tier)
            if hotel_data is None:
                try:
                    hotel = self.db.query(HotelPrice).filter_by(
                        destination_id=primary_destination.id,
                        category=tier,
                    ).order_by(HotelPrice.last_synced.desc()).first()
                    if hotel:
                        hotel_data = {
                            "hotel_name": hotel.hotel_name,
                            "booking_url": hotel.booking_url,
                            "star_rating": hotel.star_rating,
                            "category": hotel.category,
                            "price_per_night_min": hotel.price_per_night_min,
                            "price_per_night_max": hotel.price_per_night_max,
                        }
                        set_cached_hotels(primary_destination.id, tier, hotel_data)
                except Exception as e:
                    log.warning(f"HotelPrice query failed: {e}")

            if hotel_data and hotel_data.get("price_per_night_min"):
                actual_hotel_cost_per_night = float(hotel_data["price_per_night_min"])

        budget_alloc = BudgetAllocator().allocate(
            total_budget=request_data["budget"],
            num_days=num_days,
            num_travelers=request_data.get("travelers", 1),
            tier=request_data.get("style", "mid"),
            clusters=clusters,
            actual_hotel_cost_per_night=actual_hotel_cost_per_night,
        )

        # Advance start_date by day index so each day's schedule reflects the real date.
        # day_type: arrival (day 1 on multi-day trips), departure (last day), normal (rest).
        route_data = {}
        for day_key, day_acts in clusters.items():
            day_index = int(day_key.split("_")[1]) - 1  # day_1 → 0, day_2 → 1, …
            day_date_str = (base_date + timedelta(days=day_index)).strftime("%Y-%m-%d")
            if num_days > 1:
                if day_index == 0:
                    day_type = "arrival"
                elif day_index == num_days - 1:
                    day_type = "departure"
                else:
                    day_type = "normal"
            else:
                day_type = "normal"
            route_data[day_key] = RouteOptimizer().optimize(day_acts, day_date_str, day_type=day_type)

        engine_outputs = {
            "clusters": clusters,
            "budget": budget_alloc,
            "route": route_data,
        }
        timings["engine_ms"] = int((time.monotonic() - engine_started) * 1000)

        # ── Flight data fetch ─────────────────────────────────────────────────
        flight_data = None
        selected_dests = request_data.get("selected_destinations", [])
        if len(selected_dests) > 1:
            # Use origin/destination pair as cache key for flight data
            dest_names_key = "_".join(sorted(destination_names))
            flight_data = get_cached_flights(destination_names[0], dest_names_key)
            if flight_data is None:
                try:
                    dest_iata_codes = [
                        d.iata_code for d in destinations
                        if getattr(d, "iata_code", None)
                    ]
                    query = self.db.query(FlightRoute)
                    if dest_iata_codes:
                        query = query.filter(
                            FlightRoute.origin_iata.in_(dest_iata_codes)
                            | FlightRoute.destination_iata.in_(dest_iata_codes)
                        )
                    flights = query.limit(100).all()
                    flight_data = [
                        {
                            "origin_iata": flight.origin_iata,
                            "destination_iata": flight.destination_iata,
                            "transport_type": flight.transport_type,
                            "avg_one_way_inr": flight.avg_one_way_inr,
                            "duration_minutes": flight.duration_minutes,
                            "airlines": flight.airlines or [],
                        }
                        for flight in flights
                    ]
                    if flight_data:
                        set_cached_flights(destination_names[0], dest_names_key, flight_data)
                except Exception as e:
                    log.warning(f"FlightRoute query failed: {e}")

        assembler_preferences = dict(request_data)
        assembler_preferences["start_city"] = primary_destination_name
        itinerary = Assembler().assemble(
            engine_outputs,
            assembler_preferences,
            hotel_data,
            flight_data,
        )
        itinerary["trip_title"] = f"Trip to {primary_destination_name}"

        # Surface traveler profile in itinerary so the frontend can show context.
        traveler_meta: dict = {}
        if request_data.get("dietary_restrictions"):
            traveler_meta["dietary_restrictions"] = request_data["dietary_restrictions"]
        if request_data.get("accessibility"):
            traveler_meta["accessibility"] = request_data["accessibility"]
        if request_data.get("children_count"):
            traveler_meta["children_count"] = request_data["children_count"]
        if senior_count:
            traveler_meta["senior_count"] = senior_count
        if request_data.get("special_occasion"):
            traveler_meta["special_occasion"] = request_data["special_occasion"]
        if traveler_meta:
            itinerary["traveler_profile"] = traveler_meta

        # ── Pre-trip information package ──────────────────────────────────────
        # Fetch DestinationInfo and surface as `pre_trip_info` so the frontend
        # can show a traveler briefing before the trip starts.
        if primary_destination:
            try:
                dest_info = (
                    self.db.query(DestinationInfo)
                    .filter_by(destination_id=primary_destination.id)
                    .first()
                )
                if dest_info:
                    pre_trip: dict = {}
                    if dest_info.travel_advisory_level and dest_info.travel_advisory_level > 1:
                        pre_trip["safety_advisory"] = {
                            "level": dest_info.travel_advisory_level,
                            "notes": dest_info.travel_advisory_notes,
                        }
                    if dest_info.emergency_contacts:
                        pre_trip["emergency_contacts"] = dest_info.emergency_contacts
                    if dest_info.best_hospitals:
                        pre_trip["nearest_hospitals"] = dest_info.best_hospitals
                    if dest_info.visa_notes:
                        pre_trip["visa_info"] = {
                            "notes": dest_info.visa_notes,
                            "visa_required_for": dest_info.visa_required_for or [],
                            "visa_on_arrival": dest_info.visa_on_arrival or [],
                        }
                    if dest_info.vaccinations_recommended:
                        pre_trip["health"] = {
                            "vaccinations": dest_info.vaccinations_recommended,
                            "notes": dest_info.health_notes,
                            "water_safety": dest_info.water_safety,
                        }
                    else:
                        pre_trip["water_safety"] = dest_info.water_safety
                    if dest_info.altitude_sickness_risk and dest_info.altitude_sickness_risk > 1:
                        pre_trip["altitude_warning"] = {
                            "meters": dest_info.altitude_meters,
                            "risk_level": dest_info.altitude_sickness_risk,
                        }
                    if dest_info.tipping_guide:
                        pre_trip["tipping_guide"] = dest_info.tipping_guide
                    if dest_info.hidden_fees:
                        pre_trip["hidden_fees"] = dest_info.hidden_fees
                    if dest_info.local_phrases:
                        pre_trip["local_phrases"] = dest_info.local_phrases
                    if dest_info.connectivity_guide:
                        pre_trip["connectivity_guide"] = dest_info.connectivity_guide
                    if dest_info.currency_tips:
                        pre_trip["currency_tips"] = dest_info.currency_tips
                    if dest_info.dress_code_general:
                        pre_trip["dress_code_general"] = dest_info.dress_code_general
                    if pre_trip:
                        itinerary["pre_trip_info"] = pre_trip
            except Exception as e:
                log.warning(f"DestinationInfo fetch failed: {e}")

        # ── Local events & festivals during travel window ─────────────────────
        if primary_destination:
            try:
                date_strs = [
                    (base_date + timedelta(days=i)).strftime("%Y-%m-%d")
                    for i in range(num_days)
                ]
                trip_end_str = (base_date + timedelta(days=num_days - 1)).strftime("%Y-%m-%d")
                local_events = (
                    self.db.query(LocalEvent)
                    .filter(
                        LocalEvent.destination_id == primary_destination.id,
                        LocalEvent.start_date <= trip_end_str,
                    )
                    .filter(
                        (LocalEvent.end_date.is_(None)) | (LocalEvent.end_date >= base_date_str)
                    )
                    .all()
                )
                if local_events:
                    events_payload = [
                        {
                            "name": ev.name,
                            "description": ev.description,
                            "type": ev.event_type,
                            "start_date": ev.start_date,
                            "end_date": ev.end_date,
                            "impact": ev.impact,
                            "tips": ev.tips,
                        }
                        for ev in local_events
                    ]
                    itinerary["local_events"] = events_payload
                    # Warn about avoid-impact events (crowds/closures)
                    avoid_events = [ev for ev in local_events if ev.impact == "avoid"]
                    if avoid_events:
                        for ev in avoid_events:
                            itinerary.setdefault("_validation_warnings", []).append(
                                f"⚠ '{ev.name}' ({ev.start_date}) may cause crowds or closures. "
                                + (ev.tips or "Plan accordingly.")
                            )
                    # Surface positive festival highlights
                    positive_events = [ev for ev in local_events if ev.impact == "positive"]
                    if positive_events:
                        itinerary.setdefault("smart_insights", []).extend([
                            f"🎉 {ev.name} ({ev.start_date}): {ev.description or 'Local festival happening during your visit!'}"
                            for ev in positive_events[:3]
                        ])
            except Exception as e:
                log.warning(f"LocalEvent fetch failed: {e}")

        # ── Rainy day alternatives ────────────────────────────────────────────
        # For each day, generate a set of indoor-friendly backup activities
        # so the traveller has a plan if weather turns bad.
        _indoor_types = frozenset({
            "museum", "gallery", "art", "cultural", "shopping",
            "restaurant", "cafe", "spa", "cinema", "theatre", "indoor",
        })
        indoor_pool = sorted(
            [a for a in filtered if (getattr(a, "type", "") or "").lower() in _indoor_types],
            key=lambda a: getattr(a, "popularity_score", 0) or 0,
            reverse=True,
        )
        # Check WeatherAlert table for active alerts during the travel window.
        # days with high/extreme alerts will have their rainy-day alternatives
        # promoted to the front of the itinerary via a warning flag.
        weather_alerts_by_date: dict[str, dict] = {}
        if primary_destination:
            try:
                date_strs = [
                    (base_date + timedelta(days=i)).strftime("%Y-%m-%d")
                    for i in range(num_days)
                ]
                alerts = (
                    self.db.query(WeatherAlert)
                    .filter(
                        WeatherAlert.destination_id == primary_destination.id,
                        WeatherAlert.alert_date.in_(date_strs),
                        WeatherAlert.severity.in_(["high", "extreme"]),
                    )
                    .all()
                )
                for alert in alerts:
                    weather_alerts_by_date[alert.alert_date] = {
                        "type": alert.alert_type,
                        "severity": alert.severity,
                        "probability_pct": alert.probability_pct,
                        "description": alert.description,
                    }
                if weather_alerts_by_date:
                    log.info(
                        f"WeatherAlert: {len(weather_alerts_by_date)} high/extreme alert(s) "
                        f"found for {primary_destination_name}."
                    )
            except Exception as e:
                log.warning(f"WeatherAlert query failed: {e}")

        if indoor_pool:
            rainy_day_alternatives: dict = {}
            for day_key, day_acts in clusters.items():
                day_index = int(day_key.split("_")[1]) - 1
                day_date_str = (base_date + timedelta(days=day_index)).strftime("%Y-%m-%d")
                used_ids = {getattr(a, "id", None) for a in day_acts}
                backup_pool = [
                    a for a in indoor_pool if getattr(a, "id", None) not in used_ids
                ][:3]
                if backup_pool:
                    backup_schedule = RouteOptimizer().optimize(backup_pool, day_date_str, day_type="normal")
                    alert_info = weather_alerts_by_date.get(day_date_str)
                    rainy_day_alternatives[day_key] = {
                        "note": "Rainy day plan — indoor alternatives if weather turns bad.",
                        "activities": backup_schedule["activities"],
                        # promoted=True means a live weather alert suggests using this plan today
                        "promoted": bool(alert_info),
                        **({"weather_alert": alert_info} if alert_info else {}),
                    }
            if rainy_day_alternatives:
                itinerary["rainy_day_alternatives"] = rainy_day_alternatives
        elif weather_alerts_by_date:
            # No indoor pool but there are weather alerts — at least surface the warning.
            itinerary["weather_alerts"] = weather_alerts_by_date

        # Fix 6: Surface budget tier demotion so users know why they got a lower tier
        requested_tier = request_data.get("style", "mid")
        daily_budget_pp = request_data["budget"] / (num_days * request_data.get("travelers", 1))
        if requested_tier == "luxury" and daily_budget_pp < _LUXURY_MIN_DAILY_PP:
            itinerary.setdefault("_validation_warnings", []).append(
                f"Budget too low for luxury tier "
                f"(₹{daily_budget_pp:.0f}/person/day < ₹{_LUXURY_MIN_DAILY_PP}). "
                "Itinerary generated at mid-range level."
            )
        elif requested_tier == "mid" and daily_budget_pp < _MID_MIN_DAILY_PP:
            itinerary.setdefault("_validation_warnings", []).append(
                f"Budget too low for mid-range tier "
                f"(₹{daily_budget_pp:.0f}/person/day < ₹{_MID_MIN_DAILY_PP}). "
                "Itinerary generated at budget level."
            )

        # ── Multi-currency: convert costs if display_currency != INR ─────────
        display_currency = (request_data.get("display_currency") or "INR").upper()
        if display_currency != "INR":
            try:
                rate_row = (
                    self.db.query(CurrencyRate)
                    .filter_by(base_currency="INR", target_currency=display_currency)
                    .order_by(CurrencyRate.snapshot_date.desc())
                    .first()
                )
                if rate_row:
                    rate = rate_row.rate
                    itinerary["display_currency"] = display_currency
                    itinerary["inr_to_display_rate"] = rate
                    itinerary["total_cost_display"] = round(itinerary.get("total_cost", 0) * rate, 2)
                    # Convert per-day totals
                    for day in itinerary.get("itinerary", []):
                        day["day_total_display"] = round(day.get("day_total", 0) * rate, 2)
                        for act in day.get("activities", []):
                            if not act.get("is_break") and act.get("cost"):
                                act["cost_display"] = round(act["cost"] * rate, 2)
                else:
                    log.warning(f"No INR→{display_currency} rate in CurrencyRate table. Showing INR.")
            except Exception as e:
                log.warning(f"Currency conversion failed: {e}")

        # Fix 8: polish_itinerary_text mutates itinerary in-place and returns it.
        # No need for the redundant _merge_polished_itinerary deep-copy wrapper.
        if self.gemini:
            gemini_started = time.monotonic()
            itinerary = self.gemini.polish_itinerary_text(
                itinerary,
                {
                    "traveler_type": request_data.get("traveler_type", "couple"),
                    "city": primary_destination_name,
                    "days": request_data["duration"],
                    "travel_month": request_data.get("travel_month"),
                },
            )
            timings["gemini_ms"] = int((time.monotonic() - gemini_started) * 1000)

        validator_started = time.monotonic()
        is_strict = _is_truthy(os.getenv("VALIDATION_STRICT", "false")) or strict_validation

        validation_result = ItineraryValidator(strict=is_strict).validate(
            itinerary,
            user_budget=request_data["budget"],
            expected_days=num_days,
        )
        if validation_result.get("corrected"):
            itinerary = validation_result["corrected"]
        if not validation_result["valid"] and not validation_result.get("corrected"):
            raise ValueError("; ".join(validation_result["errors"]))
        if validation_result.get("warnings"):
            itinerary.setdefault("_validation_warnings", [])
            itinerary["_validation_warnings"].extend(validation_result["warnings"])
        timings["validation_ms"] = int((time.monotonic() - validator_started) * 1000)

        if emit_metrics:
            self._emit_metrics(timings, request_data, primary_destination_name)

        total_elapsed_ms = int((time.monotonic() - started) * 1000)
        itinerary["_generation_metrics"] = {
            **timings,
            "total_ms": total_elapsed_ms,
        }
        return itinerary

    def generate_variants(
        self,
        request_data: dict,
        request_user_id=None,
    ) -> dict:
        """
        Generate three plan variants for the same trip parameters so the
        traveller can pick the style that suits them best.

          relaxed  — 3 activities/day, leisurely pace
          balanced — 5 activities/day, mix of sightseeing and downtime
          intense  — 6 activities/day, see as much as possible

        Returns:
            {"relaxed": {itinerary}, "balanced": {itinerary}, "intense": {itinerary}}
        """
        configs = {
            "relaxed":  3,
            "balanced": 5,
            "intense":  6,
        }
        variants: dict = {}
        for variant_name, max_per_day in configs.items():
            try:
                variant = self.generate(
                    request_data,
                    request_user_id=request_user_id,
                    strict_validation=False,
                    emit_metrics=False,
                    _max_per_day_override=max_per_day,
                )
                variant["_variant"] = variant_name
                variants[variant_name] = variant
            except Exception as exc:
                log.warning(f"generate_variants: '{variant_name}' failed — {exc}")
                variants[variant_name] = {"error": str(exc), "_variant": variant_name}

        return variants

    def _emit_metrics(self, timings: dict, request_data: dict, city: str):
        total_ms = sum(timings.values())
        event = {
            "city": city,
            "style": request_data.get("style", "standard"),
            "duration": request_data.get("duration", 0),
            "travelers": request_data.get("travelers", 1),
            **timings,
            "total_ms": total_ms,
        }
        add_stream_event("pipeline:metrics", event)
        set_metric("metrics:pipeline:last_event", event, ttl_seconds=7 * 24 * 60 * 60)
        self._update_latency_metrics(total_ms)

    @staticmethod
    def _update_latency_metrics(total_ms: int):
        client = get_metrics_redis()
        if not client:
            return

        try:
            client.lpush("metrics:generation_samples", total_ms)
            client.ltrim("metrics:generation_samples", 0, 199)
            samples = [int(value) for value in client.lrange("metrics:generation_samples", 0, -1)]
            if not samples:
                return
            samples_sorted = sorted(samples)
            percentile_index = max(0, math.ceil(len(samples_sorted) * 0.95) - 1)
            set_metric("metrics:avg_gen_ms", int(sum(samples_sorted) / len(samples_sorted)), ttl_seconds=7 * 24 * 60 * 60)
            set_metric("metrics:p95_gen_ms", samples_sorted[percentile_index], ttl_seconds=7 * 24 * 60 * 60)
        except Exception as exc:
            log.warning(f"Pipeline latency metric update failed: {exc}")
