"""
routes/discover.py — Traveler Discovery & Planning Assistant
════════════════════════════════════════════════════════════

Answers the questions every traveler asks BEFORE they know their destination:

  GET  /api/discover/recommend
       "Where should I go?" — Ranks destinations by budget fit, seasonal
       suitability, traveler type, and declared interests.

  GET  /api/discover/best-time/<dest_id>
       "When is the best time to visit?" — Month-by-month score matrix with
       a plain-language verdict for the given (or current) month.

  GET  /api/discover/is-good-time?dest_id=X&month=apr
       Quick yes/no: "Is April a good time to visit this place?"

  POST /api/discover/estimate-budget
       "How much will this trip cost?" — Detailed breakdown before committing
       to full itinerary generation.

  POST /api/discover/compare
       "Should I do Goa or Kerala?" — Side-by-side destination comparison.
"""

import json
from datetime import datetime

import structlog
from flask import Blueprint, jsonify, request

from backend.database import db
from backend.extensions import limiter
from backend.models import Attraction, Destination, DestinationInfo, HotelPrice, State

_MAX_DEST_IDS = 10  # Maximum destination IDs accepted in a single estimate-budget call

discover_bp = Blueprint("discover", __name__)
log = structlog.get_logger(__name__)

# Month name ↔ short-key mapping (seasonal_score keys are 3-letter lowercase)
_MONTH_MAP = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}
_MONTH_NAMES = {v: k for k, v in _MONTH_MAP.items()}

_VERDICT = {
    (85, 100): ("Excellent", "Peak season — ideal conditions, high demand."),
    (65, 84):  ("Good",      "Great time to visit with mostly favourable conditions."),
    (45, 64):  ("Fair",      "Acceptable conditions but not ideal; some limitations."),
    (0, 44):   ("Avoid",     "Off-season or monsoon — many attractions may be inaccessible."),
}

_STYLE_TO_BUDGET_CATEGORY = {
    "budget": "budget",
    "standard": "mid-range",
    "mid": "mid-range",
    "luxury": "luxury",
}

# Budget tier splits for quick estimation (fraction of total budget)
_TIER_SPLITS = {
    "budget":   {"accommodation": 0.30, "food": 0.28, "transport": 0.22, "activities": 0.15, "misc": 0.05},
    "standard": {"accommodation": 0.35, "food": 0.25, "transport": 0.20, "activities": 0.15, "misc": 0.05},
    "mid":      {"accommodation": 0.35, "food": 0.25, "transport": 0.20, "activities": 0.15, "misc": 0.05},
    "luxury":   {"accommodation": 0.45, "food": 0.20, "transport": 0.15, "activities": 0.15, "misc": 0.05},
}


def _seasonal_score_for_month(destination: Destination, month_key: str) -> int:
    """
    Compute a composite seasonal score for a destination in a given month.
    Uses the destination's attraction pool to get a richer signal than any
    single seasonal_score field.
    Returns 0-100.
    """
    # Destination-level seasonal score (used as a baseline if attractions are absent)
    dest_seasonal: dict = getattr(destination, "seasonal_score", {}) or {}
    dest_score = dest_seasonal.get(month_key, 70)  # default 70 = permissive

    # Average attraction seasonal scores for a richer signal
    try:
        attractions = (
            db.session.query(Attraction.seasonal_score)
            .filter_by(destination_id=destination.id)
            .limit(50)
            .all()
        )
        scores = []
        for (ss,) in attractions:
            if ss and isinstance(ss, dict):
                scores.append(ss.get(month_key, 70) or 70)
        if scores:
            return int((dest_score + sum(scores) / len(scores)) / 2)
    except Exception:
        pass

    return int(dest_score)


def _score_destination(dest: Destination, params: dict) -> float:
    """
    Score a destination against traveler preferences.
    Higher = better match.
    """
    score = float(getattr(dest, "popularity_score", 50) or 50)

    # Seasonal suitability
    month_key = params.get("month")
    if month_key:
        seasonal = _seasonal_score_for_month(dest, month_key)
        score += seasonal * 0.5  # seasonal weight

    # Rating bonus
    rating = getattr(dest, "rating", None)
    if rating:
        score += float(rating) * 5

    # Budget category match
    style = params.get("style", "standard")
    desired_cat = _STYLE_TO_BUDGET_CATEGORY.get(style, "mid-range")
    dest_cat = getattr(dest, "budget_category", "mid-range") or "mid-range"
    if dest_cat == desired_cat:
        score += 20
    elif dest_cat == "mid-range":  # always somewhat compatible
        score += 5

    # Traveler type compatibility
    traveler_type = params.get("traveler_type")
    if traveler_type:
        compat = getattr(dest, "compatible_traveler_types", []) or []
        if isinstance(compat, str):
            try:
                compat = json.loads(compat)
            except Exception:
                compat = []
        if traveler_type in compat:
            score += 15

    # Interest / vibe tag overlap
    interests = params.get("interests") or []
    vibe_tags: list = getattr(dest, "vibe_tags", []) or []
    tag: str = (getattr(dest, "tag", "") or "").lower()
    combined_tags = {t.lower() for t in vibe_tags} | {tag}
    for interest in interests:
        if interest.lower() in combined_tags or any(interest.lower() in t for t in combined_tags):
            score += 10

    # Budget affordability
    budget = params.get("budget")
    duration = params.get("duration", 3)
    travelers = params.get("travelers", 1)
    cost_per_day = getattr(dest, "estimated_cost_per_day", None)
    if budget and cost_per_day:
        total_needed = cost_per_day * duration * travelers
        if total_needed <= budget:
            score += 25  # comfortably affordable
        elif total_needed <= budget * 1.2:
            score += 10  # slightly over budget but doable

    return score


def _verdict_for_score(score: int) -> tuple[str, str]:
    for (low, high), (label, desc) in _VERDICT.items():
        if low <= score <= high:
            return label, desc
    return "Unknown", "No seasonal data available."


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    """Compute cosine similarity between two vectors. Returns 0.0 on error."""
    try:
        if not a or not b or len(a) != len(b):
            return 0.0
        dot = sum(x * y for x, y in zip(a, b))
        mag_a = sum(x * x for x in a) ** 0.5
        mag_b = sum(x * x for x in b) ** 0.5
        if mag_a == 0 or mag_b == 0:
            return 0.0
        return dot / (mag_a * mag_b)
    except Exception:
        return 0.0


def _apply_semantic_ranking(scored: list, query: str) -> list:
    """
    Blend cosine similarity into existing scores when embeddings are available.
    Falls back to the original scored list if embedding generation fails.
    Blend: existing_score * 0.6 + similarity * 100 * 0.4
    """
    import os
    api_key = os.getenv("GEMINI_API_KEY", "")
    if not api_key:
        return scored

    # Check if any destination has an embedding
    has_embeddings = any(
        getattr(dest, "embedding", None) is not None
        for dest, _ in scored[:5]  # Quick sample check
    )
    if not has_embeddings:
        return scored

    try:
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        result = genai.embed_content(
            model="models/text-embedding-004",
            content=query,
            task_type="SEMANTIC_SIMILARITY",
        )
        query_vector = result["embedding"]
    except Exception:
        return scored  # Fallback — don't break recommendations

    reranked = []
    for dest, base_score in scored:
        dest_embedding = getattr(dest, "embedding", None)
        if dest_embedding is not None:
            try:
                # embedding may be stored as string in SQLite tests
                if isinstance(dest_embedding, str):
                    import json as _json
                    dest_embedding = _json.loads(dest_embedding)
                sim = _cosine_similarity(query_vector, dest_embedding)
                blended = base_score * 0.6 + sim * 100 * 0.4
            except Exception:
                blended = base_score
        else:
            blended = base_score * 0.6  # Slight penalty for missing embedding
        reranked.append((dest, blended))

    return reranked


# ── Routes ────────────────────────────────────────────────────────────────────


@discover_bp.route("/api/discover/recommend", methods=["GET"])
def recommend_destinations():
    """
    Smart destination recommendations based on budget, duration, style,
    traveler type, month, and interests.

    Query params (all optional):
      budget       — total trip budget in INR
      duration     — trip length in days
      travelers    — number of travelers
      style        — budget / standard / luxury
      traveler_type — solo / couple / family / group
      month        — jan…dec  (defaults to current month)
      interests    — comma-separated: "beaches,history,food"
      state        — filter by state name (partial match)
      limit        — max results (default 10, max 50)
    """
    budget = request.args.get("budget", type=float)
    if budget is not None and budget <= 0:
        return jsonify({"error": "budget must be greater than 0"}), 400

    duration = request.args.get("duration", type=int, default=3)
    travelers = request.args.get("travelers", type=int, default=1)
    style = request.args.get("style", "standard")
    traveler_type = request.args.get("traveler_type")
    month_raw = request.args.get("month") or _MONTH_NAMES.get(datetime.now().month, "jan")
    month_key = month_raw[:3].lower() if month_raw else None
    interests_raw = request.args.get("interests", "")
    interests = [i.strip().lower() for i in interests_raw.split(",") if i.strip()] if interests_raw else []
    state_filter = request.args.get("state", "")
    limit = min(request.args.get("limit", type=int, default=10), 50)
    # Optional semantic query — e.g. "peaceful hill station with old temples"
    semantic_query = (request.args.get("q") or "").strip()[:300]

    params = {
        "budget": budget,
        "duration": duration,
        "travelers": travelers,
        "style": style,
        "traveler_type": traveler_type,
        "month": month_key,
        "interests": interests,
    }

    try:
        query = db.session.query(Destination)
        if state_filter:
            matching_states = db.session.query(State).filter(
                State.name.ilike(f"%{state_filter}%")
            ).all()
            state_ids = [s.id for s in matching_states]
            if state_ids:
                query = query.filter(Destination.state_id.in_(state_ids))

        destinations = query.all()

        scored = []
        for dest in destinations:
            # Hard gate: skip destinations where the month is genuinely off-season
            if month_key:
                s_score = _seasonal_score_for_month(dest, month_key)
                if s_score < 30:  # absolute floor — "do not visit" level
                    continue

            # Hard gate: skip if budget is set and destination is clearly too expensive
            cost_per_day = getattr(dest, "estimated_cost_per_day", None)
            if budget and cost_per_day:
                total_needed = cost_per_day * duration * travelers
                if total_needed > budget * 1.5:  # allow 50% buffer in recommendations
                    continue

            final_score = _score_destination(dest, params)
            scored.append((dest, final_score))

        # ── Semantic re-ranking (optional) ───────────────────────────────────
        # When a free-text query is provided AND destination embeddings exist,
        # blend cosine similarity into the score for semantic relevance.
        if semantic_query:
            scored = _apply_semantic_ranking(scored, semantic_query)

        scored.sort(key=lambda x: x[1], reverse=True)
        top = scored[:limit]

        results = []
        for dest, score in top:
            month_score = _seasonal_score_for_month(dest, month_key) if month_key else 70
            verdict_label, verdict_desc = _verdict_for_score(month_score)

            # "Why this fits you" explanation
            reasons = []
            if month_score >= 65:
                reasons.append(f"{month_key.upper() if month_key else 'This month'} is a {verdict_label.lower()} time to visit.")
            cost_per_day = getattr(dest, "estimated_cost_per_day", None)
            if cost_per_day and budget:
                total_est = cost_per_day * duration * travelers
                reasons.append(f"Estimated cost: ₹{total_est:,} for {duration}d × {travelers} person(s) — {'within' if total_est <= budget else 'slightly over'} budget.")
            vibe_tags = getattr(dest, "vibe_tags", []) or []
            matched_vibes = [v for v in vibe_tags if any(i in v.lower() for i in interests)]
            if matched_vibes:
                reasons.append(f"Matches your interests: {', '.join(matched_vibes[:3])}.")
            if not reasons:
                reasons.append(f"Popular destination with a {(getattr(dest, 'rating') or 4):.1f}★ rating.")

            results.append({
                "id": dest.id,
                "name": dest.name,
                "location": dest.location,
                "image": dest.image,
                "tag": dest.tag,
                "vibe_tags": vibe_tags,
                "rating": dest.rating,
                "estimated_cost_per_day": cost_per_day,
                "estimated_trip_cost_inr": int(cost_per_day * duration * travelers) if cost_per_day else None,
                "best_time_months": getattr(dest, "best_time_months", []) or [],
                "seasonal_verdict": {"label": verdict_label, "description": verdict_desc, "score": month_score},
                "highlights": getattr(dest, "highlights", []) or [],
                "why_this_fits": reasons,
                "match_score": round(score, 1),
            })

        return jsonify({
            "query": {
                "budget": budget,
                "duration": duration,
                "travelers": travelers,
                "style": style,
                "traveler_type": traveler_type,
                "month": month_key,
                "interests": interests,
            },
            "recommendations": results,
            "total": len(results),
        }), 200

    except Exception:
        log.exception("discover.recommend_failed")
        return jsonify({"error": "Internal server error"}), 500


@discover_bp.route("/api/discover/best-time/<int:dest_id>", methods=["GET"])
def best_time_for_destination(dest_id: int):
    """
    Full month-by-month seasonal suitability for a destination.
    Returns a score (0-100) and verdict for each month, plus the
    top 3 recommended months.
    """
    dest = db.session.get(Destination, dest_id)
    if not dest:
        return jsonify({"error": "Destination not found"}), 404

    try:
        monthly = {}
        for month_key, month_num in _MONTH_MAP.items():
            score = _seasonal_score_for_month(dest, month_key)
            verdict_label, verdict_desc = _verdict_for_score(score)
            monthly[month_key] = {
                "month": month_key,
                "month_number": month_num,
                "score": score,
                "verdict": verdict_label,
                "description": verdict_desc,
            }

        # Top 3 best months
        best = sorted(monthly.values(), key=lambda x: x["score"], reverse=True)[:3]

        # Current month indicator
        current_month = _MONTH_NAMES.get(datetime.now().month, "jan")
        current_verdict = monthly.get(current_month, {})

        return jsonify({
            "destination": {"id": dest.id, "name": dest.name, "location": dest.location},
            "monthly_guide": monthly,
            "best_months": [m["month"] for m in best],
            "current_month": {
                "month": current_month,
                "verdict": current_verdict.get("verdict"),
                "score": current_verdict.get("score"),
                "recommendation": (
                    "Now is a great time to visit!" if current_verdict.get("score", 0) >= 65
                    else "Consider a different time — not ideal right now."
                ),
            },
            "best_time_note": getattr(dest, "best_time_months", None) or [],
        }), 200

    except Exception:
        log.exception("discover.best_time_failed")
        return jsonify({"error": "Internal server error"}), 500


@discover_bp.route("/api/discover/is-good-time", methods=["GET"])
def is_good_time():
    """
    Quick check: is a specific month a good time to visit a destination?

    Query params:
      dest_id  — required
      month    — e.g. "apr" (defaults to current month)
    """
    dest_id = request.args.get("dest_id", type=int)
    if not dest_id:
        return jsonify({"error": "dest_id is required"}), 400

    dest = db.session.get(Destination, dest_id)
    if not dest:
        return jsonify({"error": "Destination not found"}), 404

    month_raw = request.args.get("month") or _MONTH_NAMES.get(datetime.now().month, "jan")
    month_key = month_raw[:3].lower()

    score = _seasonal_score_for_month(dest, month_key)
    verdict_label, verdict_desc = _verdict_for_score(score)

    # Find best alternative month
    best_month = month_key
    best_score = score
    for mk in _MONTH_MAP:
        s = _seasonal_score_for_month(dest, mk)
        if s > best_score:
            best_score = s
            best_month = mk

    return jsonify({
        "destination": dest.name,
        "month": month_key,
        "score": score,
        "verdict": verdict_label,
        "description": verdict_desc,
        "good_to_go": score >= 65,
        "best_month_instead": best_month if best_month != month_key else None,
        "best_month_score": best_score if best_month != month_key else None,
        "tip": (
            f"Great time to visit {dest.name}!"
            if score >= 65 else
            f"Consider visiting in {best_month.upper()} instead (score: {best_score}/100)."
        ),
    }), 200


@discover_bp.route("/api/discover/estimate-budget", methods=["POST"])
@limiter.limit("30 per minute")
def estimate_budget():
    """
    Detailed budget estimate before generating a full itinerary.

    Body:
      destination_ids: [int, ...]   — required
      duration:        int           — required
      travelers:       int           — default 1
      style:           str           — budget / standard / luxury
    """
    body = request.get_json() or {}
    dest_ids = body.get("destination_ids", [])
    duration = body.get("duration", 3)
    travelers = body.get("travelers", 1)
    style = (body.get("style") or "standard").lower()

    if not dest_ids or not isinstance(dest_ids, list):
        return jsonify({"error": "destination_ids (list) is required"}), 400
    if len(dest_ids) > _MAX_DEST_IDS:
        return jsonify({"error": f"destination_ids may contain at most {_MAX_DEST_IDS} IDs"}), 400
    if not 1 <= duration <= 60:
        return jsonify({"error": "duration must be 1–60"}), 400
    if not 1 <= travelers <= 50:
        return jsonify({"error": "travelers must be 1–50"}), 400

    try:
        destinations = db.session.query(Destination).filter(
            Destination.id.in_(dest_ids)
        ).all()

        if not destinations:
            return jsonify({"error": "No destinations found for given IDs"}), 404

        splits = _TIER_SPLITS.get(style, _TIER_SPLITS["standard"])

        # Average estimated_cost_per_day across selected destinations
        costs = [d.estimated_cost_per_day for d in destinations if d.estimated_cost_per_day]
        avg_cost_per_day = int(sum(costs) / len(costs)) if costs else 3000

        # Try to get a real hotel price if available
        primary_dest = destinations[0]
        hotel_cost_per_night = None
        hotel_name = None
        try:
            hotel = db.session.query(HotelPrice).filter_by(
                destination_id=primary_dest.id,
                category=_style_to_hotel_cat(style),
            ).order_by(HotelPrice.last_synced.desc()).first()
            if hotel:
                hotel_cost_per_night = hotel.price_per_night_min
                hotel_name = hotel.hotel_name
        except Exception:
            pass

        # Base calculation: avg_cost_per_day already includes a rough blend
        base_total = avg_cost_per_day * duration * travelers
        multiplier = {"budget": 0.7, "standard": 1.0, "mid": 1.0, "luxury": 1.8}.get(style, 1.0)
        estimated_total = int(base_total * multiplier)

        # Breakdown per category
        breakdown = {
            cat: int(estimated_total * pct)
            for cat, pct in splits.items()
        }

        # Override accommodation with real hotel data if available
        if hotel_cost_per_night:
            accom_real = hotel_cost_per_night * duration * travelers
            breakdown["accommodation"] = int(accom_real)
            # Rebalance total
            estimated_total = sum(breakdown.values())

        # Per-day breakdown
        per_day = {cat: int(v / duration) for cat, v in breakdown.items()}

        # Group discount
        discount_pct = 0.0
        if travelers >= 10:
            discount_pct = 0.15
        elif travelers >= 5:
            discount_pct = 0.10
        if discount_pct:
            breakdown["activities"] = int(breakdown["activities"] * (1 - discount_pct))
            estimated_total = sum(breakdown.values())

        return jsonify({
            "destinations": [{"id": d.id, "name": d.name} for d in destinations],
            "duration": duration,
            "travelers": travelers,
            "style": style,
            "estimated_total_inr": estimated_total,
            "per_person_inr": int(estimated_total / travelers),
            "per_day_inr": int(estimated_total / duration),
            "breakdown": breakdown,
            "per_day_breakdown": per_day,
            "hotel_used": hotel_name,
            "hotel_cost_per_night": hotel_cost_per_night,
            "group_discount_applied": f"{int(discount_pct * 100)}%" if discount_pct else None,
            "note": (
                "This is an estimate. The actual itinerary cost may vary based on "
                "specific attractions, season, and availability."
            ),
        }), 200

    except Exception:
        log.exception("discover.estimate_budget_failed")
        return jsonify({"error": "Internal server error"}), 500


@discover_bp.route("/api/discover/compare", methods=["POST"])
def compare_destinations():
    """
    Side-by-side destination comparison to help choose between options.

    Body:
      destination_ids: [int, int, ...]   — 2 to 5 destinations
      budget:          float              — optional
      duration:        int
      travelers:       int
      style:           str
      month:           str               — e.g. "apr"
      traveler_type:   str
    """
    body = request.get_json() or {}
    dest_ids = body.get("destination_ids", [])
    budget = body.get("budget")
    duration = body.get("duration", 3)
    travelers = body.get("travelers", 1)
    style = body.get("style", "standard")
    month_raw = body.get("month") or _MONTH_NAMES.get(datetime.now().month, "jan")
    month_key = month_raw[:3].lower()
    traveler_type = body.get("traveler_type")

    if not dest_ids or len(dest_ids) < 2:
        return jsonify({"error": "Provide at least 2 destination_ids to compare"}), 400
    if len(dest_ids) > 5:
        return jsonify({"error": "Maximum 5 destinations can be compared at once"}), 400

    try:
        destinations = db.session.query(Destination).filter(
            Destination.id.in_(dest_ids)
        ).all()

        if len(destinations) < 2:
            return jsonify({"error": "Could not find enough destinations for comparison"}), 404

        params = {
            "budget": budget, "duration": duration, "travelers": travelers,
            "style": style, "month": month_key, "traveler_type": traveler_type, "interests": [],
        }

        comparison = []
        for dest in destinations:
            seasonal_score = _seasonal_score_for_month(dest, month_key)
            verdict_label, _ = _verdict_for_score(seasonal_score)
            cost_per_day = getattr(dest, "estimated_cost_per_day", None)
            total_est = int(cost_per_day * duration * travelers) if cost_per_day else None
            match_score = _score_destination(dest, params)

            # Traveler type fit
            compat = getattr(dest, "compatible_traveler_types", []) or []
            if isinstance(compat, str):
                try:
                    compat = json.loads(compat)
                except Exception:
                    compat = []
            type_fit = traveler_type in compat if (traveler_type and compat) else None

            # Attraction type diversity
            try:
                types = db.session.query(Attraction.type).filter_by(
                    destination_id=dest.id
                ).limit(100).all()
                type_counts: dict[str, int] = {}
                for (t,) in types:
                    if t:
                        type_counts[t] = type_counts.get(t, 0) + 1
                top_types = sorted(type_counts.items(), key=lambda x: x[1], reverse=True)[:5]
            except Exception:
                top_types = []

            # DestinationInfo safety
            try:
                dest_info = db.session.query(DestinationInfo).filter_by(
                    destination_id=dest.id
                ).first()
                safety_level = getattr(dest_info, "travel_advisory_level", 1) if dest_info else 1
            except Exception:
                safety_level = 1

            comparison.append({
                "id": dest.id,
                "name": dest.name,
                "location": dest.location,
                "image": dest.image,
                "tag": dest.tag,
                "rating": dest.rating,
                "popularity_score": getattr(dest, "popularity_score", 50),
                "estimated_cost_per_day": cost_per_day,
                "estimated_trip_cost_inr": total_est,
                "affordable": total_est <= budget if (total_est and budget) else None,
                "seasonal": {
                    "month": month_key,
                    "score": seasonal_score,
                    "verdict": verdict_label,
                },
                "best_time_months": getattr(dest, "best_time_months", []) or [],
                "traveler_type_fit": type_fit,
                "top_activity_types": [t for t, _ in top_types],
                "vibe_tags": getattr(dest, "vibe_tags", []) or [],
                "highlights": getattr(dest, "highlights", []) or [],
                "safety_advisory_level": safety_level,
                "match_score": round(match_score, 1),
            })

        # Rank them
        comparison.sort(key=lambda x: x["match_score"], reverse=True)
        winner = comparison[0]

        return jsonify({
            "query": {"duration": duration, "travelers": travelers, "style": style, "month": month_key},
            "destinations": comparison,
            "recommendation": {
                "winner": winner["name"],
                "reason": (
                    f"{winner['name']} scores highest for your preferences — "
                    f"seasonal fit: {winner['seasonal']['verdict']}, "
                    f"{'within budget, ' if winner.get('affordable') else ''}"
                    f"rating: {winner.get('rating') or 'N/A'}★."
                ),
            },
        }), 200

    except Exception:
        log.exception("discover.compare_failed")
        return jsonify({"error": "Internal server error"}), 500


# ── Helpers ───────────────────────────────────────────────────────────────────

def _style_to_hotel_cat(style: str) -> str:
    return {"budget": "budget", "luxury": "luxury"}.get(style, "mid")
