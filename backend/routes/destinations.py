"""
destinations.py — Routes for countries, destinations, destination requests, and budget calculation.
"""
import os

from flask import Blueprint, request, jsonify
from backend.database import db
from backend.models import Country, Destination, Attraction, DestinationRequest
from backend.request_validation import load_request_json
from backend.schemas import CalculateBudgetSchema, DestinationRequestSchema
from backend.extensions import limiter
from backend.constants import PAGINATION_MAX_PAGE
from backend.utils.responses import normalize_api_response

destinations_bp = Blueprint('destinations', __name__)


@destinations_bp.after_request
def _normalize_destinations_response(response):
    return normalize_api_response(response)

# Style cost multipliers — read from env so they can be overridden at deploy time
# without a code change.  The Settings page can expose these as writable engine config.
_DEFAULT_MULTIPLIERS = {"budget": 0.7, "standard": 1.0, "luxury": 1.8}


def _style_multipliers() -> dict:
    """
    Return style multipliers, allowing individual overrides via env vars.
    e.g. STYLE_MULTIPLIER_LUXURY=2.0 overrides the luxury multiplier.
    """
    return {
        "budget": float(os.getenv("STYLE_MULTIPLIER_BUDGET", "0.7")),
        "standard": float(os.getenv("STYLE_MULTIPLIER_STANDARD", "1.0")),
        "luxury": float(os.getenv("STYLE_MULTIPLIER_LUXURY", "1.8")),
    }


def _validate_page(page: int) -> tuple[int, str | None]:
    """Clamp and validate page number.  Returns (safe_page, error_message_or_None)."""
    page = max(page, 1)
    if page > PAGINATION_MAX_PAGE:
        return page, f"page must be <= {PAGINATION_MAX_PAGE}"
    return page, None


# ── Countries ────────────────────────────────────────────────────
@destinations_bp.route('/countries', methods=['GET'])
@limiter.limit("30 per minute")
def list_countries():
    countries = db.session.query(Country).all()
    return jsonify([{
        "id": c.id,
        "name": c.name,
        "code": c.code,
        "currency": getattr(c, 'currency', None),
        "image": getattr(c, 'image', None),
    } for c in countries]), 200


# ── Destinations ─────────────────────────────────────────────────
@destinations_bp.route('/destinations', methods=['GET'])
@limiter.limit("30 per minute")
def list_destinations():
    query = db.session.query(Destination)

    tag = request.args.get('tag')
    if tag:
        query = query.filter(Destination.tag == tag)

    max_cost = request.args.get('max_cost', type=int)
    if max_cost:
        query = query.filter(Destination.estimated_cost_per_day <= max_cost)

    raw_page = request.args.get("page", type=int, default=1)
    page, page_err = _validate_page(raw_page)
    if page_err:
        return jsonify({"error": page_err}), 400

    page_size = min(request.args.get("page_size", type=int, default=50), 200)

    total = query.count()
    destinations = query.limit(page_size).offset((page - 1) * page_size).all()

    return jsonify({
        "items": [_serialize_destination(d) for d in destinations],
        "page": page,
        "page_size": page_size,
        "total": total,
        "total_pages": -(-total // page_size),
    }), 200


@destinations_bp.route('/destinations/<int:dest_id>', methods=['GET'])
def destination_detail(dest_id):
    dest = db.session.get(Destination, dest_id)
    if not dest:
        return jsonify({"error": "Destination not found"}), 404

    data = _serialize_destination(dest)
    # Include attractions — paginated to prevent OOM on large OSM imports.
    raw_attr_page = request.args.get("attr_page", type=int, default=1)
    attr_page, page_err = _validate_page(raw_attr_page)
    if page_err:
        return jsonify({"error": page_err}), 400

    attr_limit = min(request.args.get("attr_limit", type=int, default=50), 200)
    attractions = (
        db.session.query(Attraction)
        .filter_by(destination_id=dest_id)
        .order_by(Attraction.popularity_score.desc(), Attraction.rating.desc())
        .limit(attr_limit)
        .offset((attr_page - 1) * attr_limit)
        .all()
    )
    data["attractions"] = [{
        "id": a.id,
        "name": a.name,
        "description": a.description,
        "type": a.type,
        "rating": a.rating,
        "entry_cost": a.entry_cost,
        "duration": a.duration,
        "popularity_score": a.popularity_score,
        "images": a.gallery_images or [],
    } for a in attractions]

    return jsonify(data), 200


# ── Destination Request ──────────────────────────────────────────
@destinations_bp.route('/api/destination-request', methods=['POST'])
def submit_destination_request():
    data, error = load_request_json(DestinationRequestSchema())
    if error:
        return error

    # Prevent duplicate pending requests for the same destination name
    existing = db.session.query(DestinationRequest).filter_by(
        name=data["name"],
        status="pending",
    ).first()
    if existing:
        return jsonify({
            "message": "A pending request for this destination already exists.",
            "id": existing.id,
        }), 200

    req = DestinationRequest(
        name=data["name"],
        description=data.get("description"),
        cost=data.get("cost"),
        tag=data.get("tag"),
    )
    db.session.add(req)
    db.session.commit()
    return jsonify({"message": "Request submitted", "id": req.id}), 201


# ── Budget Calculation ───────────────────────────────────────────
@destinations_bp.route('/calculate-budget', methods=['POST'])
def calculate_budget():
    data, error = load_request_json(CalculateBudgetSchema())
    if error:
        return error
    selected = data.get("selected_destinations", [])
    duration = data.get("duration", 1)
    travelers = data.get("travelers", 1)
    style = data.get("style", "standard")

    total = 0
    for dest_info in selected:
        dest = db.session.get(Destination, dest_info.get("id"))
        if dest and dest.estimated_cost_per_day:
            total += dest.estimated_cost_per_day

    # Average cost per day across destinations, multiplied by days & travelers
    avg_per_day = total / max(len(selected), 1)
    multiplier = _style_multipliers().get(style, 1.0)
    estimated_budget = int(avg_per_day * duration * travelers * multiplier)

    return jsonify({"estimated_budget": estimated_budget}), 200


# ── Helpers ──────────────────────────────────────────────────────
def _serialize_destination(d):
    return {
        "id": d.id,
        "name": d.name,
        "slug": d.slug,
        "desc": d.desc,
        "description": d.description,
        "image": d.image,
        "location": d.location,
        "estimated_cost_per_day": d.estimated_cost_per_day,
        "rating": d.rating,
        "tag": d.tag,
        "highlights": d.highlights,
        "best_time_months": d.best_time_months,
        "vibe_tags": d.vibe_tags,
    }
