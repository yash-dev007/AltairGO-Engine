"""Metadata for scheduled Celery tasks exposed in admin tooling."""

TASK_REGISTRY: dict[str, dict[str, str]] = {
    "run_osm_ingestion": {"label": "OSM POI Ingestion", "schedule": "Sunday 03:00"},
    "run_enrichment": {"label": "Destination Enrichment", "schedule": "Daily"},
    "run_scoring": {"label": "Attraction Scoring", "schedule": "Daily"},
    "run_price_sync": {"label": "Price Sync", "schedule": "Daily 06:00 & 18:00"},
    "run_score_update": {"label": "Popularity Score Update", "schedule": "Daily 02:00"},
    "run_destination_validation": {"label": "Destination Validation", "schedule": "Daily 01:00"},
    "run_cache_warm": {"label": "Cache Warm", "schedule": "Daily 03:30"},
    "run_affiliate_health": {"label": "Affiliate Health", "schedule": "Every 6h"},
    "run_quality_scoring": {"label": "Trip Quality Scoring", "schedule": "Daily 04:30"},
    "run_weather_sync": {"label": "Weather Sync", "schedule": "Daily 05:30"},
    "run_post_trip_summaries": {"label": "Post-Trip Summaries", "schedule": "Daily"},
    "run_embedding_sync": {"label": "Embedding Sync", "schedule": "Weekly"},
}
