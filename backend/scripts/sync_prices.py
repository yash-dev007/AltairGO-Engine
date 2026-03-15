import sys
import os
import random
import logging
from datetime import datetime, timezone
from sqlalchemy import text

# Add parent directory to path to import database
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from backend.database import SessionLocal
from backend.models import Attraction, Destination, HotelPrice, FlightRoute

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger(__name__)

# ── AI Agent: Web Scraper fallback for pricing ───────────────────
try:
    from backend.agents.web_scraper_agent import WebScraperAgent
    _scraper_agent = WebScraperAgent()
except ImportError:
    _scraper_agent = None
    log.warning("WebScraperAgent not available — running without scraper fallback.")

# Base multiplier by budget category
ATTR_COST_BASE = {
    1: {"min": 0, "max": 100},
    2: {"min": 100, "max": 400},
    3: {"min": 400, "max": 1500}
}

HOTEL_BASE = {
    "budget":   {"min": 800,  "max": 2500,  "avg": 1500},
    "standard": {"min": 2500, "max": 6000,  "avg": 4000},
    "luxury":   {"min": 6000, "max": 25000, "avg": 12000}
}


def _try_scrape_attraction_price(attraction) -> dict | None:
    """
    AI Agent fallback: If an attraction has a website URL but no API-sourced
    price, attempt to scrape it using the WebScraperAgent.
    Returns dict with entry_cost_adult or None.
    """
    if not _scraper_agent:
        return None
    website = getattr(attraction, 'website', None)
    if not website:
        return None
    try:
        result = _scraper_agent.scrape_attraction_price(website)
        if result and result.get("entry_cost_adult") is not None:
            log.info(f"  ✓ Scraped price for {attraction.name}: ₹{result['entry_cost_adult']}")
            return result
    except Exception as e:
        log.debug(f"  Scraper fallback failed for {attraction.name}: {e}")
    return None


def sync_attraction_prices(db):
    attractions = db.query(Attraction).all()
    count = 0
    scraped_count = 0
    now = datetime.now(timezone.utc)
    
    for a in attractions:
        bc = getattr(a, 'budget_category', 2)
        base = ATTR_COST_BASE.get(bc, ATTR_COST_BASE[2])
        
        # ── AI Agent: Try web scraper first for real-world prices ─
        scraped = _try_scrape_attraction_price(a)
        if scraped:
            a.entry_cost_min = scraped.get("entry_cost_adult", 0)
            a.entry_cost_max = scraped.get("entry_cost_adult", 0)
            if scraped.get("entry_cost_child") is not None:
                a.entry_cost_child = scraped["entry_cost_child"]
            a.price_last_synced = now
            count += 1
            scraped_count += 1
            continue

        # ── Heuristic fallback ───────────────────────────────────
        # Add some slight variation
        cost_min = max(0, int(base["min"] * random.uniform(0.8, 1.2)))
        cost_max = max(cost_min, int(base["max"] * random.uniform(0.8, 1.2)))
        
        # Override if it's explicitly a natural/religious free attraction
        if a.type in ["nature", "religious", "shopping"]:
            cost_min = 0
            cost_max = 50 if bc > 1 else 0
            
        a.entry_cost_min = cost_min
        a.entry_cost_max = cost_max
        a.price_last_synced = now
        count += 1
        
    log.info(f"Synced {count} attraction prices ({scraped_count} via AI scraper agent).")

def sync_hotel_prices(db):
    destinations = db.query(Destination).all()
    now = datetime.now(timezone.utc)
    count = 0
    
    # Clear old cache for simplicity in this MVP script
    db.query(HotelPrice).delete()
    
    for d in destinations:
        for tier, ranges in HOTEL_BASE.items():
            # City multiplier (Delhi/Mumbai more expensive than Pushkar)
            mult = 1.0
            if d.name in ["Mumbai", "Delhi", "Bangalore"]: mult = 1.4
            if d.name in ["Goa", "Kochi", "Udaipur"]: mult = 1.2
            if d.name in ["Pushkar", "Hampi", "Gokarna"]: mult = 0.8
            
            tier_names = {"budget": "Budget Hotel", "standard": "Standard Hotel", "luxury": "Luxury Resort"}
            p = HotelPrice(
                destination_id=d.id,
                hotel_name=f"{tier_names.get(tier, tier)} - {d.name}",
                category=tier,
                price_per_night_min=int(ranges["min"] * mult * random.uniform(0.9, 1.1)),
                price_per_night_max=int(ranges["max"] * mult * random.uniform(0.9, 1.1)),
                partner="booking.com_mock",
                booking_url=f"https://www.booking.com/searchresults.html?ss={d.name}",
                last_synced=now
            )
            db.add(p)
            count += 1
    
    db.commit()
    log.info(f"Generated {count} real-time hotel price nodes.")

def sync_flight_routes(db):
    destinations = db.query(Destination).all()
    now = datetime.now(timezone.utc)
    count = 0
    
    db.query(FlightRoute).delete()
    
    # Just seed a few major routes between major airports to avoid O(N^2) explosion
    majors = ["Delhi", "Mumbai", "Bangalore", "Jaipur", "Kochi", "Goa"]
    major_dests = [d for d in destinations if d.name in majors]
    
    for origin in major_dests:
        for dest in major_dests:
            if origin.id == dest.id: continue
            
            # Mock price 3000 to 8000
            avg_price = random.randint(3000, 8000)
            
            r = FlightRoute(
                origin_iata=origin.name[:3].upper(), # Fake IATA
                destination_iata=dest.name[:3].upper(),
                transport_type="flight",
                avg_one_way_inr=avg_price,
                duration_minutes=random.randint(60, 180),
                airlines=["IndiGo", "Vistara"],
                last_synced=now
            )
            db.add(r)
            count += 1
    
    db.commit()
    log.info(f"Generated {count} flight route pricing links.")

def run_sync():
    log.info("Starting Price Synchronization (Stage 4)...")
    db = SessionLocal()
    
    try:
        sync_attraction_prices(db)
        sync_hotel_prices(db)
        sync_flight_routes(db)
        
        db.commit()
        log.info("Pricing database successfully seeded and synchronized.")
        
    except Exception as e:
        log.error(f"Price sync failed: {e}")
        db.rollback()
    finally:
        db.close()


class PriceSyncer:
    def __init__(self, db_session=None):
        self.db = db_session

    def sync_attraction_prices(self):
        if self.db is None:
            db = SessionLocal()
            try:
                sync_attraction_prices(db)
                db.commit()
            finally:
                db.close()
            return
        sync_attraction_prices(self.db)

    def sync_hotel_prices(self):
        if self.db is None:
            db = SessionLocal()
            try:
                sync_hotel_prices(db)
            finally:
                db.close()
            return
        sync_hotel_prices(self.db)

    def sync_flight_routes(self):
        if self.db is None:
            db = SessionLocal()
            try:
                sync_flight_routes(db)
            finally:
                db.close()
            return
        sync_flight_routes(self.db)

    def run(self):
        if self.db is None:
            return run_sync()
        sync_attraction_prices(self.db)
        sync_hotel_prices(self.db)
        sync_flight_routes(self.db)
        self.db.commit()

if __name__ == "__main__":
    run_sync()
