"""Trip sharing — generates a public read-only link for any saved trip."""
import secrets

import redis
import structlog
from flask import Blueprint, current_app, jsonify
from flask_jwt_extended import get_jwt_identity, jwt_required

from backend.database import db
from backend.models import Trip

sharing_bp = Blueprint("sharing", __name__)
log = structlog.get_logger(__name__)

_SHARE_TTL = 60 * 60 * 24 * 30  # 30 days


def _redis():
    url = current_app.config.get("REDIS_URL", "")
    return redis.from_url(url, decode_responses=True)


@sharing_bp.post("/api/trip/<int:trip_id>/share")
@jwt_required()
def create_share_link(trip_id):
    user_id = int(get_jwt_identity())
    trip = db.session.query(Trip).filter_by(id=trip_id, user_id=user_id).first()
    if not trip:
        return jsonify({"error": "Trip not found"}), 404

    # Reuse existing token if present
    notes = trip.user_notes or {}
    token = notes.get("_share_token")
    if not token:
        token = secrets.token_urlsafe(24)
        notes["_share_token"] = token
        trip.user_notes = notes
        db.session.commit()

    # Cache token → trip_id in Redis for O(1) lookup
    try:
        r = _redis()
        r.setex(f"share:{token}", _SHARE_TTL, str(trip_id))
    except Exception as e:
        log.warning("share_redis_cache_failed", error=str(e))

    return jsonify({
        "share_token": token,
        "share_url": f"/trip/shared/{token}",
    }), 200


@sharing_bp.get("/api/shared/<share_token>")
def get_shared_trip(share_token):
    """Public endpoint — no auth required."""
    trip_id = None

    # Fast path: Redis
    try:
        r = _redis()
        val = r.get(f"share:{share_token}")
        if val:
            trip_id = int(val)
    except Exception:
        pass

    if trip_id:
        trip = db.session.get(Trip, trip_id)
        # Validate token still matches (user may have regenerated)
        if trip and (trip.user_notes or {}).get("_share_token") != share_token:
            trip = None
    else:
        # Slow path: DB scan (fallback when Redis is cold)
        trips = db.session.query(Trip).filter(Trip.user_notes.isnot(None)).all()
        trip = next(
            (t for t in trips if (t.user_notes or {}).get("_share_token") == share_token),
            None,
        )

    if not trip:
        return jsonify({"error": "Shared trip not found or link expired"}), 404

    return jsonify({
        "trip_title": trip.trip_title,
        "duration": trip.duration,
        "budget": trip.budget,
        "total_cost": trip.total_cost,
        "quality_score": trip.quality_score,
        "itinerary": trip.itinerary_json,
        "is_customized": bool(trip.is_customized),
    }), 200


@sharing_bp.delete("/api/trip/<int:trip_id>/share")
@jwt_required()
def revoke_share_link(trip_id):
    user_id = int(get_jwt_identity())
    trip = db.session.query(Trip).filter_by(id=trip_id, user_id=user_id).first()
    if not trip:
        return jsonify({"error": "Trip not found"}), 404

    notes = trip.user_notes or {}
    token = notes.pop("_share_token", None)
    trip.user_notes = notes
    db.session.commit()

    if token:
        try:
            _redis().delete(f"share:{token}")
        except Exception:
            pass

    return jsonify({"message": "Share link revoked"}), 200
