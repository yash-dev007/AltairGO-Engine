import json
import logging
from datetime import datetime, timezone

from backend.agents.itinerary_qa_agent import ItineraryQAAgent
from backend.database import SessionLocal
from backend.models import Trip
from backend.services.metrics_service import mark_status, set_metric

log = logging.getLogger(__name__)


class ItineraryQualityPipeline:
    def __init__(self, db_session=None):
        self.db = db_session or SessionLocal()
        self._owns_session = db_session is None
        self.qa_agent = ItineraryQAAgent()

    def score_all_trips(self, batch_size: int = 50) -> dict:
        trips = self.db.query(Trip).filter(Trip.quality_score.is_(None)).limit(batch_size).all()
        scored = 0
        failures = 0

        for trip in trips:
            itinerary_payload = trip.itinerary_json
            if isinstance(itinerary_payload, list):
                itinerary_payload = {
                    "trip_title": trip.trip_title or "Saved Trip",
                    "total_cost": trip.total_cost or 0,
                    "itinerary": itinerary_payload,
                }

            if not isinstance(itinerary_payload, dict):
                failures += 1
                continue

            try:
                report = self.qa_agent.review_itinerary(itinerary_payload)
                trip.quality_score = report["score"]
                trip.quality_flags = report.get("issues", []) + report.get("warnings", [])
                scored += 1
            except Exception as exc:
                failures += 1
                log.warning(f"Quality scoring failed for trip {trip.id}: {exc}")

        self.db.commit()

        summary = {
            "scored": scored,
            "failures": failures,
            "completed_at": datetime.now(timezone.utc).isoformat(),
        }
        set_metric("quality:last_run", summary["completed_at"], ttl_seconds=7 * 24 * 60 * 60)
        set_metric("quality:scored_count", scored, ttl_seconds=7 * 24 * 60 * 60)
        mark_status("agent", "quality_scorer", "ok" if failures == 0 else "degraded", summary)
        return summary

    def close(self):
        if self._owns_session:
            self.db.close()
