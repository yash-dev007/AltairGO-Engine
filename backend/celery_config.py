"""
celery_config.py — Celery app factory with Redis broker and beat schedule.
Handles scheduled data pipeline jobs.
"""

import os
from celery import Celery
from celery.schedules import crontab

TESTING = os.getenv("TESTING") == "true"
DEV_EAGER = os.getenv("DEV_EAGER", "false").lower() in ("1", "true", "yes")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

if TESTING or DEV_EAGER:
    # Use SQLite in-memory for broker/backend — no Redis required for local dev.
    broker_url = "sqla+sqlite:///:memory:"
    result_backend = "db+sqlite:///:memory:"
    celery_app = Celery("altairgo", broker=broker_url, backend=result_backend, include=["backend.celery_tasks"])
    celery_app.conf.update(
        task_always_eager=True,
        task_eager_propagates=True,
    )
else:
    celery_app = Celery("altairgo", broker=REDIS_URL, backend=REDIS_URL, include=["backend.celery_tasks"])

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Kolkata",
    enable_utc=True,
)

if not TESTING and not DEV_EAGER:
    celery_app.conf.update(
        redbeat_redis_url=REDIS_URL,
        beat_scheduler="redbeat.RedBeatScheduler",
    )

if not TESTING and not DEV_EAGER:
    celery_app.conf.beat_schedule = {
        "ingest-osm-weekly": {
            "task": "backend.celery_tasks.run_osm_ingestion",
            "schedule": crontab(hour=3, minute=0, day_of_week="sunday"),
        },
        "enrich-attractions-weekly": {
            "task": "backend.celery_tasks.run_enrichment",
            "schedule": crontab(hour=4, minute=0, day_of_week="monday"),
        },
        "score-attractions-monthly": {
            "task": "backend.celery_tasks.run_scoring",
            "schedule": crontab(hour=5, minute=0, day_of_month="1"),
        },
        "sync-prices-daily": {
            "task": "backend.celery_tasks.run_price_sync",
            "schedule": crontab(hour="6,18", minute=0),
        },
        "update-behavioral-scores-daily": {
            "task": "backend.celery_tasks.run_score_update",
            "schedule": crontab(hour=2, minute=0),
        },
        "auto-validate-destination-requests": {
            "task": "backend.celery_tasks.run_destination_validation",
            "schedule": crontab(hour=1, minute=0),
        },
        "warm-trip-cache-nightly": {
            "task": "backend.celery_tasks.run_cache_warm",
            "schedule": crontab(hour=3, minute=30),
        },
        "affiliate-health-check": {
            "task": "backend.celery_tasks.run_affiliate_health",
            "schedule": crontab(hour="0,6,12,18", minute=0),
        },
        "quality-score-saved-trips": {
            "task": "backend.celery_tasks.run_quality_scoring",
            "schedule": crontab(hour=4, minute=30),
        },
        "worker-heartbeat": {
            "task": "backend.celery_tasks.heartbeat",
            "schedule": crontab(minute="*/5"), # Every 5 minutes
        },
        "sync-weather-alerts-daily": {
            "task": "backend.celery_tasks.run_weather_sync",
            "schedule": crontab(hour=5, minute=30),  # After price sync, before cache warm
        },
        "generate-post-trip-summaries-daily": {
            "task": "backend.celery_tasks.run_post_trip_summaries",
            "schedule": crontab(hour=6, minute=30),  # After weather sync
        },
        "sync-embeddings-weekly": {
            "task": "backend.celery_tasks.run_embedding_sync",
            "schedule": crontab(hour=4, minute=0, day_of_week="tuesday"),  # After enrichment
        },
    }
else:
    celery_app.conf.beat_schedule = {}
