import copy
import logging
import math
import time

from backend.agents.memory_agent import MemoryAgent
from backend.database import db
from backend.engine.assembler import Assembler
from backend.engine.budget_allocator import BudgetAllocator
from backend.engine.cluster_engine import ClusterEngine
from backend.engine.filter_engine import FilterEngine
from backend.engine.route_optimizer import RouteOptimizer
from backend.models import Attraction, Destination, FlightRoute, HotelPrice
from backend.services.metrics_service import add_stream_event, get_metrics_redis, mark_status, set_metric
from backend.validation import ItineraryValidator
import os
from backend.utils.helpers import _extract_destination_names, _is_truthy

log = logging.getLogger(__name__)


def _merge_polished_itinerary(base_itinerary: dict, polished_payload: dict) -> dict:
    if not isinstance(polished_payload, dict):
        return base_itinerary

    merged = copy.deepcopy(base_itinerary)

    for top_level_key in ("trip_title", "smart_insights", "packing_tips"):
        value = polished_payload.get(top_level_key)
        if value:
            merged[top_level_key] = value

    polished_days = polished_payload.get("itinerary")
    if not isinstance(polished_days, list):
        return merged

    for day_index, day in enumerate(merged.get("itinerary", [])):
        if day_index >= len(polished_days):
            break
        polished_day = polished_days[day_index] or {}
        if polished_day.get("theme"):
            day["theme"] = polished_day["theme"]

        polished_activities: list[dict] = polished_day.get("activities", [])
        if not isinstance(polished_activities, list):
            continue

        for activity_index, activity in enumerate(day.get("activities", [])):
            if activity_index >= len(polished_activities):
                break
            polished_activity = polished_activities[activity_index] or {}
            for text_field in ("description", "why_this_fits", "local_secret", "how_to_reach"):
                val = polished_activity.get(text_field)
                if val is not None:
                    activity[text_field] = val

    return merged


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
    ) -> dict:
        destination_names = _extract_destination_names(request_data)
        if not destination_names:
            raise ValueError("At least one selected destination is required")

        timings = {}
        primary_destination_name = destination_names[0]

        destinations = self.db.query(Destination).filter(
            Destination.name.in_(destination_names)
        ).all()
        if not destinations:
            raise ValueError("Selected destinations not found")

        destination_by_name = {destination.name: destination for destination in destinations}
        primary_destination = destination_by_name.get(primary_destination_name)
        destination_ids = [destination.id for destination in destinations]

        attractions = self.db.query(Attraction).filter(
            Attraction.destination_id.in_(destination_ids)
        ).all() if destination_ids else []

        user_prefs = {
            "budget_tier": request_data.get("style", "mid"),
            "traveler_type": request_data.get("traveler_type", "couple"),
            "travel_month": request_data.get("travel_month", "any"),
            "daily_activity_budget": request_data["budget"] * 0.2 / request_data["duration"],
        }

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
        filtered = FilterEngine().filter(attractions, user_prefs)
        clusters = ClusterEngine().cluster(filtered, request_data["duration"])
        budget_alloc = BudgetAllocator().allocate(
            total_budget=request_data["budget"],
            num_days=request_data["duration"],
            num_travelers=request_data.get("travelers", 1),
            tier=request_data.get("style", "mid"),
            clusters=clusters,
        )

        route_data = {}
        for day_key, day_acts in clusters.items():
            route_data[day_key] = RouteOptimizer().optimize(
                day_acts,
                request_data.get("start_date", "2026-01-01"),
            )

        engine_outputs = {
            "clusters": clusters,
            "budget": budget_alloc,
            "route": route_data,
        }
        timings["engine_ms"] = int((time.monotonic() - engine_started) * 1000)

        # ── Data Fetching & Guarded Queries ───────────────────────────────────
        hotel_data = None
        if primary_destination:
            tier = request_data.get("style", "mid")
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
                    }
            except Exception as e:
                log.warning(f"HotelPrice query failed: {e}")

        flight_data = None
        selected_dests = request_data.get("selected_destinations", [])
        if len(selected_dests) > 1:
            try:
                # Only fetch flight routes relevant to the selected destinations,
                # not the entire table (fixes OOM risk with large datasets).
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

        if self.gemini:
            gemini_started = time.monotonic()
            polished_payload = self.gemini.polish_itinerary_text(
                itinerary,
                {
                    "traveler_type": request_data.get("traveler_type", "couple"),
                    "city": primary_destination_name,
                    "days": request_data["duration"],
                    "travel_month": request_data.get("travel_month"),
                },
            )
            itinerary = _merge_polished_itinerary(itinerary, polished_payload)
            timings["gemini_ms"] = int((time.monotonic() - gemini_started) * 1000)

        validator_started = time.monotonic()
        # Fix 6: Wire VALIDATION_STRICT correctly
        is_strict = _is_truthy(os.getenv("VALIDATION_STRICT", "false")) or strict_validation
        
        validation_result = ItineraryValidator(strict=is_strict).validate(
            itinerary,
            user_budget=request_data["budget"],
        )
        if validation_result.get("corrected"):
            itinerary = validation_result["corrected"]
        if not validation_result["valid"] and not validation_result.get("corrected"):
            raise ValueError("; ".join(validation_result["errors"]))
        if validation_result.get("warnings"):
            itinerary["_validation_warnings"] = validation_result["warnings"]
        timings["validation_ms"] = int((time.monotonic() - validator_started) * 1000)

        if emit_metrics:
            self._emit_metrics(timings, request_data, primary_destination_name)

        total_elapsed_ms = int((time.monotonic() - started) * 1000)
        itinerary["_generation_metrics"] = {
            **timings,
            "total_ms": total_elapsed_ms,
        }
        return itinerary

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
