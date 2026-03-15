import logging

from backend.database import SessionLocal
from backend.engine.orchestrator import TripGenerationOrchestrator
from backend.models import Destination
from backend.services.cache_service import get_cached, set_cached
from backend.services.gemini_service import get_gemini_service
from backend.services.metrics_service import mark_status

log = logging.getLogger(__name__)

POPULAR_COMBOS = [
    {"duration": 3, "style": "budget", "travelers": 1, "traveler_type": "solo_male"},
    {"duration": 3, "style": "standard", "travelers": 2, "traveler_type": "couple"},
    {"duration": 5, "style": "standard", "travelers": 2, "traveler_type": "couple"},
]


class CacheWarmerAgent:
    def __init__(self, db_session=None):
        self.db = db_session or SessionLocal()
        self._owns_session = db_session is None
        self.orchestrator = TripGenerationOrchestrator(self.db, get_gemini_service())

    def warm(self, limit: int = 5) -> dict:
        warmed = 0
        skipped = 0
        failures = 0

        destinations = self.db.query(Destination).order_by(
            Destination.rating.desc(),
            Destination.estimated_cost_per_day.asc(),
            Destination.id.asc(),
        ).limit(limit).all()

        for destination in destinations:
            for combo in POPULAR_COMBOS:
                payload = {
                    "destination_country": "India",
                    "start_city": destination.name,
                    "selected_destinations": [{"id": destination.id, "name": destination.name}],
                    "budget": max(6000, int((destination.estimated_cost_per_day or 3000) * combo["duration"] * combo["travelers"])),
                    "duration": combo["duration"],
                    "travelers": combo["travelers"],
                    "style": combo["style"],
                    "traveler_type": combo["traveler_type"],
                    "travel_month": "oct",
                }

                cache_prefs = {
                    "origin_city": payload["start_city"],
                    "destination_names": [destination.name],
                    "budget": payload["budget"],
                    "duration": payload["duration"],
                    "travelers": payload["travelers"],
                    "style": payload["style"],
                    "traveler_type": payload["traveler_type"],
                    "travel_month": payload["travel_month"],
                    "start_date": payload.get("start_date"),
                }

                if get_cached(cache_prefs):
                    skipped += 1
                    continue

                try:
                    itinerary = self.orchestrator.generate(payload, emit_metrics=False)
                    set_cached(cache_prefs, itinerary)
                    warmed += 1
                except Exception as exc:
                    failures += 1
                    log.warning(f"Cache warmer failed for {destination.name}/{combo}: {exc}")

        result = {"warmed": warmed, "skipped": skipped, "failures": failures}
        mark_status("agent", "cache_warmer", "ok" if failures == 0 else "degraded", result)
        return result

    def close(self):
        if self._owns_session:
            self.db.close()
