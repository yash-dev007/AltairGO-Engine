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

if __name__ == "__main__":
    log.info("Running score update manually...")
    update_scores()
