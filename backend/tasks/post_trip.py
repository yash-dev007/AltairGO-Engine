"""
tasks/post_trip.py — Post-Trip Summary Generator
══════════════════════════════════════════════════

Generates a post-trip summary for trips whose end date has passed.
Runs as a daily Celery task and can also be called per-trip from the API.

Summary output:
  - Days count + destinations visited
  - Planned vs actual spend (from ExpenseEntry)
  - Activity types experienced
  - Smart highlights (pulled from smart_insights)
  - Review prompt (if not reviewed yet)
  - Next-trip idea seed (from activity categories)
"""

import structlog
from datetime import date, datetime, timedelta

log = structlog.get_logger(__name__)


def generate_trip_summary(trip, db_session) -> dict:
    """
    Build a post-trip summary dict for a saved Trip object.
    Suitable for GET /api/trip/<id>/summary.
    """
    from backend.models import ExpenseEntry, Feedback

    itinerary = trip.itinerary_json or {}
    days = itinerary.get("itinerary", [])
    num_days = trip.duration or len(days)

    # Destinations from day locations
    destinations_visited = list({
        d.get("location") or d.get("destination", "")
        for d in days
        if d.get("location") or d.get("destination")
    })

    # Activity types experienced (for next-trip seeding)
    activity_types: list[str] = []
    total_activities = 0
    for day in days:
        for act in day.get("activities", []):
            if not act.get("is_break"):
                total_activities += 1
                t = act.get("type", "")
                if t:
                    activity_types.append(t)

    # Planned budget
    planned_total = trip.total_cost or trip.budget or 0
    cost_breakdown = itinerary.get("cost_breakdown", {})

    # Actual spend from ExpenseEntry
    actual_entries = (
        db_session.query(ExpenseEntry)
        .filter_by(trip_id=trip.id, user_id=trip.user_id)
        .all()
    )
    actual_total = sum(e.amount_inr for e in actual_entries)
    actual_by_category: dict[str, int] = {}
    for entry in actual_entries:
        actual_by_category[entry.category] = actual_by_category.get(entry.category, 0) + entry.amount_inr

    # Build planned vs actual comparison per category
    spend_comparison = {}
    if cost_breakdown and isinstance(cost_breakdown, dict):
        for cat, planned_amt in cost_breakdown.items():
            actual_amt = actual_by_category.get(cat, 0)
            spend_comparison[cat] = {
                "planned": planned_amt,
                "actual": actual_amt,
                "variance": actual_amt - (planned_amt or 0),
            }

    # Smart insights from the itinerary
    smart_insights = itinerary.get("smart_insights", [])

    # Highlights — top-rated or notable activities
    highlights = []
    for day in days:
        for act in day.get("activities", []):
            if not act.get("is_break") and act.get("is_photo_spot"):
                highlights.append(act.get("name") or act.get("activity", ""))
    highlights = list(dict.fromkeys(highlights))[:5]  # Deduplicate, take top 5

    # Check if user has already reviewed this trip
    has_review = (
        db_session.query(Feedback)
        .filter_by(itinerary_id=trip.id, user_id=trip.user_id, poi_id=None)
        .first()
    ) is not None

    # Category frequency for next-trip recommendations
    type_freq: dict[str, int] = {}
    for t in activity_types:
        type_freq[t] = type_freq.get(t, 0) + 1
    top_types = sorted(type_freq, key=lambda x: -type_freq[x])[:3]

    return {
        "trip_id": trip.id,
        "trip_title": trip.trip_title,
        "num_days": num_days,
        "destinations_visited": destinations_visited,
        "total_activities": total_activities,
        "highlights": highlights,
        # Top-level aliases expected by the frontend
        "planned_budget": planned_total,
        "actual_spend": actual_total,
        "budget": {
            "planned_total_inr": planned_total,
            "actual_total_inr": actual_total,
            "variance_inr": actual_total - planned_total,
            "on_budget": actual_total <= planned_total,
            "by_category": spend_comparison,
        },
        "smart_insights": smart_insights,
        "top_activity_types": top_types,
        "review": {
            "has_reviewed": has_review,
            "prompt": None if has_review else "How was your trip? Share your experience!",
        },
        "packing_tips": itinerary.get("packing_tips", []),
    }


def generate_post_trip_summaries() -> dict:
    """
    Daily Celery task: find trips that ended within the last 7 days and haven't
    been summarised yet, then generate and cache their summaries.

    Trips are considered 'completed' when their start_date + duration is in the past.
    """
    from backend.database import SessionLocal
    from backend.models import Trip
    from backend.services.metrics_service import set_metric

    session = SessionLocal()
    processed = 0
    try:
        today = date.today()
        cutoff = today - timedelta(days=7)

        # Fetch trips with a known start date that ended recently
        trips = (
            session.query(Trip)
            .filter(
                Trip.start_date.isnot(None),
                Trip.duration.isnot(None),
                Trip.itinerary_json.isnot(None),
            )
            .limit(200)
            .all()
        )

        for trip in trips:
            try:
                start = datetime.strptime(trip.start_date, "%Y-%m-%d").date()
                end = start + timedelta(days=trip.duration)
                if cutoff <= end <= today:
                    # Trip completed recently — generate summary and cache
                    summary = generate_trip_summary(trip, session)
                    cache_key = f"post_trip_summary:{trip.id}"
                    set_metric(cache_key, summary, ttl_seconds=30 * 24 * 60 * 60)
                    processed += 1
            except (ValueError, TypeError):
                continue

        result = {"processed": processed}
        log.info("post_trip.summaries_generated", **result)
        return result

    except Exception:
        log.exception("post_trip.task_failed")
        raise
    finally:
        session.close()
