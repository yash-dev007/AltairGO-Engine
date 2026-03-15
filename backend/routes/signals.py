from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt_identity, verify_jwt_in_request
import structlog

from backend.database import db
from backend.models import Attraction, AttractionSignal
from backend.request_validation import load_request_json
from backend.schemas import AttractionSignalSchema
from backend.extensions import limiter

signals_bp = Blueprint("signals", __name__)
log = structlog.get_logger(__name__)

ALLOWED_SIGNAL_EVENTS = {"view", "save", "remove", "swap", "book_click"}


@signals_bp.route("/api/attraction-signal", methods=["POST"])
@limiter.limit("60 per minute")
def record_attraction_signal():
    # Validate signal payloads so event metadata types are checked before persistence.
    data, error = load_request_json(AttractionSignalSchema())
    if error:
        return error
    attraction_id = data.get("attraction_id")
    event_type = data.get("event_type")

    attraction = db.session.get(Attraction, attraction_id)
    if not attraction:
        return jsonify({"error": "Attraction not found"}), 404

    user_id = None
    try:
        verify_jwt_in_request(optional=True)
        user_id = get_jwt_identity()
    except Exception as exc:
        log.warning(f"Could not verify JWT for attraction signal: {exc}")

    try:
        signal = AttractionSignal(
            attraction_id=attraction_id,
            user_id=user_id,
            event_type=event_type,
            traveler_type=data.get("traveler_type"),
            trip_style=data.get("trip_style", data.get("style")),
            budget_tier=data.get("budget_tier"),
            day_position=data.get("day_position"),
            trip_duration=data.get("trip_duration", data.get("duration")),
            session_id=data.get("session_id"),
        )
        db.session.add(signal)
        db.session.commit()
        return jsonify({"message": "Signal recorded", "id": signal.id}), 201
    except Exception as exc:
        db.session.rollback()
        log.error(f"Failed to record attraction signal: {exc}")
        return jsonify({"error": "Failed to record signal"}), 500
