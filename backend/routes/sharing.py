"""Trip sharing — generates a public read-only link for any saved trip."""
import secrets

import redis
import structlog
from flask import Blueprint, current_app, jsonify
from flask_jwt_extended import get_jwt_identity, jwt_required

from backend.database import db
from backend.models import Trip
from backend.utils.responses import normalize_api_response

sharing_bp = Blueprint("sharing", __name__)
log = structlog.get_logger(__name__)


@sharing_bp.after_request
def _normalize_sharing_response(response):
    return normalize_api_response(response)

_SHARE_TTL = 60 * 60 * 24 * 30  # 30 days
_redis_pool: dict = {}  # keyed by REDIS_URL → ConnectionPool (avoids per-request connections)


def _redis():
    try:
        url = current_app.config.get("REDIS_URL", "")
        if not url:
            return None
        if url not in _redis_pool:
            _redis_pool[url] = redis.ConnectionPool.from_url(url)
        return redis.Redis(connection_pool=_redis_pool[url], decode_responses=True)
    except Exception:
        return None


@sharing_bp.post("/api/trip/<int:trip_id>/share")
@jwt_required()
def create_share_link(trip_id):
    user_id = int(get_jwt_identity())

    # Use FOR UPDATE lock to serialise concurrent share requests for the same trip
    trip = (
        db.session.query(Trip)
        .filter_by(id=trip_id, user_id=user_id)
        .with_for_update()
        .first()
    )
    if not trip:
        return jsonify({"error": "Trip not found"}), 404

    # Reuse existing token if present (second reader after lock sees freshly committed token)
    notes = trip.user_notes or {}
    token = notes.get("_share_token")
    if not token:
        token = secrets.token_urlsafe(24)
        notes = dict(notes)
        notes["_share_token"] = token
        trip.user_notes = notes
        db.session.commit()

    # Cache token → trip_id in Redis for O(1) lookup
    try:
        r = _redis()
        if r:
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
        if r:
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
        # Slow path: DB query (fallback when Redis is cold)
        # Use JSON extraction where supported; fall back to filtered scan
        try:
            from sqlalchemy import cast, String
            trip = (
                db.session.query(Trip)
                .filter(
                    Trip.user_notes.isnot(None),
                    cast(Trip.user_notes["_share_token"].astext, String) == share_token,
                )
                .first()
            )
        except Exception:
            # SQLite or engines without JSON path support — limited scan
            trip = (
                db.session.query(Trip)
                .filter(Trip.user_notes.isnot(None))
                .filter(Trip.user_notes.contains(share_token))
                .all()
            )
            trip = next(
                (t for t in trip if (t.user_notes or {}).get("_share_token") == share_token),
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
            r = _redis()
            if r:
                r.delete(f"share:{token}")
        except Exception:
            pass

    return jsonify({"message": "Share link revoked"}), 200
