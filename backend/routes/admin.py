"""
admin.py — Admin routes for AltairGO Intelligence Backend.
Covers: auth, stats, destination CRUD, user list, request management, trips.
"""

from flask import Blueprint, request, jsonify, current_app
from backend.database import db
from backend.models import (
    Country, Destination, Attraction, User, Trip,
    DestinationRequest, AnalyticsEvent,
)
from backend.request_validation import load_request_json
from backend.schemas import VerifyAdminKeySchema, UpdateDestinationSchema
from backend.utils.auth import require_admin
from backend.utils.responses import normalize_api_response
from backend.extensions import limiter

admin_bp = Blueprint('admin', __name__)


@admin_bp.after_request
def _normalize_admin_response(response):
    return normalize_api_response(response)


# ── Auth ─────────────────────────────────────────────────────────
@admin_bp.route('/api/admin/verify-key', methods=['POST'])
@limiter.limit("10 per minute; 50 per hour")
def verify_key():
    # Validate admin verification payloads so malformed requests fail with field-level errors.
    data, error = load_request_json(VerifyAdminKeySchema())
    if error:
        return error
    key = data.get("key")
    # Use constant-time comparison so key verification does not leak timing signals.
    expected_key = current_app.config.get("ADMIN_ACCESS_KEY", "")
    from hmac import compare_digest
    if not compare_digest(key, expected_key):
        return jsonify({"error": "Invalid key"}), 401
    
    # Issue a short-lived token with a unique jti for audit trail.
    # Each token carries a unique session ID so admin actions can be traced per token.
    import secrets as _secrets
    from datetime import timedelta
    from flask_jwt_extended import create_access_token
    token = create_access_token(
        identity=f"admin_{_secrets.token_hex(8)}",
        expires_delta=timedelta(minutes=60),
        additional_claims={"role": "admin", "jti": _secrets.token_hex(16)},
    )

    return jsonify({
        "message": "Valid admin key",
        "token": token
    }), 200


# ── Stats ────────────────────────────────────────────────────────
@admin_bp.route('/api/admin/stats', methods=['GET'])
@require_admin
def admin_stats():
    total_users = db.session.query(User).count()
    total_trips = db.session.query(Trip).count()
    total_destinations = db.session.query(Destination).count()
    total_attractions = db.session.query(Attraction).count()
    return jsonify({
        "total_users": total_users,
        "total_trips": total_trips,
        "total_destinations": total_destinations,
        "total_attractions": total_attractions,
    }), 200


# ── Destinations CRUD ────────────────────────────────────────────
@admin_bp.route('/api/admin/destinations', methods=['GET'])
@require_admin
def list_destinations():
    page = max(request.args.get("page", type=int, default=1), 1)
    page_size = min(request.args.get("page_size", type=int, default=50), 200)

    query = db.session.query(Destination).order_by(Destination.name.asc())
    total = query.count()
    items = query.limit(page_size).offset((page - 1) * page_size).all()

    return jsonify({
        "items": [{
            "id": d.id, "name": d.name, "slug": d.slug,
            "rating": d.rating, "estimated_cost_per_day": d.estimated_cost_per_day,
        } for d in items],
        "page": page,
        "page_size": page_size,
        "total": total,
        "total_pages": -(-total // page_size),
    }), 200


@admin_bp.route('/api/admin/destinations', methods=['POST'])
@require_admin
def create_destination():
    data, error = load_request_json(UpdateDestinationSchema())
    if error:
        return error
    if not data.get("name"):
        return jsonify({"error": "name is required"}), 400
    dest = Destination(**{k: v for k, v in data.items() if hasattr(Destination, k)})
    db.session.add(dest)
    db.session.commit()
    return jsonify({"message": "Destination created", "id": dest.id}), 201


@admin_bp.route('/api/admin/destinations/<int:dest_id>', methods=['PUT'])
@require_admin
def update_destination(dest_id):
    dest = db.session.get(Destination, dest_id)
    if not dest:
        return jsonify({"error": "Not found"}), 404
    data, error = load_request_json(UpdateDestinationSchema())
    if error:
        return error
    for key, value in data.items():
        if hasattr(dest, key):
            setattr(dest, key, value)
    db.session.commit()
    return jsonify({"message": "Updated"}), 200


@admin_bp.route('/api/admin/destinations/<int:dest_id>', methods=['DELETE'])
@require_admin
def delete_destination(dest_id):
    dest = db.session.get(Destination, dest_id)
    if not dest:
        return jsonify({"error": "Not found"}), 404
    db.session.delete(dest)
    db.session.commit()
    return jsonify({"message": "Deleted"}), 200


# ── Users ────────────────────────────────────────────────────────
@admin_bp.route('/api/admin/users', methods=['GET'])
@require_admin
def list_users():
    page = max(request.args.get("page", type=int, default=1), 1)
    page_size = min(request.args.get("page_size", type=int, default=50), 200)

    query = db.session.query(User).order_by(User.created_at.desc())
    total = query.count()
    items = query.limit(page_size).offset((page - 1) * page_size).all()

    return jsonify({
        "items": [{
            "id": u.id, "name": u.name, "email": u.email,
            "created_at": u.created_at.isoformat() if u.created_at else None,
        } for u in items],
        "page": page,
        "page_size": page_size,
        "total": total,
        "total_pages": -(-total // page_size),
    }), 200


# ── Requests ─────────────────────────────────────────────────────
@admin_bp.route('/api/admin/requests', methods=['GET'])
@require_admin
def list_requests():
    page = max(request.args.get("page", type=int, default=1), 1)
    page_size = min(request.args.get("page_size", type=int, default=50), 200)

    query = db.session.query(DestinationRequest).order_by(DestinationRequest.id.desc())
    total = query.count()
    items = query.limit(page_size).offset((page - 1) * page_size).all()

    return jsonify({
        "items": [{
            "id": r.id, "name": r.name, "description": r.description,
            "cost": r.cost, "tag": r.tag, "status": r.status,
        } for r in items],
        "page": page,
        "page_size": page_size,
        "total": total,
        "total_pages": -(-total // page_size),
    }), 200


@admin_bp.route('/api/admin/requests/<int:req_id>/approve', methods=['POST'])
@require_admin
def approve_request(req_id):
    req = db.session.get(DestinationRequest, req_id)
    if not req:
        return jsonify({"error": "Not found"}), 404
    req.status = "approved"
    # Create the destination
    dest = Destination(
        name=req.name,
        description=req.description,
        estimated_cost_per_day=req.cost,
        tag=req.tag,
    )
    db.session.add(dest)
    db.session.commit()
    return jsonify({"message": "Approved and destination created"}), 200


@admin_bp.route('/api/admin/requests/<int:req_id>/reject', methods=['POST'])
@require_admin
def reject_request(req_id):
    req = db.session.get(DestinationRequest, req_id)
    if not req:
        return jsonify({"error": "Not found"}), 404
    req.status = "rejected"
    db.session.commit()
    return jsonify({"message": "Rejected"}), 200


# ── Trips ────────────────────────────────────────────────────────
@admin_bp.route('/api/admin/trips', methods=['GET'])
@require_admin
def list_trips():
    page = max(request.args.get("page", type=int, default=1), 1)
    page_size = min(request.args.get("page_size", type=int, default=50), 200)

    query = db.session.query(Trip).order_by(Trip.created_at.desc())
    total = query.count()
    items = query.limit(page_size).offset((page - 1) * page_size).all()

    return jsonify({
        "items": [{
            "id": t.id, "trip_title": t.trip_title,
            "destination_country": t.destination_country,
            "budget": t.budget, "duration": t.duration,
            "created_at": t.created_at.isoformat() if t.created_at else None,
        } for t in items],
        "page": page,
        "page_size": page_size,
        "total": total,
        "total_pages": -(-total // page_size),
    }), 200

@admin_bp.route('/api/admin/trips/<int:trip_id>', methods=['GET'])
@require_admin
def get_trip(trip_id):
    trip = db.session.get(Trip, trip_id)
    if not trip:
        return jsonify({"error": "Not found"}), 404
    return jsonify({
        "id": trip.id,
        "trip_title": trip.trip_title,
        "destination_country": trip.destination_country,
        "budget": trip.budget,
        "duration": trip.duration,
        "travelers": trip.travelers,
        "itinerary": trip.itinerary_json,
        "created_at": trip.created_at.isoformat() if trip.created_at else None,
    }), 200

@admin_bp.route('/api/admin/trips/<int:trip_id>', methods=['DELETE'])
@require_admin
def delete_trip(trip_id):
    trip = db.session.get(Trip, trip_id)
    if not trip:
        return jsonify({"error": "Not found"}), 404
    db.session.delete(trip)
    db.session.commit()
    return jsonify({"message": "Trip deleted"}), 200

@admin_bp.route('/api/admin/users/<int:user_id>', methods=['DELETE'])
@require_admin
def delete_user(user_id):
    user = db.session.get(User, user_id)
    if not user:
        return jsonify({"error": "Not found"}), 404
    # Delete associated trips first or let cascade handle it if configured
    db.session.query(Trip).filter_by(user_id=user_id).delete()
    db.session.delete(user)
    db.session.commit()
    return jsonify({"message": "User and their trips deleted"}), 200


# ── Feature Flags CRUD ───────────────────────────────────────────────────────


@admin_bp.route('/api/admin/feature-flags', methods=['GET'])
@require_admin
def list_feature_flags():
    """List all feature flags."""
    from backend.models import FeatureFlag
    flags = db.session.query(FeatureFlag).order_by(FeatureFlag.flag_key.asc()).all()
    return jsonify({
        "flags": [_serialize_flag(f) for f in flags],
        "total": len(flags),
    }), 200


@admin_bp.route('/api/admin/feature-flags', methods=['POST'])
@require_admin
def create_feature_flag():
    """Create a new feature flag."""
    from backend.models import FeatureFlag
    body = request.get_json() or {}
    flag_key = (body.get("flag_key") or "").strip()
    if not flag_key:
        return jsonify({"error": "flag_key is required"}), 400
    if len(flag_key) > 100:
        return jsonify({"error": "flag_key must be under 100 characters"}), 400

    existing = db.session.query(FeatureFlag).filter_by(flag_key=flag_key).first()
    if existing:
        return jsonify({"error": f"Flag '{flag_key}' already exists. Use PATCH to update."}), 409

    try:
        flag = FeatureFlag(
            flag_key=flag_key,
            is_active=1 if body.get("is_active") else 0,
            traffic_pct=min(100, max(0, int(body.get("traffic_pct", 100)))),
            details=body.get("details"),
        )
        db.session.add(flag)
        db.session.commit()
        _invalidate_flag_cache(flag_key)
        return jsonify({"flag": _serialize_flag(flag), "message": "Feature flag created."}), 201
    except Exception:
        db.session.rollback()
        return jsonify({"error": "Internal server error"}), 500


@admin_bp.route('/api/admin/feature-flags/<flag_key>', methods=['PATCH'])
@require_admin
def update_feature_flag(flag_key: str):
    """Toggle or update a feature flag."""
    from backend.models import FeatureFlag
    flag = db.session.query(FeatureFlag).filter_by(flag_key=flag_key).first()
    if not flag:
        return jsonify({"error": "Flag not found"}), 404

    body = request.get_json() or {}
    try:
        if "is_active" in body:
            flag.is_active = 1 if body["is_active"] else 0
        if "traffic_pct" in body:
            flag.traffic_pct = min(100, max(0, int(body["traffic_pct"])))
        if "details" in body:
            flag.details = body["details"]
        db.session.commit()
        _invalidate_flag_cache(flag_key)
        return jsonify({"flag": _serialize_flag(flag), "message": "Flag updated."}), 200
    except Exception:
        db.session.rollback()
        return jsonify({"error": "Internal server error"}), 500


@admin_bp.route('/api/admin/feature-flags/<flag_key>', methods=['DELETE'])
@require_admin
def delete_feature_flag(flag_key: str):
    """Delete a feature flag."""
    from backend.models import FeatureFlag
    flag = db.session.query(FeatureFlag).filter_by(flag_key=flag_key).first()
    if not flag:
        return jsonify({"error": "Flag not found"}), 404
    db.session.delete(flag)
    db.session.commit()
    _invalidate_flag_cache(flag_key)
    return jsonify({"message": f"Flag '{flag_key}' deleted."}), 200


def _serialize_flag(flag) -> dict:
    return {
        "id": flag.id,
        "flag_key": flag.flag_key,
        "is_active": bool(flag.is_active),
        "traffic_pct": flag.traffic_pct,
        "details": flag.details,
        "created_at": flag.created_at.isoformat() if flag.created_at else None,
    }


def _invalidate_flag_cache(flag_key: str):
    try:
        from backend.services.feature_flags import invalidate
        invalidate(flag_key)
    except Exception:
        pass
