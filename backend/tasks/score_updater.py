import structlog
from sqlalchemy import text
from backend.database import SessionLocal

log = structlog.get_logger(__name__)
MIN_SIGNALS: int = 10  # Minimum signal count before behavioral score overrides static


def update_scores() -> dict:
    """
    Recalculates popularity_score and user_skip_rate for every attraction
    with enough behavioral signals.
    Blend: 70% static OSM score + 30% real user save rate.

    Uses a single aggregated SQL query per run (no N+1 loop).
    """
    db = SessionLocal()
    updated = skipped = 0
    try:
        # Aggregate all signal counts in one query, then join to current scores.
        rows = db.execute(text("""
            SELECT
                sig.attraction_id,
                SUM(CASE WHEN sig.event_type IN ('save','book_click') THEN
                    CASE WHEN sig.event_type='book_click' THEN 2 ELSE 1 END
                    ELSE 0 END) AS saves,
                SUM(CASE WHEN sig.event_type IN ('remove','swap') THEN 1 ELSE 0 END) AS removes,
                a.popularity_score AS current_score
            FROM attraction_signal sig
            JOIN attraction a ON a.id = sig.attraction_id
            GROUP BY sig.attraction_id, a.popularity_score
        """)).fetchall()

        updates = []
        for row in rows:
            total = row.saves + row.removes
            if total < MIN_SIGNALS:
                skipped += 1
                continue
            skip_rate = row.removes / total
            behavior_score = (row.saves / total) * 100
            new_score = round((row.current_score * 0.7) + (behavior_score * 0.3), 2)
            updates.append({"id": row.attraction_id, "s": new_score, "skip": round(skip_rate, 3)})

        if updates:
            db.execute(
                text("UPDATE attraction SET popularity_score=:s, user_skip_rate=:skip WHERE id=:id"),
                updates,
            )
            updated = len(updates)

        db.commit()
        result = {"updated": updated, "skipped": skipped}
        log.info("score_update.done", **result)
        return result
    except Exception:
        db.rollback()
        log.exception("score_update.failed")
        raise
    finally:
        db.close()


def update_scores_from_quality() -> dict:
    """
    Secondary scoring pass: adjust popularity_score based on Trip.quality_score.
    When an attraction appears in many high-quality trips it gets a boost;
    when it appears in low-quality trips it gets a penalty.

    Blend: existing_score * 0.85 + quality_contribution * 0.15
    Only runs for attractions that appeared in >= 3 scored trips.

    Uses aggregated SQL for the trip scan and targeted UPDATE statements
    to avoid loading entire tables into Python memory.
    """
    MIN_QUALITY_TRIPS = 3
    db = SessionLocal()
    updated = skipped = 0

    try:
        from backend.models import Trip, Attraction
        from collections import defaultdict

        # Fetch only the columns we need — itinerary_json can be large,
        # so stream quality_score + itinerary_json in pages to bound memory.
        quality_map: dict[str, list[float]] = defaultdict(list)
        offset = 0
        page_size = 200
        while True:
            trips = (
                db.query(Trip.quality_score, Trip.itinerary_json)
                .filter(Trip.quality_score.isnot(None), Trip.itinerary_json.isnot(None))
                .limit(page_size)
                .offset(offset)
                .all()
            )
            if not trips:
                break
            for q_score, itin_json in trips:
                try:
                    itin = itin_json if isinstance(itin_json, dict) else {}
                    for day in itin.get("itinerary", []):
                        for act in day.get("activities", []):
                            name = (act.get("name") or act.get("activity") or "").strip().lower()
                            if name and not act.get("is_break"):
                                quality_map[name].append(float(q_score))
                except Exception:
                    continue
            offset += page_size

        # Only load attractions that appear in quality_map at all
        eligible_names = list(quality_map.keys())
        if not eligible_names:
            result = {"updated": 0, "skipped": 0}
            log.info("quality_score_update.done", **result)
            return result

        from sqlalchemy import func
        attractions = (
            db.query(Attraction)
            .filter(func.lower(Attraction.name).in_(eligible_names))
            .all()
        )

        for attr in attractions:
            attr_name = (attr.name or "").strip().lower()
            scores = quality_map.get(attr_name, [])
            if len(scores) < MIN_QUALITY_TRIPS:
                skipped += 1
                continue
            avg_quality = sum(scores) / len(scores)
            quality_contribution = (avg_quality / 5.0) * 100.0
            current_score = float(attr.popularity_score or 50)
            attr.popularity_score = round(current_score * 0.85 + quality_contribution * 0.15, 2)
            updated += 1

        db.commit()
        result = {"updated": updated, "skipped": skipped}
        log.info("quality_score_update.done", **result)
        return result
    except Exception:
        db.rollback()
        log.exception("quality_score_update.failed")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    log.info("score_update.manual_start")
    update_scores()
    update_scores_from_quality()
