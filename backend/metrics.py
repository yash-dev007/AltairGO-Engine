"""Operational metrics endpoint for admin monitoring."""

from datetime import datetime, timezone

from flask import Blueprint, jsonify

from backend.database import db
from backend.models import AsyncJob, Destination
from backend.utils.auth import require_admin
from backend.utils.responses import normalize_api_response

metrics_bp = Blueprint("metrics", __name__)
metrics_bp.after_request(normalize_api_response)


@metrics_bp.get("/api/metrics")
@require_admin
def get_metrics():
    from backend.services.cache_service import get_redis_client

    client = get_redis_client()
    trips_24h = 0
    cache_hits = 0
    cache_misses = 0
    gemini_429 = 0
    worker_alive = False
    redis_memory_mb = 0.0

    if client is not None:
        trips_24h = int(client.get("metrics:trips_generated:today") or 0)
        cache_hits = int(client.get("metrics:cache_hits:today") or 0)
        cache_misses = int(client.get("metrics:cache_misses:today") or 0)
        gemini_429 = int(client.get("metrics:gemini_429:today") or 0)
        heartbeat = client.get("heartbeat:worker:last_seen")
        if heartbeat:
            try:
                timestamp = datetime.fromisoformat(heartbeat)
                worker_alive = (datetime.now(timezone.utc) - timestamp).total_seconds() < 600
            except Exception:
                worker_alive = False
        try:
            redis_memory_mb = round(client.info("memory").get("used_memory", 0) / 1024 / 1024, 1)
        except Exception:
            redis_memory_mb = 0.0

    cache_total = cache_hits + cache_misses
    cache_hit_rate = round(cache_hits / cache_total, 3) if cache_total > 0 else 0.0

    try:
        active_jobs = AsyncJob.query.filter(AsyncJob.status.in_(["queued", "processing"])).count()
    except Exception:
        active_jobs = 0

    try:
        total_destinations = db.session.query(Destination).count()
        embedded_destinations = db.session.query(Destination).filter(Destination.embedding.isnot(None)).count()
        embedding_coverage_pct = (
            round((embedded_destinations / total_destinations) * 100, 1) if total_destinations else 0.0
        )
    except Exception:
        embedding_coverage_pct = 0.0

    return jsonify({
        "success": True,
        "data": {
            "trips_generated_24h": trips_24h,
            "active_jobs": active_jobs,
            "cache_hit_rate": cache_hit_rate,
            "embedding_coverage_pct": embedding_coverage_pct,
            "gemini_429_count_24h": gemini_429,
            "worker_alive": worker_alive,
            "redis_memory_mb": redis_memory_mb,
        },
    })
