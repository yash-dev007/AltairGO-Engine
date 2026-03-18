import sys
import os
import random
import logging
from datetime import datetime, timezone
from dotenv import load_dotenv
load_dotenv()
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
    
    for d in destinations:
        for tier, ranges in HOTEL_BASE.items():
            # City multiplier (Delhi/Mumbai more expensive than Pushkar)
            mult = 1.0
            if d.name in ["Mumbai", "Delhi", "Bangalore"]: mult = 1.4
            if d.name in ["Goa", "Kochi", "Udaipur"]: mult = 1.2
            if d.name in ["Pushkar", "Hampi", "Gokarna"]: mult = 0.8
            
            tier_names = {"budget": "Budget Hotel", "standard": "Standard Hotel", "luxury": "Luxury Resort"}
            # Upsert: update if exists, insert if not — avoids wiping all data every run
            existing = db.query(HotelPrice).filter_by(
                destination_id=d.id, category=tier, partner="booking.com_mock"
            ).first()
            price_min = int(ranges["min"] * mult * random.uniform(0.9, 1.1))
            price_max = int(ranges["max"] * mult * random.uniform(0.9, 1.1))
            if existing:
                existing.price_per_night_min = price_min
                existing.price_per_night_max = price_max
                existing.last_synced = now
            else:
                p = HotelPrice(
                    destination_id=d.id,
                    hotel_name=f"{tier_names.get(tier, tier)} - {d.name}",
                    category=tier,
                    price_per_night_min=price_min,
                    price_per_night_max=price_max,
                    partner="booking.com_mock",
                    booking_url=f"https://www.booking.com/searchresults.html?ss={d.name}",
                    last_synced=now
                )
                db.add(p)
            count += 1
    
    db.commit()
    log.info(f"Generated {count} real-time hotel price nodes.")

def sync_flight_routes(db):
    """
    Seed realistic India domestic flight routes with correct IATA codes.
    Uses distance-based pricing heuristic (short-haul ₹2500-5000, long-haul ₹4000-10000).
    Upserts to avoid wiping existing data on every run.
    """
    now = datetime.now(timezone.utc)
    count = 0

    # Correct IATA codes for Indian airports
    INDIA_IATA = {
        "Delhi":       "DEL",
        "Mumbai":      "BOM",
        "Bangalore":   "BLR",
        "Bengaluru":   "BLR",
        "Hyderabad":   "HYD",
        "Chennai":     "MAA",
        "Kolkata":     "CCU",
        "Kochi":       "COK",
        "Goa":         "GOI",
        "Jaipur":      "JAI",
        "Ahmedabad":   "AMD",
        "Pune":        "PNQ",
        "Bhubaneswar": "BBI",
        "Lucknow":     "LKO",
        "Varanasi":    "VNS",
        "Amritsar":    "ATQ",
        "Srinagar":    "SXR",
        "Leh":         "IXL",
        "Guwahati":    "GAU",
        "Port Blair":  "IXZ",
        "Agartala":    "IXA",
        "Dibrugarh":   "DIB",
        "Imphal":      "IMF",
        "Mangaluru":   "IXE",
        "Coimbatore":  "CJB",
        "Thiruvananthapuram": "TRV",
        "Vishakhapatnam": "VTZ",
        "Nagpur":      "NAG",
        "Indore":      "IDR",
        "Raipur":      "RPR",
        "Patna":       "PAT",
        "Ranchi":      "IXR",
        "Jammu":       "IXJ",
        "Chandigarh":  "IXC",
        "Udaipur":     "UDR",
        "Jodhpur":     "JDH",
    }

    # Distance tiers for pricing (approx km bands)
    # All major India hub pairs + selective regional routes
    ROUTES = [
        # (origin_iata, dest_iata, duration_min, airlines)
        ("DEL", "BOM", 130, ["IndiGo", "Air India", "SpiceJet"]),
        ("DEL", "BLR", 160, ["IndiGo", "Air India", "Vistara"]),
        ("DEL", "HYD", 140, ["IndiGo", "Air India"]),
        ("DEL", "MAA", 160, ["IndiGo", "Air India", "SpiceJet"]),
        ("DEL", "CCU", 130, ["IndiGo", "Air India"]),
        ("DEL", "COK", 190, ["IndiGo", "Air India"]),
        ("DEL", "GOI", 130, ["IndiGo", "SpiceJet"]),
        ("DEL", "JAI",  55, ["IndiGo", "SpiceJet", "Air India"]),
        ("DEL", "AMD", 100, ["IndiGo", "SpiceJet"]),
        ("DEL", "SXR",  75, ["IndiGo", "SpiceJet", "Go First"]),
        ("DEL", "IXL", 100, ["IndiGo", "SpiceJet"]),
        ("DEL", "LKO",  60, ["IndiGo", "Air India"]),
        ("DEL", "VNS",  80, ["IndiGo", "Air India"]),
        ("DEL", "ATQ",  55, ["IndiGo", "SpiceJet"]),
        ("DEL", "IXC",  45, ["IndiGo", "SpiceJet"]),
        ("DEL", "GAU", 160, ["IndiGo", "Air India"]),
        ("DEL", "IXZ", 230, ["Air India"]),
        ("BOM", "BLR",  80, ["IndiGo", "Air India", "Vistara"]),
        ("BOM", "HYD",  85, ["IndiGo", "Vistara"]),
        ("BOM", "MAA",  90, ["IndiGo", "Air India"]),
        ("BOM", "COK",  90, ["IndiGo", "Air India"]),
        ("BOM", "GOI",  60, ["IndiGo", "SpiceJet"]),
        ("BOM", "JAI", 100, ["IndiGo", "SpiceJet"]),
        ("BOM", "AMD",  65, ["IndiGo", "SpiceJet"]),
        ("BOM", "CCU", 160, ["IndiGo", "Air India"]),
        ("BOM", "VNS", 110, ["IndiGo"]),
        ("BOM", "PNQ",  50, ["IndiGo", "SpiceJet"]),
        ("BLR", "HYD",  60, ["IndiGo", "Vistara"]),
        ("BLR", "MAA",  55, ["IndiGo", "Air India"]),
        ("BLR", "COK",  70, ["IndiGo", "Air India"]),
        ("BLR", "GOI",  75, ["IndiGo"]),
        ("BLR", "CCU", 150, ["IndiGo", "Air India"]),
        ("BLR", "TRV",  75, ["IndiGo", "Air India"]),
        ("BLR", "CJB",  50, ["IndiGo"]),
        ("MAA", "COK",  70, ["IndiGo", "Air India"]),
        ("MAA", "HYD",  65, ["IndiGo"]),
        ("MAA", "CCU", 140, ["IndiGo", "Air India"]),
        ("HYD", "CCU", 120, ["IndiGo", "Air India"]),
        ("JAI", "UDR",  45, ["IndiGo"]),
        ("JAI", "JDH",  40, ["IndiGo"]),
        ("GAU", "IXA",  40, ["IndiGo"]),
        ("GAU", "IMF",  55, ["IndiGo"]),
        ("GAU", "DIB",  60, ["IndiGo"]),
    ]

    def _price_for_duration(dur_min: int) -> int:
        """Rough distance-based pricing: short < 75min, medium < 130min, long >= 130min."""
        if dur_min < 75:
            return random.randint(2200, 4500)
        if dur_min < 130:
            return random.randint(3500, 7000)
        return random.randint(5000, 11000)

    for origin_iata, dest_iata, dur, airlines in ROUTES:
        for o, d in [(origin_iata, dest_iata), (dest_iata, origin_iata)]:
            existing = db.query(FlightRoute).filter_by(
                origin_iata=o, destination_iata=d, transport_type="flight"
            ).first()
            price = _price_for_duration(dur)
            if existing:
                existing.avg_one_way_inr = price
                existing.duration_minutes = dur
                existing.airlines = airlines
                existing.last_synced = now
            else:
                db.add(FlightRoute(
                    origin_iata=o,
                    destination_iata=d,
                    transport_type="flight",
                    avg_one_way_inr=price,
                    duration_minutes=dur,
                    airlines=airlines,
                    last_synced=now,
                ))
            count += 1

    db.commit()
    log.info(f"Upserted {count} flight route pricing links.")

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
