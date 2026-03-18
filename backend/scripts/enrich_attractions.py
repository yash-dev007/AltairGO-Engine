import sys
import os
import json
import time
import logging
import requests
from dotenv import load_dotenv
load_dotenv()
from sqlalchemy import text

# Add parent directory to path to import database
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from backend.database import SessionLocal
from backend.models import Attraction

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger(__name__)

GOOGLE_API_KEY = os.environ.get("GOOGLE_MAPS_API_KEY", "")
WIKIDATA_SPARQL_URL = "https://query.wikidata.org/sparql"
WIKIPEDIA_API_URL = "https://en.wikipedia.org/api/rest_v1/page/summary"


# ── Step 2a: Wikidata SPARQL Enrichment ──────────────────────────────

def fetch_wikidata_info(wikidata_id: str) -> dict:
    """
    Fetch label, description, and image from Wikidata for a given QID.
    Returns: {official_name, description, image_url, country, instance_of}
    """
    if not wikidata_id:
        return {}

    sparql_query = """
    SELECT ?label ?description ?image ?country ?countryLabel ?instanceLabel WHERE {
      wd:%s rdfs:label ?label FILTER(LANG(?label) = "en").
      OPTIONAL { wd:%s schema:description ?description FILTER(LANG(?description) = "en"). }
      OPTIONAL { wd:%s wdt:P18 ?image. }
      OPTIONAL { wd:%s wdt:P17 ?country. ?country rdfs:label ?countryLabel FILTER(LANG(?countryLabel) = "en"). }
      OPTIONAL { wd:%s wdt:P31 ?instance. ?instance rdfs:label ?instanceLabel FILTER(LANG(?instanceLabel) = "en"). }
    }
    LIMIT 1
    """ % (wikidata_id, wikidata_id, wikidata_id, wikidata_id, wikidata_id)

    try:
        resp = requests.get(
            WIKIDATA_SPARQL_URL,
            params={"query": sparql_query, "format": "json"},
            headers={"User-Agent": "AltairGO/1.0 (https://altairgo.ai)"},
            timeout=15,
        )
        if resp.status_code != 200:
            return {}

        results = resp.json().get("results", {}).get("bindings", [])
        if not results:
            return {}

        r = results[0]
        return {
            "official_name": r.get("label", {}).get("value"),
            "description": r.get("description", {}).get("value"),
            "image_url": r.get("image", {}).get("value"),
            "country": r.get("countryLabel", {}).get("value"),
            "instance_of": r.get("instanceLabel", {}).get("value"),
        }
    except Exception as e:
        log.warning(f"Wikidata SPARQL error for {wikidata_id}: {e}")
    return {}


# ── Step 2b: Wikipedia REST Description ──────────────────────────────

def fetch_wikipedia_summary(name: str) -> dict:
    """
    Fetch a 2-3 sentence summary and main image from Wikipedia REST API.
    Returns: {description, main_image, categories}
    """
    try:
        safe_name = name.replace(" ", "_")
        resp = requests.get(
            f"{WIKIPEDIA_API_URL}/{safe_name}",
            timeout=8,
        )
        if resp.status_code != 200:
            return {}

        data = resp.json()
        description = data.get("extract", "")
        # Truncate to 2-3 sentences
        sentences = description.split(". ")
        if len(sentences) > 3:
            description = ". ".join(sentences[:3]) + "."

        return {
            "description": description,
            "main_image": data.get("thumbnail", {}).get("source"),
        }
    except Exception as e:
        log.warning(f"Wikipedia API error for {name}: {e}")
    return {}


# ── Step 2d: Google Places ───────────────────────────────────────────

def search_google_places(query: str, lat: float, lng: float):
    if not GOOGLE_API_KEY:
        return None

    url = "https://maps.googleapis.com/maps/api/place/textsearch/json"
    params = {
        "query": query,
        "location": f"{lat},{lng}",
        "radius": 5000,
        "key": GOOGLE_API_KEY
    }

    try:
        res = requests.get(url, params=params, timeout=10)
        res.raise_for_status()
        data = res.json()
        if data.get("status") == "OK" and data.get("results"):
            return data["results"][0]
    except Exception as e:
        log.warning(f"Google Places API error for {query}: {e}")

    return None


def get_google_place_details(place_id: str):
    if not GOOGLE_API_KEY:
        return None

    url = "https://maps.googleapis.com/maps/api/place/details/json"
    params = {
        "place_id": place_id,
        "fields": "rating,user_ratings_total,photos",
        "key": GOOGLE_API_KEY
    }

    try:
        res = requests.get(url, params=params, timeout=10)
        res.raise_for_status()
        data = res.json()
        if data.get("status") == "OK":
            return data.get("result", {})
    except Exception as e:
        log.warning(f"Google Places Details error for {place_id}: {e}")

    return None


# ── Main Enrichment Pipeline (Waterfall Pattern) ─────────────────────

def run_enrichment(batch_size: int = 200):
    """
    Enrich attractions via Wikidata → Wikipedia → Google Places waterfall.

    Args:
        batch_size: How many attractions to process per run (default 200).
                    Set to 0 to process all unenriched attractions in one shot.
                    Pass --all from CLI to process everything.
    """
    log.info("Starting POI enrichment (Wikidata → Wikipedia → Google Places)...")

    if not GOOGLE_API_KEY:
        log.warning("No GOOGLE_MAPS_API_KEY found. Google ratings/images will be skipped.")

    db = SessionLocal()

    try:
        q = db.query(Attraction).filter(
            (Attraction.google_rating == None) | (Attraction.gallery_images == None)
        )
        if batch_size > 0:
            q = q.limit(batch_size)
        attractions = q.all()

        log.info(f"Found {len(attractions)} attractions requiring enrichment.")

        updated_count = 0
        for attraction in attractions:
            description = None
            rating = None
            reviews = 0
            photo_urls = []

            # ── Step 2a: Wikidata SPARQL ──────────────────────────
            wikidata_id = getattr(attraction, 'wikidata_id', None)
            if wikidata_id:
                wd_info = fetch_wikidata_info(wikidata_id)
                if wd_info.get("description"):
                    description = wd_info["description"]
                if wd_info.get("image_url"):
                    photo_urls.append(wd_info["image_url"])
                log.info(f"  Wikidata enriched: {attraction.name} ({wikidata_id})")
                time.sleep(1)

            # ── Step 2b: Wikipedia REST ───────────────────────────
            if not description:
                wiki_info = fetch_wikipedia_summary(attraction.name)
                if wiki_info.get("description"):
                    description = wiki_info["description"]
                if wiki_info.get("main_image") and len(photo_urls) < 3:
                    photo_urls.append(wiki_info["main_image"])
                time.sleep(0.5)

            # ── Step 2d: Google Places ────────────────────────────
            query = f"{attraction.name} tourism"
            lat = getattr(attraction, 'lat', None) or getattr(attraction, 'latitude', 0)
            lng = getattr(attraction, 'lng', None) or getattr(attraction, 'longitude', 0)

            place_info = search_google_places(query, lat, lng)

            if place_info:
                place_id = place_info.get("place_id")
                rating = place_info.get("rating")
                reviews = place_info.get("user_ratings_total", 0)

                # Fetch details for photos
                details = get_google_place_details(place_id)
                if details:
                    rating = details.get("rating", rating)
                    reviews = details.get("user_ratings_total", reviews)

                    # Convert photo references to URLs (max 3 total)
                    photos = details.get("photos", [])[:max(0, 3 - len(photo_urls))]
                    for p in photos:
                        photo_ref = p.get("photo_reference")
                        if photo_ref:
                            url = f"https://maps.googleapis.com/maps/api/place/photo?maxwidth=800&photo_reference={photo_ref}&key={GOOGLE_API_KEY}"
                            photo_urls.append(url)

            # ── Update DB ─────────────────────────────────────────
            needs_update = False

            if description and not attraction.description:
                attraction.description = description[:1000]
                needs_update = True

            if rating is not None:
                attraction.google_rating = float(rating)
                attraction.review_count = int(reviews)
                needs_update = True

            if photo_urls:
                existing_urls = attraction.gallery_images or []
                for url in photo_urls:
                    if url not in existing_urls:
                        existing_urls.append(url)
                attraction.gallery_images = existing_urls[:5]  # Cap at 5
                needs_update = True

            if needs_update:
                log.info(f"Enriched: {attraction.name} (Rating: {attraction.google_rating}, Photos: {len(attraction.gallery_images or [])}, Desc: {'yes' if description else 'no'})")
                updated_count += 1
            else:
                log.info(f"Could not enrich {attraction.name} via any API.")
                if attraction.gallery_images is None:
                    attraction.gallery_images = []

            db.commit()
            time.sleep(1)

        log.info(f"Enrichment complete. Updated {updated_count} attractions.")

    except Exception as e:
        log.error(f"Enrichment pipeline failed: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Enrich attraction POIs via Wikidata/Wikipedia/Google.")
    parser.add_argument("--all", dest="process_all", action="store_true",
                        help="Process all unenriched attractions (no batch limit).")
    parser.add_argument("--batch", type=int, default=200,
                        help="Max attractions to process per run (default: 200).")
    args = parser.parse_args()
    run_enrichment(batch_size=0 if args.process_all else args.batch)
