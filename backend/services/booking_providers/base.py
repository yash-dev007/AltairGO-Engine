"""
booking_providers/base.py — Abstract BookingProvider interface
══════════════════════════════════════════════════════════════

All booking providers implement this interface so route logic stays stable
while vendor SDK implementations are plugged in one at a time.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class BookingResult:
    """Unified result returned by every provider."""
    success: bool
    booking_ref: str | None = None
    booking_url: str | None = None
    simulated: bool = True
    error: str | None = None
    # Extra provider-specific data surfaced to the frontend
    extra: dict = field(default_factory=dict)


class BookingProvider(ABC):
    """
    Abstract base for a booking vendor.

    Implementations:
      - SimulatedProvider  — generates fake refs (current default)
      - BookingComProvider — Booking.com affiliate deep-links (hotel)
      - MakeMyTripProvider — MakeMyTrip deep-links (flight)
    """

    @abstractmethod
    def execute(self, booking) -> BookingResult:
        """
        Attempt to confirm a booking.
        booking: a Booking ORM object.
        Returns BookingResult with success=True on confirmation.
        """

    @abstractmethod
    def cancel(self, booking) -> BookingResult:
        """
        Request cancellation of a previously confirmed booking.
        Returns BookingResult with success=True on cancellation.
        """

    def check_status(self, booking) -> BookingResult:
        """
        Optional: poll vendor API for current booking status.
        Default implementation returns the current DB status unchanged.
        """
        return BookingResult(
            success=True,
            booking_ref=booking.booking_ref,
            simulated=True,
        )
