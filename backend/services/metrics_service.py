import json
import os
from datetime import datetime, timedelta, timezone

import redis
import structlog

log = structlog.get_logger(__name__)

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

_metrics_redis = None
_metrics_ready = None


def get_metrics_redis():
    global _metrics_redis, _metrics_ready

    if _metrics_ready is not None:
        return _metrics_redis if _metrics_ready else None

    try:
        client = redis.from_url(REDIS_URL, decode_responses=True)
        client.ping()
        _metrics_redis = client
        _metrics_ready = True
    except Exception as exc:
        log.warning(f"Metrics Redis unavailable: {exc}")
        _metrics_redis = None
        _metrics_ready = False

    return _metrics_redis


def incr_daily_counter(metric_name: str, amount: int = 1):
    try:
        client = get_metrics_redis()
        if not client:
            return None

        now = datetime.now(timezone.utc)
        day_key = f"{metric_name}:{now.date().isoformat()}"
        alias_key = f"{metric_name}:today"

        value = client.incrby(day_key, int(amount))
        client.expire(day_key, 2 * 24 * 60 * 60)
        client.set(alias_key, value, ex=_seconds_until_next_utc_midnight(now))
        return value
    except Exception as exc:
        log.warning(f"Metric increment failed for {metric_name}: {exc}")
        return None


def set_metric(metric_name: str, value, ttl_seconds: int | None = None):
    try:
        client = get_metrics_redis()
        if not client:
            return False

        stored_value = json.dumps(value) if isinstance(value, (dict, list)) else value
        if ttl_seconds:
            client.set(metric_name, stored_value, ex=ttl_seconds)
        else:
            client.set(metric_name, stored_value)
        return True
    except Exception as exc:
        log.warning(f"Metric set failed for {metric_name}: {exc}")
        return False


def record_generation_time(seconds: float):
    """Maintain a rolling average of generation times in Redis (last 50 samples)."""
    try:
        client = get_metrics_redis()
        if not client:
            return

        list_key = "metrics:gen_times"
        client.lpush(list_key, seconds)
        client.ltrim(list_key, 0, 49)  # Keep last 50 samples
        # Expire the list after 7 days so stale samples don't persist across restarts
        client.expire(list_key, 7 * 24 * 60 * 60)

        times = [float(t) for t in client.lrange(list_key, 0, -1)]
        if times:
            avg = sum(times) / len(times)
            client.set("metrics:avg_gen_time", avg, ex=7 * 24 * 60 * 60)
    except Exception as exc:
        log.warning(f"Failed to record generation time: {exc}")


def get_metric(metric_name: str, default=None, parse_json: bool = False):
    try:
        client = get_metrics_redis()
        if not client:
            return default

        value = client.get(metric_name)
        if value is None:
            return default
        if parse_json:
            return json.loads(value)
        return value
    except Exception as exc:
        log.warning(f"Metric get failed for {metric_name}: {exc}")
        return default


def add_stream_event(stream_name: str, payload: dict, maxlen: int = 10000):
    try:
        client = get_metrics_redis()
        if not client:
            return None

        event = {}
        for key, value in (payload or {}).items():
            if value is None:
                continue
            if isinstance(value, (dict, list)):
                event[key] = json.dumps(value)
            else:
                event[key] = str(value)
        if "ts" not in event:
            event["ts"] = str(datetime.now(timezone.utc).timestamp())
        return client.xadd(stream_name, event, maxlen=maxlen, approximate=True)
    except Exception as exc:
        log.warning(f"Stream write failed for {stream_name}: {exc}")
        return None


def mark_status(prefix: str, name: str, status: str, details=None, ttl_seconds: int = 7 * 24 * 60 * 60):
    try:
        now_iso = datetime.now(timezone.utc).isoformat()
        base_key = f"{prefix}:{name}"
        set_metric(f"{base_key}:last_run", now_iso, ttl_seconds=ttl_seconds)
        set_metric(f"{base_key}:last_status", status, ttl_seconds=ttl_seconds)
        if details is not None:
            set_metric(f"{base_key}:last_result", details, ttl_seconds=ttl_seconds)
        return {"last_run": now_iso, "status": status, "details": details}
    except Exception:
        # mark_status depends on set_metric which is already guarded,
        # but we guard the whole thing just in case.
        return {"status": "error", "details": "Redis write botched"}


def _seconds_until_next_utc_midnight(now: datetime) -> int:
    next_midnight = datetime.combine(
        now.date() + timedelta(days=1),
        datetime.min.time(),
        tzinfo=timezone.utc,
    )
    return max(60, int((next_midnight - now).total_seconds()))
