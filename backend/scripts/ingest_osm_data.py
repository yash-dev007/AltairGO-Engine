import sys
import os
import json
import time
import logging
import requests
from dotenv import load_dotenv
load_dotenv()

# Add parent directory to path to import database
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from backend.database import SessionLocal
from sqlalchemy import text

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger(__name__)

# ── H3 import (once at module level) ─────────────────────────────────────────
try:
    import h3 as _h3lib
    if hasattr(_h3lib, 'latlng_to_cell'):   # h3-py v4
        def _geo_to_h3(lat: float, lng: float, res: int) -> str:
            return _h3lib.latlng_to_cell(lat, lng, res)
    else:                                    # h3-py v3 fallback
        def _geo_to_h3(lat: float, lng: float, res: int) -> str:
            return _h3lib.geo_to_h3(lat, lng, res)
except ImportError:
    def _geo_to_h3(lat: float, lng: float, res: int):   # type: ignore[misc]
        return None

# ─────────────────────────────────────────────────────────────────────────────

OVERPASS_URL      = "https://overpass-api.de/api/interpreter"
MAX_POIS_PER_CITY = 150
RADIUS_METERS     = 15000
OVERPASS_RETRIES  = 2          # retry once on timeout before giving up
OVERPASS_RETRY_DELAY = 10      # seconds between retries

# ── OSM tag → (category, budget_category_int, avg_duration_hrs, best_visit_hour) ──
TYPE_MAP = {
    # tourism tags
    "museum":           ("cultural",  2, 2.5, 10),
    "gallery":          ("cultural",  2, 1.5, 10),
    "artwork":          ("cultural",  1, 0.5, 10),
    "attraction":       ("general",   2, 1.5, 10),
    "viewpoint":        ("nature",    1, 1.0,  7),
    "zoo":              ("family",    2, 3.0, 11),
    "theme_park":       ("family",    3, 5.0, 11),
    "aquarium":         ("family",    2, 2.0, 11),
    "camp_site":        ("nature",    1, 3.0,  8),
    "picnic_site":      ("nature",    1, 1.5,  9),
    # historic tags
    "fort":             ("heritage",  2, 2.5,  9),
    "palace":           ("heritage",  2, 2.0,  9),
    "castle":           ("heritage",  2, 2.5,  9),
    "monument":         ("heritage",  1, 1.0,  9),
    "memorial":         ("heritage",  1, 0.5,  9),
    "ruins":            ("heritage",  1, 2.0,  9),
    "archaeological_site": ("heritage", 2, 2.0, 9),
    "yes":              ("heritage",  1, 1.5,  9),   # generic historic=yes
    # leisure tags
    "park":             ("nature",    1, 2.0,  7),
    "garden":           ("nature",    1, 1.5,  8),
    "nature_reserve":   ("nature",    1, 3.0,  7),
    "water_park":       ("family",    2, 4.0, 11),
    # amenity
    "place_of_worship": ("religious", 1, 1.0,  6),
    "marketplace":      ("shopping",  1, 2.0, 16),   # OSM: amenity=marketplace
    # waterfront / natural
    "waterfall":        ("nature",    1, 1.5,  7),
    "beach":            ("nature",    1, 3.0,  8),
    "hot_spring":       ("nature",    2, 2.0,  8),
}

# ── Traveler types per category ───────────────────────────────────
TRAVELER_MAP = {
    "cultural":  ["solo_male","solo_female","couple","group","elderly"],
    "heritage":  ["solo_male","solo_female","couple","family","group","elderly"],
    "nature":    ["solo_male","solo_female","couple","family","group"],
    "family":    ["family","couple","group"],
    "religious": ["solo_male","solo_female","couple","family","elderly"],
    "shopping":  ["solo_female","couple","family","group"],
    "general":   ["solo_male","solo_female","couple","family","group"],
}

# ── Entry cost estimates (INR) by (category, budget_category_int) ─────
COST_MAP = {
    ("cultural",  1):  50,  ("cultural",  2): 200, ("cultural",  3): 500,
    ("heritage",  1):  30,  ("heritage",  2): 150, ("heritage",  3): 400,
    ("nature",    1):   0,  ("nature",    2):  50, ("nature",    3): 200,
    ("family",    1): 100,  ("family",    2): 300, ("family",    3): 800,
    ("religious", 1):   0,  ("religious", 2):   0, ("religious", 3):   0,
    ("shopping",  1):   0,  ("shopping",  2):   0, ("shopping",  3):   0,
    ("general",   1):  50,  ("general",   2): 100, ("general",   3): 300,
}

# ── Default crowd pattern for most Indian tourist sites ──────────
DEFAULT_CROWD = {
    "8": 2, "9": 3, "10": 5, "11": 7, "12": 6,
    "14": 8, "15": 9, "16": 8, "17": 7, "18": 5,
}

# ── Budget category int → string (matches Attraction.budget_category) ─
BUDGET_MAP = {1: "budget", 2: "mid-range", 3: "luxury"}

# ── Crowd pattern overrides per category ─────────────────────────
CROWD_OVERRIDES = {
    "religious": {"5": 6, "6": 9, "7": 8, "8": 6, "17": 7, "18": 9, "19": 8},
    "shopping":  {"10": 3, "11": 5, "14": 7, "16": 9, "17": 9, "18": 8, "20": 7},
    "nature":    {"7": 4, "8": 6, "9": 7, "10": 6, "16": 7, "17": 6},
}


def _resolve_type(tags: dict) -> tuple:
    """
    Returns (category, budget_category_int, avg_duration_hrs, best_visit_hour)
    from the OSM tags of a POI element.
    """
    for key in ["tourism", "historic", "leisure", "amenity", "natural"]:
        val = tags.get(key, "")
        if val in TYPE_MAP:
            return TYPE_MAP[val]

    # Generic natural feature not in TYPE_MAP (e.g. natural=cliff)
    if "natural" in tags:
        return ("nature", 1, 2.0, 7)

    return ("general", 2, 1.5, 10)


def _score_poi(tags: dict) -> float:
    """
    Quality score 0–100 based on OSM data richness signals.
    High score = more likely to be a real, notable attraction.
    """
    score = 30.0
    if tags.get("wikipedia"):     score += 5
    if tags.get("wikidata"):      score += 3
    if tags.get("website"):       score += 2
    if tags.get("heritage"):      score += 4
    if tags.get("image"):         score += 1
    if tags.get("description"):   score += 1
    if tags.get("opening_hours"): score += 2

    if tags.get("tourism") == "museum":                           score += 5
    if tags.get("tourism") == "viewpoint":                        score += 2
    if tags.get("leisure") == "park":                             score += 3
    if tags.get("historic") in ("fort", "palace", "castle"):      score += 4

    return min(score, 100.0)


def _get_coords(el: dict) -> tuple:
    """
    Extract (lat, lng) from node or way element.
    Ways from Overpass with `out center` have a `center` sub-dict.
    Returns (None, None) for relation elements or missing coords.
    """
    if el["type"] == "node":
        return el.get("lat"), el.get("lon")
    if el["type"] == "way":
        center = el.get("center", {})
        return center.get("lat"), center.get("lon")
    return None, None


def _build_overpass_query(lat: float, lng: float, radius: int) -> str:
    """
    Overpass QL query that fetches tourism, historic, leisure (incl. water_park),
    amenity=place_of_worship, amenity=marketplace, and key natural features.
    Uses `out body center qt` so ways return center coordinates.
    Timeout=60 — India queries can be slow.
    """
    return f"""[out:json][timeout:60];
(
  node["tourism"](around:{radius},{lat},{lng});
  way["tourism"](around:{radius},{lat},{lng});
  node["historic"](around:{radius},{lat},{lng});
  way["historic"](around:{radius},{lat},{lng});
  node["leisure"~"park|garden|nature_reserve|water_park"](around:{radius},{lat},{lng});
  way["leisure"~"park|garden|nature_reserve|water_park"](around:{radius},{lat},{lng});
  node["amenity"="place_of_worship"](around:{radius},{lat},{lng});
  way["amenity"="place_of_worship"](around:{radius},{lat},{lng});
  node["amenity"="marketplace"](around:{radius},{lat},{lng});
  way["amenity"="marketplace"](around:{radius},{lat},{lng});
  node["natural"~"waterfall|hot_spring|beach"](around:{radius},{lat},{lng});
);
out body center qt;"""


def _fetch_overpass(query: str, city_name: str) -> list | None:
    """
    POST query to Overpass with retry on timeout.
    Returns list of elements or None on permanent failure.
    """
    for attempt in range(1, OVERPASS_RETRIES + 1):
        try:
            resp = requests.post(
                OVERPASS_URL,
                data={"data": query},
                headers={"User-Agent": "AltairGO-Intelligence/1.0"},
                timeout=90,
            )
            resp.raise_for_status()
            return resp.json().get("elements", [])
        except requests.exceptions.Timeout:
            if attempt < OVERPASS_RETRIES:
                log.warning(f"  Overpass timeout (attempt {attempt}/{OVERPASS_RETRIES}), "
                            f"retrying in {OVERPASS_RETRY_DELAY}s…")
                time.sleep(OVERPASS_RETRY_DELAY)
            else:
                log.error(f"  Overpass timeout for {city_name} after {OVERPASS_RETRIES} attempts")
                return None
        except Exception as e:
            log.error(f"  Overpass fetch failed for {city_name}: {e}")
            return None
    return None


def ingest_city_pois(city_name: str, city_id: int, lat: float, lng: float,
                     radius: int = RADIUS_METERS) -> int:
    """
    Fetch POIs from Overpass for one city, score them, upsert top N into DB.
    Returns number of POIs actually upserted (inserted + updated).
    """
    log.info(f"{'─'*50}")
    log.info(f"Ingesting: {city_name}  (lat={lat}, lng={lng}, r={radius}m)")

    query    = _build_overpass_query(lat, lng, radius)
    elements = _fetch_overpass(query, city_name)
    if elements is None:
        return 0

    log.info(f"  Overpass returned {len(elements)} raw elements")

    # ── Score all named elements ──────────────────────────────────
    scored = []

    for el in elements:
        tags     = el.get("tags", {})
        name     = tags.get("name") or tags.get("name:en")
        if not name:
            continue

        lat_poi, lng_poi = _get_coords(el)
        if lat_poi is None or lng_poi is None:
            continue

        cat, bc, dur, visit_hr = _resolve_type(tags)
        pop_score = _score_poi(tags)
        crowd     = CROWD_OVERRIDES.get(cat, DEFAULT_CROWD)
        cost      = COST_MAP.get((cat, bc), 100)

        # Prefix osm_id with element type — node/way numeric IDs are separate
        # namespaces in OSM, so the same integer can appear for both types.
        osm_id = f"{el['type']}/{el['id']}"

        scored.append({
            "name":                       name[:255],
            "lat":                        lat_poi,
            "lng":                        lng_poi,
            "osm_id":                     osm_id,
            "wikidata_id":                tags.get("wikidata") or None,
            "type":                       cat,
            "entry_cost":                 cost,
            "avg_visit_duration_hours":   dur,
            "budget_category":            BUDGET_MAP.get(bc, "mid-range"),
            "popularity_score":           pop_score,
            "best_visit_time_hour":       visit_hr,
            "compatible_traveler_types":  TRAVELER_MAP.get(cat, TRAVELER_MAP["general"]),
            "best_months":                list(range(1, 13)),
            "crowd_level_by_hour":        crowd,
            "description":                (tags.get("description") or "")[:1000],
            "rating":                     4.0,
        })

    # Sort by score descending FIRST, then deduplicate by name — this ensures
    # we keep the highest-quality occurrence when the same name appears multiple
    # times (e.g. a node and a way both tagged "Taj Mahal").
    scored.sort(key=lambda x: -x["popularity_score"])
    seen_names: set[str] = set()
    deduped = []
    for p in scored:
        key = p["name"].strip().lower()
        if key not in seen_names:
            seen_names.add(key)
            deduped.append(p)

    top_pois = deduped[:MAX_POIS_PER_CITY]
    log.info(f"  {len(scored)} named elements → keeping top {len(top_pois)}")

    if not top_pois:
        log.warning(f"  No usable POIs found for {city_name}")
        return 0

    # ── Upsert into DB ────────────────────────────────────────────
    db = SessionLocal()
    inserted = updated = skipped = 0

    try:
        for p in top_pois:
            # H3 indices per POI (module-level function; no per-iteration import)
            try:
                h3_r9 = _geo_to_h3(p["lat"], p["lng"], 9)
                h3_r7 = _geo_to_h3(p["lat"], p["lng"], 7)
            except Exception as e:
                log.warning(f"    H3 generation failed for {p['name']}: {e}")
                h3_r9 = h3_r7 = None

            db_params = {
                "name":                      p["name"],
                "description":               p["description"],
                "lat":                       p["lat"],
                "lng":                       p["lng"],
                "osm_id":                    p["osm_id"],
                "wikidata_id":               p["wikidata_id"],
                "type":                      p["type"],
                "entry_cost":                p["entry_cost"],
                "rating":                    p["rating"],
                "avg_visit_duration_hours":  p["avg_visit_duration_hours"],
                "budget_category":           p["budget_category"],
                "popularity_score":          p["popularity_score"],
                "best_visit_time_hour":      p["best_visit_time_hour"],
                "compatible_traveler_types": json.dumps(p["compatible_traveler_types"]),
                "best_months":               json.dumps(p["best_months"]),
                "crowd_level_by_hour":       json.dumps(p["crowd_level_by_hour"]),
                "dest_id":                   city_id,
                "h3_r9":                     h3_r9,
                "h3_r7":                     h3_r7,
            }

            # SAVEPOINT per row — isolates row-level errors so a single
            # constraint violation does not abort the whole transaction.
            try:
                db.execute(text("SAVEPOINT poi_upsert"))

                existing = db.execute(
                    text("SELECT id FROM attraction WHERE osm_id = :osm_id"),
                    {"osm_id": p["osm_id"]}
                ).fetchone()

                if existing:
                    db.execute(text("""
                        UPDATE attraction SET
                            lat                       = :lat,
                            lng                       = :lng,
                            latitude                  = :lat,
                            longitude                 = :lng,
                            coordinates               = ST_MakePoint(:lng, :lat)::geography,
                            h3_index_r9               = :h3_r9,
                            h3_index_r7               = :h3_r7,
                            type                      = :type,
                            entry_cost                = :entry_cost,
                            avg_visit_duration_hours  = :avg_visit_duration_hours,
                            budget_category           = :budget_category,
                            popularity_score          = :popularity_score,
                            best_visit_time_hour      = :best_visit_time_hour,
                            compatible_traveler_types = CAST(:compatible_traveler_types AS jsonb),
                            best_months               = CAST(:best_months AS jsonb),
                            crowd_level_by_hour       = CAST(:crowd_level_by_hour AS jsonb),
                            wikidata_id               = :wikidata_id
                        WHERE osm_id = :osm_id
                    """), db_params)
                    updated += 1
                else:
                    db.execute(text("""
                        INSERT INTO attraction (
                            name, description, lat, lng, latitude, longitude,
                            coordinates, h3_index_r9, h3_index_r7,
                            osm_id, wikidata_id, type, entry_cost, rating,
                            avg_visit_duration_hours, budget_category,
                            popularity_score, best_visit_time_hour,
                            compatible_traveler_types, best_months,
                            crowd_level_by_hour, destination_id, source
                        ) VALUES (
                            :name, :description, :lat, :lng, :lat, :lng,
                            ST_MakePoint(:lng, :lat)::geography,
                            :h3_r9, :h3_r7,
                            :osm_id, :wikidata_id, :type, :entry_cost, :rating,
                            :avg_visit_duration_hours, :budget_category,
                            :popularity_score, :best_visit_time_hour,
                            CAST(:compatible_traveler_types AS jsonb),
                            CAST(:best_months AS jsonb),
                            CAST(:crowd_level_by_hour AS jsonb),
                            :dest_id, 'osm'
                        )
                    """), db_params)
                    inserted += 1

                db.execute(text("RELEASE SAVEPOINT poi_upsert"))

            except Exception as row_err:
                # Roll back only this row; leave the rest of the transaction intact.
                db.execute(text("ROLLBACK TO SAVEPOINT poi_upsert"))
                db.execute(text("RELEASE SAVEPOINT poi_upsert"))
                skipped += 1
                log.warning(f"    Row skipped ({p['name']}): {row_err}")

        db.commit()
        log.info(f"  Done: {inserted} inserted, {updated} updated, {skipped} skipped")
        return inserted + updated

    except Exception as e:
        db.rollback()
        log.error(f"  DB transaction failed for {city_name}: {e}")
        return 0
    finally:
        db.close()


def run_ingestion(city_filter: str = None):
    """
    Run ingestion for all destinations in the DB that have coordinates.
    Pass city_filter="Jaipur" to run for a single city only.
    """
    db = SessionLocal()
    try:
        destinations = db.execute(
            text("SELECT id, name, lat, lng FROM destination ORDER BY name")
        ).fetchall()
    finally:
        db.close()

    if not destinations:
        log.error("No destinations found in DB. Run enrich_destinations.py first.")
        return

    targets = [d for d in destinations if d.lat is not None and d.lng is not None]
    skipped_no_coords = len(destinations) - len(targets)

    if city_filter:
        targets = [d for d in targets if city_filter.lower() in d.name.lower()]
        if not targets:
            log.error(f"No destination matching '{city_filter}' found with coordinates.")
            return

    log.info(f"Starting ingestion: {len(targets)} cities")
    if skipped_no_coords:
        log.warning(f"Skipping {skipped_no_coords} destinations with no coordinates")

    total_ingested = 0
    for i, dest in enumerate(targets, 1):
        log.info(f"\n[{i}/{len(targets)}]")
        count = ingest_city_pois(dest.name, dest.id, dest.lat, dest.lng)
        total_ingested += count

        if i < len(targets):
            # Respect Overpass ToS: 5 seconds between city queries
            log.info("Throttling 5s for Overpass rate limit…")
            time.sleep(5)

    log.info(f"\n{'═'*50}")
    log.info(f"Ingestion complete: {total_ingested} total POIs across {len(targets)} cities")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Ingest OSM POIs for AltairGO destinations")
    parser.add_argument("--city", type=str, default=None,
                        help="Ingest a single city only (e.g. --city Jaipur)")
    parser.add_argument("--radius", type=int, default=RADIUS_METERS,
                        help=f"Search radius in meters (default: {RADIUS_METERS})")
    args = parser.parse_args()

    if args.city:
        db = SessionLocal()
        try:
            row = db.execute(
                text("SELECT id, lat, lng FROM destination WHERE LOWER(name) LIKE :p"),
                {"p": f"%{args.city.lower()}%"}
            ).fetchone()
        finally:
            db.close()

        if not row:
            log.error(f"Destination '{args.city}' not found in DB.")
        elif not row.lat or not row.lng:
            log.error(f"Destination '{args.city}' has no coordinates. Run enrich_destinations.py first.")
        else:
            ingest_city_pois(args.city, row.id, row.lat, row.lng, args.radius)
    else:
        run_ingestion()
