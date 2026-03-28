import secrets
import structlog
from werkzeug.security import check_password_hash, generate_password_hash
from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required

from backend.database import db
from backend.models import (
    AnalyticsEvent, AsyncJob, AttractionSignal, ExpenseEntry,
    Feedback, User, UserProfile,
)

profile_bp = Blueprint("profile", __name__)
log = structlog.get_logger(__name__)

# Allowlist of preference keys that users may set via the API.
# Unknown keys are silently dropped to prevent injection of trust signals.
_ALLOWED_PREF_KEYS = frozenset({
    "dietary_restrictions",
    "accessibility",
    "traveler_type",
    "interests",
    "children_count",
    "senior_count",
    "children_min_age",
    "fitness_level",
    "special_occasion",
    "preferred_style",
    "home_city",
    "currency",
})


@profile_bp.get("/api/user/profile")
@jwt_required()
def get_profile():
    user_id = int(get_jwt_identity())
    user = db.session.get(User, user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404

    profile = db.session.query(UserProfile).filter_by(user_id=user_id).first()
    return jsonify({
        "id": user.id,
        "name": user.name,
        "email": user.email,
        "created_at": user.created_at.isoformat() if user.created_at else None,
        "preferences": profile.preferences if profile else {},
    }), 200


@profile_bp.put("/api/user/profile")
@jwt_required()
def update_profile():
    user_id = int(get_jwt_identity())
    user = db.session.get(User, user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404

    body = request.get_json(silent=True) or {}

    if "name" in body:
        name = str(body["name"]).strip()
        if not name:
            return jsonify({"error": "Name cannot be empty"}), 400
        user.name = name

    prefs = body.get("preferences")
    if prefs is not None:
        if not isinstance(prefs, dict):
            return jsonify({"error": "preferences must be an object"}), 400
        # Only retain keys from the allowlist — drop anything unknown.
        sanitized_prefs = {k: v for k, v in prefs.items() if k in _ALLOWED_PREF_KEYS}
        profile = db.session.query(UserProfile).filter_by(user_id=user_id).first()
        if not profile:
            profile = UserProfile(user_id=user_id, preferences={})
            db.session.add(profile)
        existing = dict(profile.preferences or {})
        existing.update(sanitized_prefs)
        profile.preferences = existing

    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        log.error("profile_update_failed", user_id=user_id, error=str(e))
        return jsonify({"error": "Failed to update profile"}), 500

    return jsonify({"message": "Profile updated"}), 200


@profile_bp.delete("/api/user/account")
@jwt_required()
def delete_account():
    """GDPR-compliant account deletion (anonymise user + purge all related activity data)."""
    user_id = int(get_jwt_identity())
    user = db.session.get(User, user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404

    # Password re-confirmation is optional when provided, skipped when absent.
    # JWT already proves identity; frontend shows a confirmation step before calling this.
    body = request.get_json(silent=True) or {}
    password = body.get("password")
    if password and not check_password_hash(user.password_hash, password):
        return jsonify({"error": "Incorrect password"}), 403

    try:
        # Purge all user activity data (GDPR right to be forgotten)
        db.session.query(AttractionSignal).filter_by(user_id=user_id).delete()
        db.session.query(AnalyticsEvent).filter_by(user_id=user_id).delete()
        db.session.query(Feedback).filter_by(user_id=user_id).delete()
        db.session.query(ExpenseEntry).filter_by(user_id=user_id).delete()
        db.session.query(AsyncJob).filter_by(user_id=user_id).delete()
        # Delete profile preferences
        db.session.query(UserProfile).filter_by(user_id=user_id).delete()

        # Anonymise the User record (preserve FK refs from Trip, Booking, etc.)
        user.name = "Deleted User"
        user.email = f"deleted_{user_id}@altairgo.invalid"
        user.password_hash = generate_password_hash(secrets.token_hex(32))

        db.session.commit()
        log.info("account_deleted", user_id=user_id)
    except Exception as e:
        db.session.rollback()
        log.exception("account_delete_failed", user_id=user_id, error=str(e))
        return jsonify({"error": "Failed to delete account"}), 500

    return jsonify({"message": "Account deleted"}), 200
