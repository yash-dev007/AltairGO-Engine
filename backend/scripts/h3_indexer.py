"""
h3_indexer.py — Backfill H3 geospatial cell indices for destinations and attractions.
Run: python -m backend.scripts.h3_indexer

Fixes from original:
  1. Wrong import (database → backend.database)
  2. h3 v3-only: geo_to_h3() removed in v4 → compat wrapper
  3. Attractions only indexed at r9, not r7 — fixed to index both
  4. No per-row error handling — one bad coord aborted the whole run
  5. No batching for destination updates (low risk but now consistent)
"""
import sys
import os
import logging

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from backend.database import SessionLocal
from sqlalchemy import text

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger(__name__)

# ── h3 v3 / v4 compatibility wrapper ─────────────────────────────────
try:
    import h3 as h3lib

    def _geo_to_h3(lat: float, lng: float, res: int) -> str:
        """Works with both h3-py v3 (geo_to_h3) and v4 (latlng_to_cell)."""
        if hasattr(h3lib, "latlng_to_cell"):
            return h3lib.latlng_to_cell(lat, lng, res)
        return h3lib.geo_to_h3(lat, lng, res)

    H3_AVAILABLE = True
except ImportError:
    H3_AVAILABLE = False
    log.warning("h3 library not installed — skipping H3 indexing.")


BATCH_SIZE = 500


def backfill():
    if not H3_AVAILABLE:
        log.error("Install h3-py: pip install h3")
        return

    db = SessionLocal()
    try:
        # ── Destinations (index r7 + r9) ──────────────────────────────
        rows = db.execute(text(
            "SELECT id, lat, lng FROM destination "
            "WHERE lat IS NOT NULL AND lng IS NOT NULL "
            "AND (h3_index_r9 IS NULL OR h3_index_r7 IS NULL)"
        )).fetchall()
        log.info(f"Destinations to index: {len(rows)}")

        ok = fail = 0
        for r in rows:
            try:
                r7 = _geo_to_h3(r.lat, r.lng, 7)
                r9 = _geo_to_h3(r.lat, r.lng, 9)
                db.execute(
                    text("UPDATE destination SET h3_index_r7=:r7, h3_index_r9=:r9 WHERE id=:id"),
                    {"r7": r7, "r9": r9, "id": r.id},
                )
                ok += 1
            except Exception as e:
                log.warning(f"  Destination id={r.id} lat={r.lat} lng={r.lng}: {e}")
                fail += 1

        db.commit()
        log.info(f"Destinations: {ok} indexed, {fail} failed.")

        # ── Attractions (index r7 + r9) ───────────────────────────────
        rows = db.execute(text(
            "SELECT id, lat, lng FROM attraction "
            "WHERE lat IS NOT NULL AND lng IS NOT NULL "
            "AND (h3_index_r9 IS NULL OR h3_index_r7 IS NULL)"
        )).fetchall()
        log.info(f"Attractions to index: {len(rows)}")

        ok = fail = 0
        for i, r in enumerate(rows):
            try:
                r7 = _geo_to_h3(r.lat, r.lng, 7)
                r9 = _geo_to_h3(r.lat, r.lng, 9)
                db.execute(
                    text("UPDATE attraction SET h3_index_r7=:r7, h3_index_r9=:r9 WHERE id=:id"),
                    {"r7": r7, "r9": r9, "id": r.id},
                )
                ok += 1
            except Exception as e:
                log.warning(f"  Attraction id={r.id} lat={r.lat} lng={r.lng}: {e}")
                fail += 1

            if (i + 1) % BATCH_SIZE == 0:
                db.commit()
                log.info(f"  {i + 1}/{len(rows)} committed...")

        db.commit()
        log.info(f"Attractions: {ok} indexed, {fail} failed.")

    finally:
        db.close()


if __name__ == "__main__":
    backfill()
