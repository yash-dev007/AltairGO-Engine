import logging
from datetime import datetime, timezone

import requests

from backend.services.metrics_service import get_metric, mark_status, set_metric

log = logging.getLogger(__name__)

PARTNERS = {
    "makemytrip": "https://www.makemytrip.com/hotels/",
    "booking": "https://www.booking.com/",
}


def check_affiliate_health() -> dict:
    results = {}
    for partner, url in PARTNERS.items():
        entry = {
            "healthy": False,
            "checked_at": datetime.now(timezone.utc).isoformat(),
        }
        try:
            response = requests.head(url, allow_redirects=True, timeout=10)
            entry.update({
                "status_code": response.status_code,
                "healthy": response.status_code < 400,
                "final_url": response.url,
            })
        except Exception as exc:
            entry["error"] = str(exc)

        results[partner] = entry

    set_metric("affiliate:health", results, ttl_seconds=24 * 60 * 60)
    mark_status("agent", "affiliate_health", "ok", results)
    return results
