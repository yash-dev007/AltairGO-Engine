"""
image_service.py — Multi-source image fetcher for AltairGO.
Priority chain: Wikipedia → Wikidata (SPARQL P18) → Pexels → SVG placeholder.
"""

import os
import re
import requests
from concurrent.futures import ThreadPoolExecutor, TimeoutError
import structlog

log = structlog.get_logger(__name__)

MAX_IMAGE_BYTES = 5 * 1024 * 1024  # 5 MB cap for dimension checks

PEXELS_API_KEY = os.getenv("PEXELS_API_KEY", "")
MIN_WIDTH = 800
MIN_HEIGHT = 600

# Wikidata SPARQL endpoint
WIKIDATA_SPARQL_URL = "https://query.wikidata.org/sparql"

# Minimal SVG placeholder (data URI)
SVG_PLACEHOLDER = (
    "data:image/svg+xml,"
    "%3Csvg xmlns='http://www.w3.org/2000/svg' width='800' height='600'%3E"
    "%3Crect width='800' height='600' fill='%23e0e0e0'/%3E"
    "%3Ctext x='400' y='300' text-anchor='middle' fill='%23999' "
    "font-size='24'%3ENo image available%3C/text%3E%3C/svg%3E"
)


class ImageService:
    """Fetches the best available image for an attraction."""

    def __init__(self, pexels_key=None):
        self.pexels_key = pexels_key or PEXELS_API_KEY

    def get_image(self, name: str, category: str = "attraction") -> str:
        """Return the best image URL or an SVG data URI as fallback."""
        # Query external image sources in parallel so one slow provider does not delay the whole response.
        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = {
                "wikipedia": executor.submit(self.get_image_from_wikipedia, name),
                "wikidata": executor.submit(self.get_image_from_wikidata, name),
                "pexels": executor.submit(self.get_image_from_pexels, name),
            }

            results = {}
            for source_name, future in futures.items():
                try:
                    results[source_name] = future.result(timeout=5)
                except TimeoutError:
                    log.debug(f"{source_name} image fetch timed out for '{name}'")
                    results[source_name] = None
                except Exception as e:
                    log.debug(f"{source_name} image fetch failed for '{name}': {e}")
                    results[source_name] = None

        url = results.get("wikipedia")
        if url and self.is_image_acceptable(url):
            return url

        url = results.get("wikidata")
        if url and self.is_image_acceptable(url):
            return url

        url = results.get("pexels")
        if url:
            return url

        return SVG_PLACEHOLDER

    # ── Sources ──────────────────────────────────────────────────

    def get_image_from_wikipedia(self, name: str):
        """Fetch thumbnail from Wikipedia REST API."""
        try:
            safe_name = name.replace(" ", "_")
            url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{safe_name}"
            resp = requests.get(url, timeout=5)
            if resp.status_code != 200:
                return None
            data = resp.json()
            thumb = data.get("thumbnail", {}).get("source")
            return thumb
        except Exception as e:
            log.debug(f"Wikipedia image fetch failed for '{name}': {e}")
            return None

    def get_image_from_wikidata(self, name: str):
        """Fetch image from Wikidata SPARQL endpoint using P18 (image) property."""
        try:
            # Sanitize input to prevent SPARQL injection:
            # Strip all non-alphanumeric/space/apostrophe/hyphen characters, limit length
            safe_name = re.sub(r"[^\w\s'\-]", "", name)[:100]
            sparql_query = """
            SELECT ?image WHERE {
              ?item rdfs:label "%s"@en .
              ?item wdt:P18 ?image .
            }
            LIMIT 1
            """ % safe_name.replace('"', '\\"')

            resp = requests.get(
                WIKIDATA_SPARQL_URL,
                params={"query": sparql_query, "format": "json"},
                headers={"User-Agent": "AltairGO/1.0 (https://altairgo.ai)"},
                timeout=10,
            )

            if resp.status_code != 200:
                return None

            results = resp.json().get("results", {}).get("bindings", [])
            if results:
                image_url = results[0].get("image", {}).get("value")
                if image_url:
                    # Wikidata returns Wikimedia Commons filename URL
                    # Convert to a direct thumbnail URL
                    return image_url
            return None
        except Exception as e:
            log.debug(f"Wikidata SPARQL image fetch failed for '{name}': {e}")
            return None

    def get_image_from_pexels(self, name: str):
        """Fetch image from Pexels API."""
        if not self.pexels_key:
            return None
        try:
            resp = requests.get(
                "https://api.pexels.com/v1/search",
                headers={"Authorization": self.pexels_key},
                params={"query": name, "per_page": 1},
                timeout=5,
            )
            if resp.status_code != 200:
                return None
            photos = resp.json().get("photos", [])
            if photos:
                return photos[0]["src"]["large"]
            return None
        except Exception as e:
            log.debug(f"Pexels image fetch failed for '{name}': {e}")
            return None

    # ── Quality checks ───────────────────────────────────────────

    def is_image_acceptable(self, url: str) -> bool:
        """Check if image meets minimum resolution (800x600)."""
        if not url or url.startswith("data:"):
            return False
        width, height = self._fetch_image_dimensions(url)
        return width >= MIN_WIDTH and height >= MIN_HEIGHT

    @staticmethod
    def _fetch_image_dimensions(url: str):
        """Fetch image and return (width, height) with size cap to prevent OOM."""
        try:
            from PIL import Image
            from io import BytesIO
            resp = requests.get(url, timeout=5, stream=True)
            # Read up to MAX_IMAGE_BYTES to prevent OOM on huge images
            content = resp.raw.read(MAX_IMAGE_BYTES + 1)
            if len(content) > MAX_IMAGE_BYTES:
                log.debug(f"Image too large for dimension check: {url}")
                return (800, 600)  # Accept large images without full check
            img = Image.open(BytesIO(content))
            return img.size
        except Exception:
            # If PIL not available or fetch fails, accept the image
            return (800, 600)
