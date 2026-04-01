"""
booking_providers/bookingcom.py — Booking.com Affiliate Provider
═════════════════════════════════════════════════════════════════

Generates Booking.com affiliate deep-links for hotel bookings.

Revenue model: affiliate commission when the traveler completes the
booking on Booking.com (no direct transaction handled by AltairGO).

Required env var: BOOKINGCOM_AFFILIATE_ID
Optional env var: BOOKINGCOM_LABEL_PREFIX (default: "altairgo")

When BOOKINGCOM_AFFILIATE_ID is not set, falls back to SimulatedProvider
so development/testing works without credentials.
"""

import os
from urllib.parse import urlencode

import structlog

from .base import BookingProvider, BookingResult
from .simulated import SimulatedProvider

log = structlog.get_logger(__name__)

_AFFILIATE_ID = os.getenv("BOOKINGCOM_AFFILIATE_ID", "")
_LABEL_PREFIX = os.getenv("BOOKINGCOM_LABEL_PREFIX", "altairgo")
_BASE_SEARCH_URL = "https://www.booking.com/searchresults.html"
_BASE_HOTEL_URL = "https://www.booking.com/hotel/in/{slug}.html"
_MY_RESERVATIONS_URL = "https://www.booking.com/myreservations.html"


class BookingComProvider(BookingProvider):
    """
    Booking.com affiliate deep-link generator.

    For hotel bookings: builds a Booking.com search/property URL with
    check-in/check-out dates, guest count, and affiliate tracking.
    The user is redirected to Booking.com to complete the transaction.
    """

    def execute(self, booking) -> BookingResult:
        if not _AFFILIATE_ID:
            log.warning("bookingcom.no_affiliate_id — falling back to simulated")
            return SimulatedProvider().execute(booking)

        try:
            params = {
                "aid": _AFFILIATE_ID,
                "label": f"{_LABEL_PREFIX}-trip-{booking.trip_id}",
                "lang": "en-gb",
                "no_rooms": max(1, (booking.num_travelers or 1 + 1) // 2),
                "group_adults": booking.num_travelers or 1,
            }

            if booking.start_datetime:
                params["checkin"] = booking.start_datetime.strftime("%Y-%m-%d")
            if booking.end_datetime:
                params["checkout"] = booking.end_datetime.strftime("%Y-%m-%d")

            # If hotel name is known, pre-fill the search
            if booking.item_name:
                params["ss"] = booking.item_name

            # Check payload for a hotel slug (enables direct property page)
            payload = booking.payload or {}
            slug = payload.get("hotel_slug")
            if slug:
                base = _BASE_HOTEL_URL.format(slug=slug)
            else:
                base = _BASE_SEARCH_URL

            affiliate_url = f"{base}?{urlencode(params)}"
            ref = f"BCM-{str(booking.id)[:8].upper()}"

            log.info("bookingcom.link_generated", trip_id=booking.trip_id, ref=ref)

            return BookingResult(
                success=True,
                booking_ref=ref,
                booking_url=affiliate_url,
                simulated=False,
                extra={"provider": "Booking.com", "affiliate_id": _AFFILIATE_ID},
            )

        except Exception as exc:
            log.exception("bookingcom.execute_failed", error=str(exc))
            return BookingResult(
                success=False,
                error=str(exc),
                simulated=False,
            )

    def cancel(self, booking) -> BookingResult:
        """
        Booking.com cancellations are handled on their platform.
        Return a direct link to the user's reservations page.
        """
        return BookingResult(
            success=True,
            booking_ref=booking.booking_ref,
            booking_url=_MY_RESERVATIONS_URL,
            simulated=False,
            extra={"note": "Please cancel directly on Booking.com"},
        )
