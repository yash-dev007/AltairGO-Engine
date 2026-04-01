"""
booking_providers/simulated.py — Simulated (test/demo) provider
═══════════════════════════════════════════════════════════════

Generates fake booking references so the full booking flow can be tested
end-to-end without connecting to any real vendor API.

All responses carry simulated=True so the frontend can display a
"simulated booking" disclaimer.
"""

import secrets

from .base import BookingProvider, BookingResult


class SimulatedProvider(BookingProvider):
    """Default provider — no external calls, always succeeds with a fake ref."""

    def execute(self, booking) -> BookingResult:
        prefix = (booking.booking_type or "BKG").upper()[:3]
        ref = f"ALTAIR-{prefix}-{secrets.token_hex(4).upper()}"
        return BookingResult(
            success=True,
            booking_ref=ref,
            booking_url=booking.booking_url or None,
            simulated=True,
        )

    def cancel(self, booking) -> BookingResult:
        return BookingResult(
            success=True,
            booking_ref=booking.booking_ref,
            booking_url=None,
            simulated=True,
        )
