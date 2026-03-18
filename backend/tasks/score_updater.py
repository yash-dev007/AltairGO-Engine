import logging
from sqlalchemy import text
from backend.database import SessionLocal

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)
MIN_SIGNALS = 10   # Minimum before behavioral score overrides static

def update_scores():
    """
    Recalculates popularity_score and user_skip_rate for every
    attraction with enough behavioral signals.
    Blend: 70% static OSM score + 30% real user save rate.
    """
    db = SessionLocal()
    updated = skipped = 0
    try:
        attraction_ids = db.execute(text(
            "SELECT DISTINCT attraction_id FROM attraction_signal"
        )).fetchall()

        for row in attraction_ids:
            aid = row.attraction_id
            counts = db.execute(text("""
                SELECT event_type, COUNT(*) AS cnt
                FROM attraction_signal WHERE attraction_id=:aid
                GROUP BY event_type
            """), {"aid": aid}).fetchall()

            ec = {r.event_type: r.cnt for r in counts}
            saves = ec.get("save", 0) + ec.get("book_click", 0) * 2
            removes = ec.get("remove", 0) + ec.get("swap", 0)
            total = saves + removes

            if total < MIN_SIGNALS:
                skipped += 1; continue

            skip_rate      = removes / total
            behavior_score = (saves / total) * 100

            current = db.execute(
                text("SELECT popularity_score FROM attraction WHERE id=:id"), {"id":aid}
            ).fetchone()
            if not current: continue

            new_score = (current.popularity_score * 0.7) + (behavior_score * 0.3)
            db.execute(text("""
                UPDATE attraction SET popularity_score=:s, user_skip_rate=:skip WHERE id=:id
            """), {"s": round(new_score,2), "skip": round(skip_rate,3), "id": aid})
            updated += 1

        db.commit()
        log.info(f"Score update done: {updated} updated, {skipped} skipped (<{MIN_SIGNALS} signals)")
    except Exception as e:
        db.rollback(); log.error(f"Score update failed: {e}"); raise
    finally:
        db.close()


def update_scores_from_quality():
    """
    Secondary scoring pass: adjust popularity_score based on Trip.quality_score.
    When an attraction appears in many high-quality trips it gets a boost;
    when it appears in low-quality trips it gets a penalty.

    Blend: existing_score * 0.85 + quality_contribution * 0.15
    Only runs for attractions that appeared in ≥ 3 scored trips.
    """
    db = SessionLocal()
    updated = skipped = 0
    MIN_QUALITY_TRIPS = 3

    try:
        from backend.models import Trip, Attraction
        trips = db.query(Trip).filter(
            Trip.quality_score.isnot(None),
            Trip.itinerary_json.isnot(None),
        ).all()

        # Build attraction_name → [quality_scores] mapping
        from collections import defaultdict
        quality_map: dict = defaultdict(list)
        for trip in trips:
            q_score = trip.quality_score
            if q_score is None:
                continue
            try:
                itin = trip.itinerary_json if isinstance(trip.itinerary_json, dict) else {}
                for day in itin.get("itinerary", []):
                    for act in day.get("activities", []):
                        name = (act.get("name") or act.get("activity") or "").strip().lower()
                        if name and not act.get("is_break"):
                            quality_map[name].append(float(q_score))
            except Exception:
                continue

        # Update attraction popularity_score
        attractions = db.query(Attraction).all()
        for attr in attractions:
            attr_name = (attr.name or "").strip().lower()
            scores = quality_map.get(attr_name, [])
            if len(scores) < MIN_QUALITY_TRIPS:
                skipped += 1
                continue

            avg_quality = sum(scores) / len(scores)
            # quality_score is 0-5 → normalize to 0-100
            quality_contribution = (avg_quality / 5.0) * 100.0
            current_score = float(attr.popularity_score or 50)
            new_score = round(current_score * 0.85 + quality_contribution * 0.15, 2)
            attr.popularity_score = new_score
            updated += 1

        db.commit()
        log.info(
            f"Quality-score update done: {updated} attractions updated, "
            f"{skipped} skipped (< {MIN_QUALITY_TRIPS} scored trips)."
        )
    except Exception as e:
        db.rollback()
        log.error(f"Quality score update failed: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    log.info("Running score update manually...")
    update_scores()
    update_scores_from_quality()
