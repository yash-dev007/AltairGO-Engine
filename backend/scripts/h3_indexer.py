import h3, logging
from sqlalchemy import text
from database import SessionLocal

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

def backfill():
    db = SessionLocal()
    try:
        rows = db.execute(text(
            "SELECT id,lat,lng FROM destination WHERE lat IS NOT NULL AND h3_index_r9 IS NULL"
        )).fetchall()
        for r in rows:
            db.execute(text("UPDATE destination SET h3_index_r7=:r7,h3_index_r9=:r9 WHERE id=:id"),
                {"r7":h3.geo_to_h3(r.lat,r.lng,7),"r9":h3.geo_to_h3(r.lat,r.lng,9),"id":r.id})
        db.commit()
        log.info(f"{len(rows)} destinations H3-indexed")

        rows = db.execute(text(
            "SELECT id,lat,lng FROM attraction WHERE lat IS NOT NULL AND h3_index_r9 IS NULL"
        )).fetchall()
        for i, r in enumerate(rows):
            db.execute(text("UPDATE attraction SET h3_index_r9=:r9 WHERE id=:id"),
                {"r9":h3.geo_to_h3(r.lat,r.lng,9),"id":r.id})
            if i % 500 == 0: db.commit(); log.info(f"  {i}/{len(rows)}...")
        db.commit()
        log.info(f"{len(rows)} attractions H3-indexed")
    finally:
        db.close()

if __name__ == "__main__":
    backfill()
