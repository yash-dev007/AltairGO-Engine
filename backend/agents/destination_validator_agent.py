import logging

import requests

from backend.database import db
from backend.models import Destination, DestinationRequest
from backend.services.metrics_service import mark_status

log = logging.getLogger(__name__)


class DestinationValidatorAgent:
    """
    Nightly heuristic validator for pending destination requests.
    External lookups are opportunistic; if unavailable, the agent falls back
    to local signals and keeps ambiguous requests pending.
    """

    COST_MIN = 500
    COST_MAX = 50000

    def __init__(self, db_session=None):
        self.db = db_session or db.session

    def validate(self, request_record: DestinationRequest) -> tuple[str, dict]:
        score = 0
        reasons = []
        normalized_name = (request_record.name or "").strip()

        if not normalized_name:
            return "rejected", {"reason": "missing_name"}

        if self.db.query(Destination).filter(Destination.name.ilike(normalized_name)).first():
            return "rejected", {"reason": "destination_already_exists"}

        if len(normalized_name) >= 3 and any(char.isalpha() for char in normalized_name):
            score += 1
            reasons.append("name_shape_ok")

        if request_record.tag:
            score += 1
            reasons.append("tag_present")

        if request_record.cost and self.COST_MIN <= request_record.cost <= self.COST_MAX:
            score += 1
            reasons.append("cost_range_ok")
        elif request_record.cost in (0, None):
            reasons.append("cost_missing_or_zero")

        if self._wikipedia_exists(normalized_name):
            score += 2
            reasons.append("wikipedia_match")

        if score >= 4:
            return "approved", {"score": score, "reasons": reasons}
        if score <= 1:
            return "rejected", {"score": score, "reasons": reasons}
        return "pending", {"score": score, "reasons": reasons}

    def run_pending_requests(self) -> dict:
        pending_requests = self.db.query(DestinationRequest).filter_by(status="pending").all()
        results = {"processed": 0, "approved": 0, "rejected": 0, "pending": 0}

        for request_record in pending_requests:
            decision, details = self.validate(request_record)
            request_record.status = decision
            results["processed"] += 1
            results[decision] += 1
            log.info(f"DestinationValidatorAgent: {request_record.name} -> {decision} ({details})")

        self.db.commit()
        mark_status("agent", "destination_validator", "ok", results)
        return results

    @staticmethod
    def _wikipedia_exists(name: str) -> bool:
        try:
            response = requests.get(
                "https://en.wikipedia.org/w/api.php",
                params={
                    "action": "query",
                    "list": "search",
                    "srsearch": name,
                    "format": "json",
                    "srlimit": 1,
                },
                timeout=5,
            )
            if response.status_code != 200:
                return False
            payload = response.json()
            return bool(payload.get("query", {}).get("search"))
        except Exception:
            return False
