"""Full-text search across destinations, countries, and attraction types."""
from flask import Blueprint, jsonify, request

from backend.database import db
from backend.models import Country, Destination, State

search_bp = Blueprint("search", __name__)


@search_bp.get("/api/search")
def search():
    q = (request.args.get("q") or "").strip()
    if len(q) < 2:
        return jsonify({"error": "Query must be at least 2 characters"}), 400
    if len(q) > 100:
        return jsonify({"error": "Query too long"}), 400

    limit = min(int(request.args.get("limit", 10)), 30)
    search_type = request.args.get("type", "all")  # all | destination | country

    results = []

    if search_type in ("all", "destination"):
        dests = (
            db.session.query(Destination)
            .filter(Destination.name.ilike(f"%{q}%"))
            .order_by(Destination.popularity_score.desc())
            .limit(limit)
            .all()
        )
        # Collect state_ids to avoid N+1
        state_ids = {d.state_id for d in dests if d.state_id}
        state_map = {}
        if state_ids:
            for s in db.session.query(State).filter(State.id.in_(state_ids)).all():
                state_map[s.id] = s.name

        for d in dests:
            results.append({
                "type": "destination",
                "id": d.id,
                "name": d.name,
                "slug": d.slug,
                "state": state_map.get(d.state_id),
                "budget_category": d.budget_category,
                "rating": d.rating,
                "image_url": d.image,
                "vibe_tags": d.vibe_tags,
            })

    if search_type in ("all", "country"):
        countries = (
            db.session.query(Country)
            .filter(Country.name.ilike(f"%{q}%"))
            .limit(limit)
            .all()
        )
        for c in countries:
            results.append({
                "type": "country",
                "id": c.id,
                "name": c.name,
                "code": c.code,
                "image": c.image,
            })

    # Sort: exact name match first, then prefix, then contains
    q_lower = q.lower()
    def sort_key(r):
        name = r["name"].lower()
        if name == q_lower:
            return 0
        if name.startswith(q_lower):
            return 1
        return 2

    results.sort(key=sort_key)
    return jsonify({"results": results[:limit], "query": q}), 200
