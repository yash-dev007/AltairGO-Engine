"""
celery_tasks.py — Celery task wrappers for all pipeline stages.
Each task wraps the corresponding script's run function.
"""

import os
from backend.celery_config import celery_app
from backend.database import SessionLocal
from backend.engine.orchestrator import TripGenerationOrchestrator
from backend.models import AnalyticsEvent, AsyncJob
from backend.services.metrics_service import mark_status
from backend.services.cache_service import get_cached, set_cached
from backend.services.gemini_service import get_gemini_service
import structlog

log = structlog.get_logger(__name__)


def _run_and_record(task_name: str, fn):
    try:
        result = fn()
        mark_status("celery", task_name, "ok", result if result is not None else {"status": "completed"})
        return result
    except Exception as exc:
        mark_status("celery", task_name, "error", {"error": str(exc)})
        raise


from backend.utils.helpers import _is_truthy


@celery_app.task(name="backend.celery_tasks.run_osm_ingestion")
def run_osm_ingestion():
    """Stage 1: OSM POI Ingestion for all destinations."""
    log.info("Celery: Starting OSM ingestion...")
    from backend.scripts.ingest_osm_data import run_ingestion

    result = _run_and_record("osm_ingestion", run_ingestion)
    log.info("Celery: OSM ingestion complete.")
    return result


@celery_app.task(name="backend.celery_tasks.run_enrichment")
def run_enrichment():
    """Stage 2: Wikidata + Wikipedia + Google Places enrichment."""
    log.info("Celery: Starting enrichment pipeline...")
    from backend.scripts.enrich_attractions import run_enrichment as _run

    result = _run_and_record("enrichment", _run)
    mark_status("agent", "mcp_context", "ok", result)
    mark_status("agent", "web_scraper", "ok", result)
    log.info("Celery: Enrichment complete.")
    return result


@celery_app.task(name="backend.celery_tasks.run_scoring")
def run_scoring():
    """Stage 3: Intelligence scoring (popularity + seasonal)."""
    log.info("Celery: Starting scoring pipeline...")
    from backend.scripts.score_attractions import run_scoring as _run

    result = _run_and_record("scoring", _run)
    mark_status("agent", "memory_agent", "ok", result)
    log.info("Celery: Scoring complete.")
    return result


@celery_app.task(name="backend.celery_tasks.run_price_sync")
def run_price_sync():
    """Stage 4: Hotel, flight, and attraction price sync."""
    log.info("Celery: Starting price sync...")
    from backend.scripts.sync_prices import run_sync

    result = _run_and_record("price_sync", run_sync)
    log.info("Celery: Price sync complete.")
    return result


@celery_app.task(name="backend.celery_tasks.run_score_update")
def run_score_update():
    """Behavioral score update from AttractionSignal data + quality feedback loop."""
    log.info("Celery: Starting behavioral score update...")
    from backend.tasks.score_updater import update_scores, update_scores_from_quality

    result = _run_and_record("score_update", update_scores)
    # Secondary pass: blend Trip.quality_score into attraction popularity_score.
    # Runs after behavioral update so both signals compound correctly.
    try:
        update_scores_from_quality()
    except Exception as exc:
        log.warning(f"Quality score update failed (non-fatal): {exc}")
    log.info("Celery: Behavioral score update complete.")
    return result


@celery_app.task(name="backend.celery_tasks.run_destination_validation")
def run_destination_validation():
    log.info("Celery: Starting destination validation...")
    from backend.agents.destination_validator_agent import DestinationValidatorAgent

    session = SessionLocal()
    try:
        agent = DestinationValidatorAgent(session)
        result = _run_and_record("destination_validation", agent.run_pending_requests)
        mark_status("agent", "destination_validator", "ok", result)
        return result
    finally:
        session.close()


@celery_app.task(name="backend.celery_tasks.run_cache_warm")
def run_cache_warm():
    log.info("Celery: Starting cache warm...")
    from backend.tasks.cache_warmer import CacheWarmerAgent

    session = SessionLocal()
    try:
        agent = CacheWarmerAgent(session)
        result = _run_and_record("cache_warm", agent.warm)
        mark_status("agent", "cache_warmer", "ok", result)
        return result
    finally:
        session.close()


@celery_app.task(name="backend.celery_tasks.run_affiliate_health")
def run_affiliate_health():
    log.info("Celery: Starting affiliate health check...")
    from backend.tasks.affiliate_health import check_affiliate_health

    result = _run_and_record("affiliate_health", check_affiliate_health)
    mark_status("agent", "affiliate_health", "ok", result)
    return result


@celery_app.task(name="backend.celery_tasks.run_quality_scoring")
def run_quality_scoring():
    log.info("Celery: Starting itinerary quality scoring...")
    from backend.tasks.quality_scorer import ItineraryQualityPipeline

    session = SessionLocal()
    try:
        pipeline = ItineraryQualityPipeline(session)
        result = _run_and_record("quality_scoring", pipeline.score_all_trips)
        mark_status("agent", "quality_scorer", "ok", result)
        mark_status("agent", "itinerary_qa", "ok", result)
        return result
    finally:
        session.close()


@celery_app.task(name="backend.celery_tasks.run_weather_sync")
def run_weather_sync():
    """Sync weather alerts for all active destinations from a weather API."""
    log.info("Celery: Starting weather sync...")
    from backend.tasks.weather_sync import sync_weather_alerts

    result = _run_and_record("weather_sync", sync_weather_alerts)
    log.info("Celery: Weather sync complete.")
    return result


@celery_app.task(name="backend.celery_tasks.generate_itinerary_job")
def generate_itinerary_job(job_id: str):
    """Generate an itinerary asynchronously so request threads return immediately."""
    session = SessionLocal()
    try:
        job = session.get(AsyncJob, job_id)
        if not job:
            return {"job_id": job_id, "status": "missing"}

        job.status = "processing"
        session.commit()

        payload = job.payload or {}
        destination_names = sorted(
            destination["name"]
            for destination in (payload.get("selected_destinations") or [])
            if destination.get("name")
        )
        cache_prefs = {
            "origin_city": payload["start_city"],
            "destination_names": destination_names,
            "budget": payload["budget"],
            "duration": payload["duration"],
            "travelers": payload.get("travelers", 1),
            "style": payload.get("style", "standard"),
            "traveler_type": payload.get("traveler_type", "solo"),
            "travel_month": payload.get("travel_month", "any"),
            "start_date": payload.get("start_date"),
            # Must match cache_prefs in routes/trips.py — all user-visible params
            "interests": sorted(payload.get("interests") or []),
            "date_type": payload.get("date_type", "fixed"),
            "use_engine": payload.get("use_engine", True),
            # Traveler-specific params that change the filtered pool
            "dietary_restrictions": sorted(payload.get("dietary_restrictions") or []),
            "accessibility": payload.get("accessibility", 0),
            "children_count": payload.get("children_count", 0),
        }
        cached_result = get_cached(cache_prefs)
        if cached_result:
            job.status = "completed"
            job.result = cached_result
            job.error_message = None
            session.commit()
            return {"job_id": job_id, "status": "completed"}

        import time
        start_time = time.monotonic()
        orchestrator = TripGenerationOrchestrator(session, get_gemini_service())
        result = orchestrator.generate(
            payload,
            request_user_id=job.user_id,
            strict_validation=_is_truthy(os.getenv("VALIDATION_STRICT", False)),
        )
        elapsed = time.monotonic() - start_time
        from backend.services.metrics_service import record_generation_time
        record_generation_time(elapsed)
        
        set_cached(cache_prefs, result)

        session.add(AnalyticsEvent(
            event_type="GenerateItinerary",
            user_id=job.user_id,
            # Store only metadata to keep payload size manageable
            payload={
                "job_id": job_id,
                "origin_city": payload["start_city"],
                "selected_destination_names": cache_prefs["destination_names"],
                "budget": payload["budget"],
                "duration": payload["duration"],
                "travelers": payload.get("travelers", 1),
                "style": payload.get("style", "standard"),
                "traveler_type": payload.get("traveler_type", "solo"),
                "travel_month": payload.get("travel_month", "any"),
            },
        ))
        job.status = "completed"
        job.result = result
        job.error_message = None
        session.commit()
        return {"job_id": job_id, "status": "completed"}
    except ValueError as exc:
        session.rollback()
        job = session.get(AsyncJob, job_id)
        if job:
            job.status = "failed"
            job.error_message = str(exc)
            session.commit()
        return {"job_id": job_id, "status": "failed", "error": str(exc)}
    except Exception as exc:
        session.rollback()
        job = session.get(AsyncJob, job_id)
        if job:
            job.status = "failed"
            job.error_message = str(exc)
            session.commit()
        raise
    finally:
        session.close()


@celery_app.task(name="backend.celery_tasks.heartbeat")
def heartbeat():
    """Periodic task to signal that a worker is alive."""
    from backend.services.metrics_service import set_metric
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).isoformat()
    set_metric("heartbeat:worker:last_seen", now)
    mark_status("agent", "token_optimizer", "ok", {"status": "alive", "ts": now})
    return {"status": "alive", "ts": now}
