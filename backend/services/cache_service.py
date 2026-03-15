import hashlib, json, os
import redis
import structlog

from backend.services.metrics_service import incr_daily_counter

log = structlog.get_logger(__name__)
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# TTLs per cache level (in seconds)
TTL_ITINERARY = 72 * 60 * 60       # 72 hours for full itineraries
TTL_CLUSTERS  = 7 * 24 * 60 * 60   # 7 days for destination clusters
TTL_HOTELS    = 12 * 60 * 60       # 12 hours for hotel prices
TTL_FLIGHTS   = 6 * 60 * 60        # 6 hours for flight routes
TTL_SCORES    = 30 * 24 * 60 * 60  # 30 days for attraction scores
TTL_POLISH    = 30 * 24 * 60 * 60  # 30 days for AI polish text

try:
    _r = redis.from_url(REDIS_URL, decode_responses=True)
    _r.ping()
    log.info("Redis connected")
    REDIS_OK = True
except Exception as e:
    log.warning(f"Redis not available, caching disabled: {e}")
    REDIS_OK = False
    _r = None


def get_cache_key(prefix: str, params: dict) -> str:
    param_str = json.dumps(params, sort_keys=True)
    hash_val = hashlib.md5(param_str.encode()).hexdigest()[:12]
    return f"{prefix}:{hash_val}"


def make_cache_key(prefix: str, *parts: str) -> str:
    normalised = "_".join(str(p).strip().lower().replace(" ", "_") for p in parts)
    return f"{prefix}:{normalised}"


def _redis_call(operation: str, default, fn):
    # Swallow Redis outages so cache failures degrade to cache misses instead of request failures.
    if not REDIS_OK or _r is None:
        return default
    try:
        return fn()
    except Exception as e:
        log.warning(f"Redis {operation} failed: {e}")
        return default


# ── Full Itinerary Cache ─────────────────────────────────────────────

def _key(user_prefs: dict) -> str:
    return get_cache_key("trip", _normalize(user_prefs))


def _normalize(value):
    if isinstance(value, dict):
        return {k: _normalize(v) for k, v in sorted(value.items())}
    if isinstance(value, list):
        return [_normalize(item) for item in value]
    if isinstance(value, str):
        return value.strip().lower().replace(" ", "_")
    return value


def _label(user_prefs: dict) -> str:
    destinations = user_prefs.get("destination_names") or []
    if destinations:
        return ",".join(destinations)
    return user_prefs.get("city", "unknown")


def get_cached(user_prefs: dict):
    def _load():
        data = _r.get(_key(user_prefs))
        if data:
            incr_daily_counter("metrics:cache_hits")
            log.info(
                f"Cache HIT: {_label(user_prefs)}/"
                f"{user_prefs.get('duration', user_prefs.get('days'))}d"
            )
            return json.loads(data)
        incr_daily_counter("metrics:cache_misses")
        return None

    return _redis_call("get", None, _load)


def set_cached(user_prefs: dict, itinerary: dict):
    def _store():
        _r.setex(_key(user_prefs), TTL_ITINERARY, json.dumps(itinerary))
        log.info(
            f"Cache SET: {_label(user_prefs)}/"
            f"{user_prefs.get('duration', user_prefs.get('days'))}d"
        )
        return None

    return _redis_call("set", None, _store)


def invalidate(user_prefs: dict):
    return _redis_call("delete", None, lambda: _r.delete(_key(user_prefs)))


# ── Destination Cluster Cache (~80% hit rate, 7 day TTL) ─────────────

def get_cached_clusters(city_id: int, num_days: int):
    def _load():
        key = make_cache_key("clusters", city_id, num_days)
        data = _r.get(key)
        return json.loads(data) if data else None

    return _redis_call("get_clusters", None, _load)


def set_cached_clusters(city_id: int, num_days: int, clusters: dict):
    def _store():
        key = make_cache_key("clusters", city_id, num_days)
        _r.setex(key, TTL_CLUSTERS, json.dumps(clusters, default=str))
        return None

    return _redis_call("set_clusters", None, _store)


# ── Hotel Price Cache (~90% hit rate, 12 hour TTL) ───────────────────

def get_cached_hotels(dest_id: int, tier: str):
    def _load():
        key = make_cache_key("hotels", dest_id, tier)
        data = _r.get(key)
        return json.loads(data) if data else None

    return _redis_call("get_hotels", None, _load)


def set_cached_hotels(dest_id: int, tier: str, hotel_data: dict):
    def _store():
        key = make_cache_key("hotels", dest_id, tier)
        _r.setex(key, TTL_HOTELS, json.dumps(hotel_data))
        return None

    return _redis_call("set_hotels", None, _store)


# ── Flight Route Cache (~85% hit rate, 6 hour TTL) ───────────────────

def get_cached_flights(origin: str, destination: str):
    def _load():
        key = make_cache_key("flights", origin, destination)
        data = _r.get(key)
        return json.loads(data) if data else None

    return _redis_call("get_flights", None, _load)


def set_cached_flights(origin: str, destination: str, flight_data: dict):
    def _store():
        key = make_cache_key("flights", origin, destination)
        _r.setex(key, TTL_FLIGHTS, json.dumps(flight_data))
        return None

    return _redis_call("set_flights", None, _store)


# ── Attraction Score Cache (~95% hit rate, 30 day TTL) ───────────────

def get_cached_scores(city_id: int):
    def _load():
        key = make_cache_key("scores", city_id)
        data = _r.get(key)
        return json.loads(data) if data else None

    return _redis_call("get_scores", None, _load)


def set_cached_scores(city_id: int, scores: dict):
    def _store():
        key = make_cache_key("scores", city_id)
        _r.setex(key, TTL_SCORES, json.dumps(scores))
        return None

    return _redis_call("set_scores", None, _store)


# ── AI Polish Text Cache (~60% hit rate, 30 day TTL) ────────────────

def get_cached_polish(attraction_id: int, style: str):
    def _load():
        key = make_cache_key("polish", attraction_id, style)
        data = _r.get(key)
        return json.loads(data) if data else None

    return _redis_call("get_polish", None, _load)


def set_cached_polish(attraction_id: int, style: str, polish_data: dict):
    def _store():
        key = make_cache_key("polish", attraction_id, style)
        _r.setex(key, TTL_POLISH, json.dumps(polish_data))
        return None

    return _redis_call("set_polish", None, _store)
