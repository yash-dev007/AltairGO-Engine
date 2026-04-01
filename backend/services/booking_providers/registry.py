"""
booking_providers/registry.py — Provider registry
══════════════════════════════════════════════════

Maps booking_type strings to BookingProvider instances.
When no specific provider is registered for a type, the default
SimulatedProvider is returned so execution never fails silently.

Usage:
  from backend.services.booking_providers import get_provider, register

  # Register a real provider for hotels at app startup:
  register("hotel", BookingComProvider())

  # Route code:
  result = get_provider(booking.booking_type).execute(booking)
"""

from .base import BookingProvider
from .simulated import SimulatedProvider

_providers: dict[str, BookingProvider] = {}
_default_provider: BookingProvider = SimulatedProvider()


def get_provider(booking_type: str) -> BookingProvider:
    """Return the registered provider for booking_type, or the default SimulatedProvider."""
    return _providers.get(booking_type or "", _default_provider)


def register(booking_type: str, provider: BookingProvider) -> None:
    """Register a provider for a booking type. Thread-safe (dict assignment is atomic in CPython)."""
    if not isinstance(provider, BookingProvider):
        raise TypeError(f"provider must be a BookingProvider instance, got {type(provider)}")
    _providers[booking_type] = provider


def registered_types() -> list[str]:
    """Return the booking types that have real (non-default) providers registered."""
    return list(_providers.keys())
