"""
routes/feedback.py — Trip Review & Attraction Rating API
═══════════════════════════════════════════════════════

Traveler-submitted ratings feed directly into the quality feedback loop:
  - Trip reviews (1-5 stars + tags + comment) are blended into Trip.quality_score
  - Attraction reviews adjust Attraction.google_rating and popularity_score
  - Destination aggregate reviews are public (no auth required)

Endpoints:
  POST   /api/trip/<id>/review               Submit trip review
  GET    /api/trip/<id>/review               Get my review for a trip
  PUT    /api/trip/<id>/review               Update my review
  POST   /api/attraction/<id>/review         Rate an individual attraction
  GET    /api/destination/<id>/reviews       Aggregated public reviews
"""

import structlog
from flask import Blueprint, g, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required

from backend.database import db
from backend.extensions import limiter
from backend.models import Attraction, Destination, Feedback, Trip

feedback_bp = Blueprint("feedback", __name__)
log = structlog.get_logger(__name__)

_VALID_TAGS = frozenset({
    # Frontend tags (hyphenated)
    "great-value", "well-paced", "hidden-gems", "family-friendly",
    "romantic", "adventure", "foodie", "budget-friendly",
    # Legacy tags (underscore) — kept for backward compatibility
    "family_friendly", "worth_the_cost", "hidden_gem", "crowded",
    "great_guide", "poor_infrastructure", "breathtaking_views",
    "overrated", "authentic_experience", "good_for_couples",
    "solo_friendly", "budget_friendly", "well_organised", "needs_improvement",
})

_MAX_COMMENT_LEN = 2000
_MAX_TAGS = 5


def _safe_user_id() -> int | None:
    try:
        return int(get_jwt_identity())
    except (TypeError, ValueError):
        return None


def _validate_rating(rating) -> tuple[float | None, str | None]:
    """Return (float, None) on success or (None, error_msg) on failure."""
    try:
        r = float(rating)
        if not (1.0 <= r <= 5.0):
            return None, "rating must be between 1 and 5"
        return round(r * 2) / 2, None  # Round to nearest 0.5
    except (TypeError, ValueError):
        return None, "rating must be a number between 1 and 5"


def _validate_tags(tags) -> tuple[list, str | None]:
    if tags is None:
        return [], None
    if not isinstance(tags, list):
        return [], "tags must be an array"
    invalid = [t for t in tags if t not in _VALID_TAGS]
    if invalid:
        return [], f"invalid tags: {invalid}. Valid tags: {sorted(_VALID_TAGS)}"
    if len(tags) > _MAX_TAGS:
        return [], f"maximum {_MAX_TAGS} tags allowed"
    return [str(t) for t in tags], None


# ── Trip Reviews ──────────────────────────────────────────────────────────────


@feedback_bp.route("/api/trip/<int:trip_id>/review", methods=["POST"])
@jwt_required()
@limiter.limit("10 per minute")
def submit_trip_review(trip_id: int):
    """Submit a review for a completed trip."""
    user_id = _safe_user_id()
    if user_id is None:
        return jsonify({"error": "Unauthorized"}), 401

    body = request.get_json() or {}
    rating, err = _validate_rating(body.get("rating"))
    if err:
        return jsonify({"error": err}), 400

    tags, err = _validate_tags(body.get("tags"))
    if err:
        return jsonify({"error": err}), 400

    comment = body.get("comment", "")
    if comment and len(comment) > _MAX_COMMENT_LEN:
        return jsonify({"error": f"comment must be under {_MAX_COMMENT_LEN} characters"}), 400

    try:
        trip = db.session.get(Trip, trip_id)
        if not trip or trip.user_id != user_id:
            return jsonify({"error": "Trip not found"}), 404

        # Check for existing review
        existing = (
            db.session.query(Feedback)
            .filter_by(itinerary_id=trip_id, user_id=user_id, poi_id=None)
            .first()
        )
        if existing:
            return jsonify({"error": "Review already exists. Use PUT to update."}), 409

        review = Feedback(
            user_id=user_id,
            itinerary_id=trip_id,
            rating=rating,
            corrections={"tags": tags},
            comment=comment or None,
        )
        db.session.add(review)

        # Update Trip.quality_score with reviewer's rating (blend 80% existing + 20% new)
        if trip.quality_score is not None:
            trip.quality_score = round(trip.quality_score * 0.8 + (rating / 5.0 * 100) * 0.2, 2)
        else:
            trip.quality_score = round((rating / 5.0) * 100, 2)

        db.session.commit()
        log.info("trip_review.submitted", trip_id=trip_id, user_id=user_id, rating=rating)

        return jsonify({
            "id": review.id,
            "trip_id": trip_id,
            "rating": rating,
            "tags": tags,
            "comment": comment or None,
            "message": "Review submitted. Thank you for your feedback!",
        }), 201

    except Exception:
        db.session.rollback()
        log.exception("trip_review.submit_failed")
        return jsonify({"error": "Internal server error", "request_id": getattr(g, "request_id", None)}), 500


@feedback_bp.route("/api/trip/<int:trip_id>/review", methods=["GET"])
@jwt_required()
def get_trip_review(trip_id: int):
    """Get the current user's review for a trip."""
    user_id = _safe_user_id()
    if user_id is None:
        return jsonify({"error": "Unauthorized"}), 401

    try:
        trip = db.session.get(Trip, trip_id)
        if not trip or trip.user_id != user_id:
            return jsonify({"error": "Trip not found"}), 404

        review = (
            db.session.query(Feedback)
            .filter_by(itinerary_id=trip_id, user_id=user_id, poi_id=None)
            .first()
        )
        if not review:
            return jsonify({"review": None}), 200

        return jsonify({"review": _serialize_review(review)}), 200

    except Exception:
        log.exception("trip_review.fetch_failed")
        return jsonify({"error": "Internal server error"}), 500


@feedback_bp.route("/api/trip/<int:trip_id>/review", methods=["PUT"])
@jwt_required()
@limiter.limit("10 per minute")
def update_trip_review(trip_id: int):
    """Update an existing trip review."""
    user_id = _safe_user_id()
    if user_id is None:
        return jsonify({"error": "Unauthorized"}), 401

    body = request.get_json() or {}

    try:
        trip = db.session.get(Trip, trip_id)
        if not trip or trip.user_id != user_id:
            return jsonify({"error": "Trip not found"}), 404

        review = (
            db.session.query(Feedback)
            .filter_by(itinerary_id=trip_id, user_id=user_id, poi_id=None)
            .first()
        )
        if not review:
            return jsonify({"error": "No review found. Use POST to create one."}), 404

        if "rating" in body:
            rating, err = _validate_rating(body["rating"])
            if err:
                return jsonify({"error": err}), 400
            review.rating = rating
            # Re-blend quality score
            if trip.quality_score is not None:
                trip.quality_score = round(trip.quality_score * 0.8 + (rating / 5.0 * 100) * 0.2, 2)
            else:
                trip.quality_score = round((rating / 5.0) * 100, 2)

        if "tags" in body:
            tags, err = _validate_tags(body["tags"])
            if err:
                return jsonify({"error": err}), 400
            review.corrections = {**(review.corrections or {}), "tags": tags}

        if "comment" in body:
            comment = body["comment"] or ""
            if len(comment) > _MAX_COMMENT_LEN:
                return jsonify({"error": f"comment must be under {_MAX_COMMENT_LEN} characters"}), 400
            review.comment = comment or None

        db.session.commit()
        log.info("trip_review.updated", trip_id=trip_id, user_id=user_id)
        return jsonify({"review": _serialize_review(review), "message": "Review updated."}), 200

    except Exception:
        db.session.rollback()
        log.exception("trip_review.update_failed")
        return jsonify({"error": "Internal server error"}), 500


# ── Attraction Reviews ─────────────────────────────────────────────────────────


@feedback_bp.route("/api/attraction/<int:attraction_id>/review", methods=["POST"])
@jwt_required()
@limiter.limit("20 per minute")
def submit_attraction_review(attraction_id: int):
    """Rate an individual attraction visited during a trip."""
    user_id = _safe_user_id()
    if user_id is None:
        return jsonify({"error": "Unauthorized"}), 401

    body = request.get_json() or {}
    rating, err = _validate_rating(body.get("rating"))
    if err:
        return jsonify({"error": err}), 400

    comment = body.get("comment", "")
    if comment and len(comment) > _MAX_COMMENT_LEN:
        return jsonify({"error": f"comment must be under {_MAX_COMMENT_LEN} characters"}), 400

    try:
        attraction = db.session.get(Attraction, attraction_id)
        if not attraction:
            return jsonify({"error": "Attraction not found"}), 404

        # Prevent duplicate reviews per user per attraction
        existing = (
            db.session.query(Feedback)
            .filter_by(poi_id=attraction_id, user_id=user_id)
            .first()
        )
        if existing:
            # Update instead of duplicate
            existing.rating = rating
            existing.comment = comment or None
            db.session.commit()
            _update_attraction_rating(attraction, rating)
            db.session.commit()
            log.info("attraction_review.updated", attraction_id=attraction_id, rating=rating)
            return jsonify({"message": "Review updated.", "rating": rating}), 200

        review = Feedback(
            user_id=user_id,
            poi_id=attraction_id,
            rating=rating,
            comment=comment or None,
        )
        db.session.add(review)

        # Blend user rating into attraction.google_rating (rolling average)
        _update_attraction_rating(attraction, rating)
        db.session.commit()

        log.info("attraction_review.submitted", attraction_id=attraction_id, rating=rating)
        return jsonify({"message": "Attraction rated. Thanks!", "rating": rating}), 201

    except Exception:
        db.session.rollback()
        log.exception("attraction_review.failed")
        return jsonify({"error": "Internal server error"}), 500


def _update_attraction_rating(attraction: Attraction, new_rating: float):
    """Blend a new user rating into the attraction's google_rating using exponential moving average."""
    review_count = (attraction.review_count or 0) + 1
    existing_rating = attraction.google_rating or attraction.rating or new_rating
    # Exponential moving average — newer ratings have slightly more weight
    alpha = min(0.1, 1.0 / review_count)
    attraction.google_rating = round(existing_rating * (1 - alpha) + new_rating * alpha, 2)
    attraction.review_count = review_count


# ── Destination Aggregate Reviews ─────────────────────────────────────────────


@feedback_bp.route("/api/destination/<int:destination_id>/reviews", methods=["GET"])
@limiter.limit("60 per minute")
def get_destination_reviews(destination_id: int):
    """
    Return aggregated attraction reviews for a destination.
    Public endpoint — no auth required.
    """
    try:
        destination = db.session.get(Destination, destination_id)
        if not destination:
            return jsonify({"error": "Destination not found"}), 404

        # Get all attractions for this destination that have reviews
        attractions = (
            db.session.query(Attraction)
            .filter_by(destination_id=destination_id)
            .filter(Attraction.review_count > 0)
            .order_by(Attraction.google_rating.desc())
            .limit(20)
            .all()
        )

        rated_attractions = [
            {
                "attraction_id": a.id,
                "name": a.name,
                "rating": a.google_rating or a.rating,
                "review_count": a.review_count,
                "type": a.type,
            }
            for a in attractions
        ]

        # Aggregate destination-level trip reviews
        trip_reviews = (
            db.session.query(Feedback)
            .join(Trip, Feedback.itinerary_id == Trip.id)
            .filter(
                Trip.destination_country == destination.name,
                Feedback.poi_id.is_(None),
                Feedback.rating.isnot(None),
            )
            .limit(50)
            .all()
        )

        avg_trip_rating = None
        if trip_reviews:
            avg_trip_rating = round(sum(r.rating for r in trip_reviews) / len(trip_reviews), 2)

        return jsonify({
            "destination_id": destination_id,
            "destination_name": destination.name,
            "trip_rating": {
                "average": avg_trip_rating,
                "count": len(trip_reviews),
            },
            "top_rated_attractions": rated_attractions,
        }), 200

    except Exception:
        log.exception("destination_reviews.fetch_failed")
        return jsonify({"error": "Internal server error"}), 500


# ── Private helpers ────────────────────────────────────────────────────────────


def _serialize_review(review: Feedback) -> dict:
    corrections = review.corrections or {}
    return {
        "id": review.id,
        "rating": review.rating,
        "tags": corrections.get("tags", []),
        "comment": review.comment,
        "created_at": review.created_at.isoformat() if review.created_at else None,
    }
