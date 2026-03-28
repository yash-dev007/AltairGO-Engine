"""
services/feature_flags.py — Feature Flag Service
══════════════════════════════════════════════════

Activates the existing FeatureFlag model so engine parameters can be toggled
without redeployment.  Supports traffic_pct for gradual rollouts:

  - is_enabled("gemini_polish_v2")            → True/False for 100% rollout
  - is_enabled("new_filter_logic", user_id=7) → deterministic per user for partial %

Flags are cached for 60 seconds to avoid a DB query on every request.
The cache is invalidated when a flag is created/updated via the admin API.
"""

import hashlib
import time
import threading

import structlog

log = structlog.get_logger(__name__)

_CACHE_TTL = 60  # seconds
_cache: dict[str, tuple] = {}  # {flag_key: (FeatureFlag | None, fetched_at)}
_cache_lock = threading.Lock()


def is_enabled(flag_key: str, user_id: int | None = None) -> bool:
    """
    Return True if the feature flag is active for the given user.

    Traffic bucketing is deterministic: a given (flag_key, user_id) pair
    always falls in the same bucket so a user gets a consistent experience.
    """
    flag = _get_flag(flag_key)
    if flag is None or not flag.is_active:
        return False
    if flag.traffic_pct >= 100:
        return True
    if flag.traffic_pct <= 0:
        return False

    # Deterministic bucket 0-99 based on flag_key + user_id
    seed = f"{flag_key}:{user_id or 'anon'}"
    bucket = int(hashlib.md5(seed.encode(), usedforsecurity=False).hexdigest(), 16) % 100
    return bucket < flag.traffic_pct


def invalidate(flag_key: str | None = None):
    """
    Evict one flag (or all flags) from the local cache.
    Call this after creating or updating a flag via the admin API.
    """
    with _cache_lock:
        if flag_key:
            _cache.pop(flag_key, None)
        else:
            _cache.clear()


def _get_flag(flag_key: str):
    """Return a FeatureFlag ORM object from cache or DB, or None if not found."""
    now = time.monotonic()
    with _cache_lock:
        cached = _cache.get(flag_key)
        if cached:
            value, fetched_at = cached
            if now - fetched_at < _CACHE_TTL:
                return value

    try:
        from backend.database import db
        from backend.models import FeatureFlag

        flag = db.session.query(FeatureFlag).filter_by(flag_key=flag_key).first()
        with _cache_lock:
            _cache[flag_key] = (flag, now)
        return flag
    except Exception as exc:
        log.warning("feature_flag.db_read_failed", flag_key=flag_key, error=str(exc))
        return None
