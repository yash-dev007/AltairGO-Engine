"""
destinations.py — Routes for countries, destinations, destination requests, and budget calculation.
"""

from flask import Blueprint, request, jsonify
from backend.database import db
from backend.models import Country, Destination, Attraction, DestinationRequest
from backend.request_validation import load_request_json
from backend.schemas import CalculateBudgetSchema, DestinationRequestSchema
from backend.extensions import limiter

destinations_bp = Blueprint('destinations', __name__)


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

    page = max(request.args.get("page", type=int, default=1), 1)
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
    attr_page = max(request.args.get("attr_page", type=int, default=1), 1)
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
    } for a in attractions]

    return jsonify(data), 200


# ── Destination Request ──────────────────────────────────────────
@destinations_bp.route('/api/destination-request', methods=['POST'])
def submit_destination_request():
    # Validate destination requests so invalid body shapes return field-level errors.
    data, error = load_request_json(DestinationRequestSchema())
    if error:
        return error

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
STYLE_MULTIPLIERS = {"budget": 0.7, "standard": 1.0, "luxury": 1.8}


@destinations_bp.route('/calculate-budget', methods=['POST'])
def calculate_budget():
    # Validate budget calculation payloads so numeric fields never arrive as invalid strings.
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
    multiplier = STYLE_MULTIPLIERS.get(style, 1.0)
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
