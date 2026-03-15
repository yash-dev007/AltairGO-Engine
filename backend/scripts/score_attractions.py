import sys
import os
import json
import logging
import math
from sqlalchemy import text

# Add parent directory to path to import database
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from backend.database import SessionLocal
from backend.models import Attraction, Destination

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger(__name__)

MONTH_KEYS = ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"]

def calculate_seasonal_score(destination_months, attraction_months):
    """
    Returns a dictionary mapping month keys to a 0-100 score.
    If destination is good in a month, base score 80. Else 40.
    If attraction is specifically good, +20. Else -20.
    """
    dst_months = destination_months or []
    attr_months = attraction_months or list(range(1, 13))
    
    scores = {}
    for i, m in enumerate(MONTH_KEYS, 1):
        base = 80 if i in dst_months else 40
        modifier = 20 if i in attr_months else -20
        scores[m] = max(0, min(100, base + modifier))
        
    return scores

def run_scoring():
    log.info("Starting POI Intelligence Scoring (Stage 3)...")
    db = SessionLocal()
    
    try:
        destinations = db.query(Destination).all()
        dest_map = {d.id: d for d in destinations}
        
        attractions = db.query(Attraction).all()
        log.info(f"Found {len(attractions)} attractions to score.")
        
        updated_count = 0
        for attr in attractions:
            # 1. Popularity Score Recalculation
            # Base score from OSM ingestion is 30.
            # We bump this up with Google Rating and Reviews.
            google_bonus = 0
            if attr.google_rating:
                # Up to 25 points for rating if > 4.0
                if attr.google_rating >= 4.0:
                    google_bonus += (attr.google_rating - 4.0) * 25
            
            review_bonus = 0
            if attr.review_count:
                # Logarithmic scale up to 45 points (maxing out around 10k reviews)
                if attr.review_count > 0:
                    review_bonus = min(45, math.log10(attr.review_count) * 11)
                    
            # 30 (OSM base) + 25 (Rating) + 45 (Reviews) = 100 max
            final_popularity = 30 + google_bonus + review_bonus
            
            # Additional bonus for Wikipedia reference
            if attr.wikidata_id:
                final_popularity += 15
                
            attr.popularity_score = min(100.0, final_popularity)
            
            # 2. Seasonal Index Calculation
            dest = dest_map.get(attr.destination_id)
            if dest:
                # Assuming best_months is stored as JSON list in DB
                try:
                    dest_months_arr = json.loads(dest.best_months) if isinstance(dest.best_months, str) else dest.best_months
                except:
                    dest_months_arr = []
                    
                seasonal = calculate_seasonal_score(dest_months_arr, attr.best_months)
                attr.seasonal_score = seasonal
                
            updated_count += 1
            
        db.commit()
        log.info(f"Scoring complete. Updated {updated_count} attractions.")
        
    except Exception as e:
        log.error(f"Scoring pipeline failed: {e}")
        db.rollback()
    finally:
        db.close()


class AttractionScorer:
    def __init__(self, db_session=None):
        self.db = db_session

    @staticmethod
    def calculate_seasonal_score(destination_months, attraction_months):
        return calculate_seasonal_score(destination_months, attraction_months)

    def run(self):
        if self.db is None:
            return run_scoring()

        destinations = self.db.query(Destination).all()
        dest_map = {destination.id: destination for destination in destinations}
        attractions = self.db.query(Attraction).all()

        for attr in attractions:
            google_bonus = 0
            if attr.google_rating and attr.google_rating >= 4.0:
                google_bonus += (attr.google_rating - 4.0) * 25

            review_bonus = 0
            if attr.review_count and attr.review_count > 0:
                review_bonus = min(45, math.log10(attr.review_count) * 11)

            final_popularity = 30 + google_bonus + review_bonus
            if attr.wikidata_id:
                final_popularity += 15
            attr.popularity_score = min(100.0, final_popularity)

            destination = dest_map.get(attr.destination_id)
            if destination:
                try:
                    destination_months = (
                        json.loads(destination.best_months)
                        if isinstance(destination.best_months, str)
                        else destination.best_months
                    )
                except Exception:
                    destination_months = []
                attr.seasonal_score = calculate_seasonal_score(
                    destination_months,
                    attr.best_months,
                )

        self.db.commit()

if __name__ == "__main__":
    run_scoring()
