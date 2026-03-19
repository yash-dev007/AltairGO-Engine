import sys
import os
import time
import logging
import requests
from urllib.parse import quote
from dotenv import load_dotenv
load_dotenv()

# Add parent directory to path to import database
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from backend.database import SessionLocal
from backend.models import Attraction

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger(__name__)

GOOGLE_API_KEY      = os.environ.get("GOOGLE_MAPS_API_KEY", "")
WIKIDATA_SPARQL_URL = "https://query.wikidata.org/sparql"
WIKIPEDIA_API_URL   = "https://en.wikipedia.org/api/rest_v1/page/summary"


# ── Wikidata SPARQL ───────────────────────────────────────────────────────────

def fetch_wikidata_info(wikidata_id: str) -> dict:
    """
    Fetch label, description, and image from Wikidata for a given QID.
    Returns dict with keys: official_name, description, image_url, country, instance_of.
    Returns {} on any error or when the QID yields no results.
    """
    if not wikidata_id:
        return {}

    # f-string is clearer and avoids %s conflicts if the string ever changes
    sparql_query = f"""
    SELECT ?label ?description ?image ?countryLabel ?instanceLabel WHERE {{
      wd:{wikidata_id} rdfs:label ?label FILTER(LANG(?label) = "en").
      OPTIONAL {{ wd:{wikidata_id} schema:description ?description FILTER(LANG(?description) = "en"). }}
      OPTIONAL {{ wd:{wikidata_id} wdt:P18 ?image. }}
      OPTIONAL {{ wd:{wikidata_id} wdt:P17 ?country. ?country rdfs:label ?countryLabel FILTER(LANG(?countryLabel) = "en"). }}
      OPTIONAL {{ wd:{wikidata_id} wdt:P31 ?instance. ?instance rdfs:label ?instanceLabel FILTER(LANG(?instanceLabel) = "en"). }}
    }}
    LIMIT 1
    """

    try:
        resp = requests.get(
            WIKIDATA_SPARQL_URL,
            params={"query": sparql_query, "format": "json"},
            headers={"User-Agent": "AltairGO/1.0 (https://altairgo.in)"},
            timeout=15,
        )
        if resp.status_code != 200:
            return {}

        bindings = resp.json().get("results", {}).get("bindings", [])
        if not bindings:
            return {}

        r = bindings[0]
        return {
            "official_name": r.get("label",         {}).get("value"),
            "description":   r.get("description",   {}).get("value"),
            "image_url":     r.get("image",          {}).get("value"),
            "country":       r.get("countryLabel",   {}).get("value"),
            "instance_of":   r.get("instanceLabel",  {}).get("value"),
        }
    except Exception as e:
        log.warning(f"Wikidata SPARQL error for {wikidata_id}: {e}")
    return {}


# ── Wikipedia REST ────────────────────────────────────────────────────────────

def fetch_wikipedia_summary(name: str) -> dict:
    """
    Fetch a 2-3 sentence summary and main thumbnail from Wikipedia REST API.
    Returns dict with keys: description, main_image.
    Returns {} on any error or 404.

    The attraction name is URL-encoded so special characters and non-ASCII
    (e.g. diacritics in South Indian temple names) don't cause 404s.
    """
    try:
        # quote() handles &, ?, #, %, non-ASCII, etc.
        safe_name = quote(name.replace(" ", "_"), safe="")
        resp = requests.get(
            f"{WIKIPEDIA_API_URL}/{safe_name}",
            timeout=8,
        )
        if resp.status_code != 200:
            return {}

        data = resp.json()
        extract = data.get("extract", "")
        # Keep 2-3 sentences maximum
        sentences = extract.split(". ")
        if len(sentences) > 3:
            extract = ". ".join(sentences[:3]) + "."

        return {
            "description": extract or None,
            "main_image":  data.get("thumbnail", {}).get("source"),
        }
    except Exception as e:
        log.warning(f"Wikipedia API error for {name}: {e}")
    return {}


# ── Google Places ─────────────────────────────────────────────────────────────

def search_google_places(query: str, lat: float, lng: float):
    """
    Search Google Places by text query near lat/lng.
    Returns the first result dict or None.
    """
    if not GOOGLE_API_KEY:
        return None

    try:
        resp = requests.get(
            "https://maps.googleapis.com/maps/api/place/textsearch/json",
            params={
                "query":    query,
                "location": f"{lat},{lng}",
                "radius":   5000,
                "key":      GOOGLE_API_KEY,
            },
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        if data.get("status") == "OK" and data.get("results"):
            return data["results"][0]
    except Exception as e:
        log.warning(f"Google Places error for '{query}': {e}")
    return None


def get_google_place_details(place_id: str):
    """
    Fetch rating, review count, and photos for a Google place_id.
    Returns the result dict or None.
    """
    if not GOOGLE_API_KEY or not place_id:
        return None

    try:
        resp = requests.get(
            "https://maps.googleapis.com/maps/api/place/details/json",
            params={
                "place_id": place_id,
                "fields":   "rating,user_ratings_total,photos",
                "key":      GOOGLE_API_KEY,
            },
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        if data.get("status") == "OK":
            return data.get("result", {})
    except Exception as e:
        log.warning(f"Google Places Details error for {place_id}: {e}")
    return None


# ── Coordinate helpers ────────────────────────────────────────────────────────

def _get_coords(attraction) -> tuple[float | None, float | None]:
    """
    Return (lat, lng) for an attraction, preferring lat/lng over latitude/longitude.
    Uses `is not None` — NOT truthy check — so 0.0 is treated as a valid coordinate.
    Returns (None, None) if no valid coordinates exist.
    """
    lat = attraction.lat if attraction.lat is not None else attraction.latitude
    lng = attraction.lng if attraction.lng is not None else attraction.longitude
    # Treat (0.0, 0.0) as missing — the null-island guard from ingest_osm_data
    if lat == 0.0 and lng == 0.0:
        return None, None
    return lat, lng


# ── Main Enrichment Pipeline ──────────────────────────────────────────────────

def run_enrichment(batch_size: int = 200):
    """
    Enrich attractions via a Wikidata → Wikipedia → Google Places waterfall.

    Selection filter (OR):
      - google_rating IS NULL (never had Google enrichment)
      - gallery_images IS NULL (never had photo enrichment)
      - description IS NULL (never got a text description from any source)

    Args:
        batch_size: Max attractions per run. 0 = no limit (process all matching).
    """
    log.info("Starting POI enrichment (Wikidata → Wikipedia → Google Places)…")

    if not GOOGLE_API_KEY:
        log.warning("No GOOGLE_MAPS_API_KEY — Google ratings/images will be skipped.")

    db = SessionLocal()

    try:
        q = db.query(Attraction).filter(
            (Attraction.google_rating == None)   |  # noqa: E711
            (Attraction.gallery_images == None)  |  # noqa: E711
            (Attraction.description == None)        # noqa: E711 — also enrich desc-only gaps
        )
        if batch_size > 0:
            q = q.limit(batch_size)
        attractions = q.all()

        log.info(f"Found {len(attractions)} attractions requiring enrichment.")

        updated_count = 0

        for attraction in attractions:
            try:
                if _enrich_one(db, attraction):
                    updated_count += 1
            except Exception as e:
                # Per-attraction isolation — one bad row must not abort the batch.
                log.error(f"Failed to enrich '{attraction.name}' (id={attraction.id}): {e}")
                db.rollback()

        log.info(f"Enrichment complete. {updated_count} attractions updated.")

    except Exception as e:
        log.error(f"Enrichment pipeline failed: {e}")
        db.rollback()
    finally:
        db.close()


def _enrich_one(db, attraction) -> bool:
    """
    Run the full enrichment waterfall for a single attraction and commit.
    Returns True if at least one field was updated, False otherwise.
    Raises on unexpected errors — the caller handles isolation.
    """
    description = None
    photo_urls  = []
    rating      = None
    reviews     = 0

    # ── Step 1: Wikidata SPARQL ───────────────────────────────────
    wikidata_id = attraction.wikidata_id
    if wikidata_id:
        wd = fetch_wikidata_info(wikidata_id)
        got_wd_desc  = bool(wd.get("description"))
        got_wd_image = bool(wd.get("image_url"))

        if got_wd_desc:
            description = wd["description"]
        if got_wd_image:
            photo_urls.append(wd["image_url"])

        if got_wd_desc or got_wd_image:
            log.info(f"  Wikidata [{wikidata_id}]: desc={'yes' if got_wd_desc else 'no'}, "
                     f"image={'yes' if got_wd_image else 'no'} — {attraction.name}")
        else:
            log.debug(f"  Wikidata [{wikidata_id}]: no data returned — {attraction.name}")

        time.sleep(1)   # Wikidata SPARQL rate limit

    # ── Step 2: Wikipedia REST (only when Wikidata had no description) ────
    if not description:
        wiki = fetch_wikipedia_summary(attraction.name)
        if wiki.get("description"):
            description = wiki["description"]
        if wiki.get("main_image") and len(photo_urls) < 3:
            photo_urls.append(wiki["main_image"])
        time.sleep(0.5)

    # ── Step 3: Google Places ─────────────────────────────────────
    lat, lng = _get_coords(attraction)
    if lat is not None and lng is not None:
        place_info = search_google_places(f"{attraction.name} tourism", lat, lng)
        if place_info:
            place_id = place_info.get("place_id")
            rating   = place_info.get("rating")
            reviews  = place_info.get("user_ratings_total", 0)

            # place_id guard — malformed responses can omit it
            if place_id:
                details = get_google_place_details(place_id)
                if details:
                    rating  = details.get("rating", rating)
                    reviews = details.get("user_ratings_total", reviews)

                    # Photo references (up to 3 total across all sources)
                    slots  = max(0, 3 - len(photo_urls))
                    photos = details.get("photos", [])[:slots]
                    for p in photos:
                        ref = p.get("photo_reference")
                        if ref:
                            url = (
                                "https://maps.googleapis.com/maps/api/place/photo"
                                f"?maxwidth=800&photo_reference={ref}&key={GOOGLE_API_KEY}"
                            )
                            photo_urls.append(url)
    else:
        log.debug(f"  No coordinates for '{attraction.name}' — skipping Google Places.")

    # ── Persist ───────────────────────────────────────────────────
    needs_update = False

    # Description: only fill when empty (don't overwrite manual curation)
    if description and not attraction.description:
        attraction.description = description[:1000]
        needs_update = True

    # Google rating + review count
    if rating is not None:
        attraction.google_rating = float(rating)
        attraction.review_count  = int(reviews)
        needs_update = True

    # Photo gallery: merge new URLs into existing, cap at 5
    if photo_urls:
        existing = list(attraction.gallery_images or [])
        for url in photo_urls:
            if url not in existing:
                existing.append(url)
        attraction.gallery_images = existing[:5]
        needs_update = True

    if needs_update:
        log.info(
            f"Enriched: {attraction.name} | "
            f"rating={attraction.google_rating} | "
            f"photos={len(attraction.gallery_images or [])} | "
            f"desc={'yes' if attraction.description else 'no'}"
        )
    else:
        log.info(f"No data found for '{attraction.name}' via any API.")
        # Set sentinels on ALL three filter fields so the batch query
        # (google_rating IS NULL OR gallery_images IS NULL OR description IS NULL)
        # does not re-select this attraction on future runs.
        # Sentinels: [] / "" / 0.0 — all falsy so scoring treats them as "no data".
        # (0.0 is not a valid POI rating; no legitimate attraction scores this low.)
        if attraction.gallery_images is None:
            attraction.gallery_images = []
        if attraction.description is None:
            attraction.description = ""
        if attraction.google_rating is None:
            attraction.google_rating = 0.0

    db.commit()
    # Expire only THIS attraction to free memory; other objects in the session
    # stay warm so the next iteration doesn't trigger unnecessary lazy SELECTs.
    db.expire(attraction)

    time.sleep(1)   # Google Places / general rate limit
    return needs_update


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(
        description="Enrich attraction POIs via Wikidata / Wikipedia / Google Places."
    )
    parser.add_argument(
        "--all", dest="process_all", action="store_true",
        help="Process all unenriched attractions (no batch limit).",
    )
    parser.add_argument(
        "--batch", type=int, default=200,
        help="Max attractions to process per run (default: 200).",
    )
    parser.add_argument(
        "--destination", type=int, default=None,
        metavar="DEST_ID",
        help="Restrict enrichment to a single destination ID.",
    )
    args = parser.parse_args()

    if args.destination:
        # Targeted single-city run for testing / manual correction
        db = SessionLocal()
        try:
            q = db.query(Attraction).filter(
                Attraction.destination_id == args.destination,
            ).filter(
                (Attraction.google_rating == None)  |  # noqa: E711
                (Attraction.gallery_images == None) |  # noqa: E711
                (Attraction.description == None)       # noqa: E711
            )
            attractions = q.all()
            log.info(f"Targeted run: {len(attractions)} attractions for dest_id={args.destination}")
            updated = 0
            for a in attractions:
                try:
                    if _enrich_one(db, a):
                        updated += 1
                except Exception as e:
                    log.error(f"Failed '{a.name}': {e}")
                    db.rollback()
            log.info(f"Targeted enrichment complete. {updated} attractions updated.")
        finally:
            db.close()
    else:
        run_enrichment(batch_size=0 if args.process_all else args.batch)
