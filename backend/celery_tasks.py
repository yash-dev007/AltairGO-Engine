"""
celery_tasks.py — Celery task wrappers for all pipeline stages.
Each task wraps the corresponding script's run function.
"""

import json
import os
import time
from datetime import datetime, timezone
from backend.celery_config import celery_app
from backend.database import SessionLocal
from backend.engine.orchestrator import TripGenerationOrchestrator
from backend.models import AnalyticsEvent, AsyncJob
from backend.services.metrics_service import mark_status
from backend.services.cache_service import get_cached, set_cached
from backend.services.gemini_service import get_gemini_service
import structlog

log = structlog.get_logger(__name__)


def _write_datasource_log(source_name: str, event_type: str, status: str, details: dict | None = None):
    """Write a DataSourceLog entry in its own session so task failures don't suppress the log."""
    try:
        from backend.models import DataSourceLog
        session = SessionLocal()
        try:
            entry = DataSourceLog(
                source_name=source_name,
                event_type=event_type,
                status=status,
                details=details or {},
            )
            session.add(entry)
            session.commit()
        except Exception:
            session.rollback()
        finally:
            session.close()
    except Exception:
        pass  # Never let logging failure break the task


def _run_and_record(task_name: str, fn):
    _write_datasource_log(task_name, "start", "running")
    try:
        result = fn()
        details = result if isinstance(result, dict) else {"status": "completed"}
        mark_status("celery", task_name, "ok", details)
        _write_datasource_log(task_name, "complete", "ok", details)
        return result
    except Exception as exc:
        error_details = {"error": str(exc)}
        mark_status("celery", task_name, "error", error_details)
        _write_datasource_log(task_name, "error", "error", error_details)
        raise


from backend.utils.helpers import _is_truthy


def _write_task_result(task_name: str, status: str, duration_s: float, error: str | None = None) -> None:
    """Write task execution metadata to Redis without affecting task execution."""
    try:
        from backend.services.cache_service import get_redis_client

        client = get_redis_client()
        if client is None:
            return

        payload = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "status": status,
            "duration_s": round(duration_s, 2),
        }
        client.set(f"celery:task:{task_name}:last", json.dumps(payload))
        if error:
            client.lpush(
                f"celery:errors:{task_name}",
                json.dumps({"ts": payload["ts"], "error": error[:500]}),
            )
            client.ltrim(f"celery:errors:{task_name}", 0, 9)
    except Exception:
        pass


def _run_task_with_retry(task, task_name: str, runner):
    start = time.monotonic()
    try:
        result = runner()
        _write_task_result(task_name, "success", time.monotonic() - start)
        return result
    except Exception as exc:
        _write_task_result(task_name, "failed", time.monotonic() - start, str(exc))
        raise task.retry(exc=exc)


def _publish_job_event(job_id: str, status: str):
    """Publish a job completion event to a Redis stream for SSE subscribers."""
    try:
        from backend.services.metrics_service import get_metrics_redis
        client = get_metrics_redis()
        if client:
            stream_key = f"job:events:{job_id}"
            client.xadd(stream_key, {"status": status, "job_id": job_id}, maxlen=100)
            client.expire(stream_key, 3600)  # 1 hour TTL — subscriber must connect quickly
    except Exception:
        pass  # Never let SSE notification failure break the task


@celery_app.task(name="backend.celery_tasks.run_osm_ingestion", bind=True, max_retries=3, default_retry_delay=60)
def run_osm_ingestion(self):
    """Stage 1: OSM POI Ingestion for all destinations."""
    log.info("Celery: Starting OSM ingestion...")
    from backend.scripts.ingest_osm_data import run_ingestion

    result = _run_task_with_retry(self, "run_osm_ingestion", lambda: _run_and_record("osm_ingestion", run_ingestion))
    log.info("Celery: OSM ingestion complete.")
    return result


@celery_app.task(name="backend.celery_tasks.run_enrichment", bind=True, max_retries=3, default_retry_delay=60)
def run_enrichment(self):
    """Stage 2: Wikidata + Wikipedia + Google Places enrichment."""
    log.info("Celery: Starting enrichment pipeline...")
    from backend.scripts.enrich_attractions import run_enrichment as _run

    result = _run_task_with_retry(self, "run_enrichment", lambda: _run_and_record("enrichment", _run))
    mark_status("agent", "mcp_context", "ok", result)
    mark_status("agent", "web_scraper", "ok", result)
    log.info("Celery: Enrichment complete.")
    return result


@celery_app.task(name="backend.celery_tasks.run_scoring", bind=True, max_retries=3, default_retry_delay=60)
def run_scoring(self):
    """Stage 3: Intelligence scoring (popularity + seasonal)."""
    log.info("Celery: Starting scoring pipeline...")
    from backend.scripts.score_attractions import run_scoring as _run

    result = _run_task_with_retry(self, "run_scoring", lambda: _run_and_record("scoring", _run))
    mark_status("agent", "memory_agent", "ok", result)
    log.info("Celery: Scoring complete.")
    return result


@celery_app.task(name="backend.celery_tasks.run_price_sync", bind=True, max_retries=3, default_retry_delay=60)
def run_price_sync(self):
    """Stage 4: Hotel, flight, and attraction price sync."""
    log.info("Celery: Starting price sync...")
    from backend.scripts.sync_prices import run_sync

    result = _run_task_with_retry(self, "run_price_sync", lambda: _run_and_record("price_sync", run_sync))
    log.info("Celery: Price sync complete.")
    return result


@celery_app.task(name="backend.celery_tasks.run_score_update", bind=True, max_retries=3, default_retry_delay=60)
def run_score_update(self):
    """Behavioral score update from AttractionSignal data + quality feedback loop."""
    log.info("Celery: Starting behavioral score update...")
    from backend.tasks.score_updater import update_scores, update_scores_from_quality

    def _runner():
        result = _run_and_record("score_update", update_scores)
        try:
            update_scores_from_quality()
        except Exception as exc:
            log.warning(f"Quality score update failed (non-fatal): {exc}")
        return result

    result = _run_task_with_retry(self, "run_score_update", _runner)
    log.info("Celery: Behavioral score update complete.")
    return result


@celery_app.task(name="backend.celery_tasks.run_destination_validation", bind=True, max_retries=3, default_retry_delay=60)
def run_destination_validation(self):
    log.info("Celery: Starting destination validation...")
    from backend.agents.destination_validator_agent import DestinationValidatorAgent

    session = SessionLocal()
    try:
        agent = DestinationValidatorAgent(session)
        result = _run_task_with_retry(
            self,
            "run_destination_validation",
            lambda: _run_and_record("destination_validation", agent.run_pending_requests),
        )
        mark_status("agent", "destination_validator", "ok", result)
        return result
    finally:
        session.close()


@celery_app.task(name="backend.celery_tasks.run_cache_warm", bind=True, max_retries=3, default_retry_delay=60)
def run_cache_warm(self):
    log.info("Celery: Starting cache warm...")
    from backend.tasks.cache_warmer import CacheWarmerAgent

    session = SessionLocal()
    try:
        agent = CacheWarmerAgent(session)
        result = _run_task_with_retry(self, "run_cache_warm", lambda: _run_and_record("cache_warm", agent.warm))
        mark_status("agent", "cache_warmer", "ok", result)
        return result
    finally:
        session.close()


@celery_app.task(name="backend.celery_tasks.run_affiliate_health", bind=True, max_retries=3, default_retry_delay=60)
def run_affiliate_health(self):
    log.info("Celery: Starting affiliate health check...")
    from backend.tasks.affiliate_health import check_affiliate_health

    result = _run_task_with_retry(self, "run_affiliate_health", lambda: _run_and_record("affiliate_health", check_affiliate_health))
    mark_status("agent", "affiliate_health", "ok", result)
    return result


@celery_app.task(name="backend.celery_tasks.run_quality_scoring", bind=True, max_retries=3, default_retry_delay=60)
def run_quality_scoring(self):
    log.info("Celery: Starting itinerary quality scoring...")
    from backend.tasks.quality_scorer import ItineraryQualityPipeline

    session = SessionLocal()
    try:
        pipeline = ItineraryQualityPipeline(session)
        result = _run_task_with_retry(
            self,
            "run_quality_scoring",
            lambda: _run_and_record("quality_scoring", pipeline.score_all_trips),
        )
        mark_status("agent", "quality_scorer", "ok", result)
        mark_status("agent", "itinerary_qa", "ok", result)
        return result
    finally:
        session.close()


@celery_app.task(name="backend.celery_tasks.run_weather_sync", bind=True, max_retries=3, default_retry_delay=60)
def run_weather_sync(self):
    """Sync weather alerts for all active destinations from a weather API."""
    log.info("Celery: Starting weather sync...")
    from backend.tasks.weather_sync import sync_weather_alerts

    result = _run_task_with_retry(self, "run_weather_sync", lambda: _run_and_record("weather_sync", sync_weather_alerts))
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
            strict_validation=_is_truthy(os.getenv("VALIDATION_STRICT", "false")),
        )
        elapsed = time.monotonic() - start_time
        from backend.services.metrics_service import record_generation_time
        record_generation_time(elapsed)
        
        set_cached(cache_prefs, result)

        # Publish to job-specific Redis stream so SSE subscribers get instant notification
        _publish_job_event(job_id, "completed")

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
    except Exception as exc:
        session.rollback()
        # Re-fetch job after rollback; use merge() to avoid detached-instance errors.
        try:
            job = session.get(AsyncJob, job_id)
            if job:
                job.status = "failed"
                job.error_message = str(exc)
                session.commit()
        except Exception:
            log.exception("generate_itinerary_job.fail_record_error", job_id=job_id)
        _publish_job_event(job_id, "failed")
        # Return a structured error for ValueError (user-visible) but re-raise others.
        if isinstance(exc, ValueError):
            return {"job_id": job_id, "status": "failed", "error": str(exc)}
        raise
    finally:
        session.close()


@celery_app.task(name="backend.celery_tasks.run_post_trip_summaries", bind=True, max_retries=3, default_retry_delay=60)
def run_post_trip_summaries(self):
    """Generate post-trip summaries for recently completed trips."""
    log.info("Celery: Starting post-trip summary generation...")
    from backend.tasks.post_trip import generate_post_trip_summaries

    result = _run_task_with_retry(
        self,
        "run_post_trip_summaries",
        lambda: _run_and_record("post_trip", generate_post_trip_summaries),
    )
    log.info("Celery: Post-trip summaries done.")
    return result


@celery_app.task(name="backend.celery_tasks.run_embedding_sync", bind=True, max_retries=3, default_retry_delay=60)
def run_embedding_sync(self):
    """Sync destination embeddings for semantic recommendations."""
    log.info("Celery: Starting embedding sync...")
    from backend.tasks.embedding_sync import sync_embeddings

    result = _run_task_with_retry(self, "run_embedding_sync", lambda: _run_and_record("embedding_sync", sync_embeddings))
    log.info("Celery: Embedding sync complete.")
    return result


@celery_app.task(name="backend.celery_tasks.heartbeat")
def heartbeat():
    """Periodic task to signal that a worker is alive."""
    from backend.services.metrics_service import set_metric
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).isoformat()
    set_metric("heartbeat:worker:last_seen", now)
    mark_status("agent", "token_optimizer", "ok", {"status": "alive", "ts": now})
    return {"status": "alive", "ts": now}
