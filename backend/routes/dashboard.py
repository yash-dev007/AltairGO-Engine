import json
import time
from datetime import datetime, timezone

from flask import Blueprint, Response, current_app, jsonify, stream_with_context

from backend.database import db
from backend.models import AnalyticsEvent, AttractionSignal, DataSourceLog, Destination, DestinationRequest, Trip, User
from backend.services.metrics_service import get_metric, get_metrics_redis
from backend.utils.auth import require_admin

dashboard_bp = Blueprint("dashboard", __name__)


def _metric_int(metric_name: str, default: int = 0) -> int:
    value = get_metric(metric_name, default=default)
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _metric_json(metric_name: str, default=None):
    if default is None:
        default = {}
    return get_metric(metric_name, default=default, parse_json=True)


@dashboard_bp.route("/api/ops/summary", methods=["GET"])
@require_admin
def ops_summary():
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    gemini_calls_today = _metric_int("gemini:calls:today")
    gemini_tokens_today = _metric_int("gemini:tokens:today")
    gemini_errors_today = _metric_int("gemini:errors:today")

    cache_hits_today = _metric_int("metrics:cache_hits:today")
    cache_misses_today = _metric_int("metrics:cache_misses:today")
    cache_total = max(cache_hits_today + cache_misses_today, 1)

    latest_pipeline = _metric_json("metrics:pipeline:last_event", default={})

    trips_today = db.session.query(AnalyticsEvent).filter(
        AnalyticsEvent.event_type == "GenerateItinerary",
        AnalyticsEvent.created_at >= today_start,
    ).count()
    signals_today = db.session.query(AttractionSignal).filter(
        AttractionSignal.created_at >= today_start,
    ).count()

    agent_names = [
        "memory", "token_optimizer", "mcp_context", "itinerary_qa",
        "web_scraper", "destination_validator", "cache_warmer",
        "affiliate_health", "quality_scorer",
    ]
    agents = {}
    for agent_name in agent_names:
        agents[agent_name] = {
            "last_run": get_metric(f"agent:{agent_name}:last_run"),
            "status": get_metric(f"agent:{agent_name}:last_status", default="never_run"),
            "result": _metric_json(f"agent:{agent_name}:last_result", default=None),
        }

    celery_task_names = [
        "osm_ingestion", "enrichment", "scoring", "price_sync",
        "score_update", "destination_validation", "cache_warm",
        "affiliate_health", "quality_scoring",
    ]
    celery_tasks = {}
    for task_name in celery_task_names:
        celery_tasks[task_name] = {
            "last_run": get_metric(f"celery:{task_name}:last_run"),
            "status": get_metric(f"celery:{task_name}:last_status", default="never_run"),
            "result": _metric_json(f"celery:{task_name}:last_result", default=None),
        }

    # ── DataSourceLog: last run per task name ─────────────────────────────────
    from sqlalchemy import func as sql_func

    datasource_subq = (
        db.session.query(
            DataSourceLog.source_name,
            sql_func.max(DataSourceLog.created_at).label("latest"),
        )
        .group_by(DataSourceLog.source_name)
        .subquery()
    )
    recent_logs = (
        db.session.query(DataSourceLog)
        .join(
            datasource_subq,
            (DataSourceLog.source_name == datasource_subq.c.source_name)
            & (DataSourceLog.created_at == datasource_subq.c.latest),
        )
        .all()
    )
    job_health = {
        row.source_name: {
            "last_run": row.created_at.isoformat() if row.created_at else None,
            "status": row.status,
            "event_type": row.event_type,
            "details": row.details,
        }
        for row in recent_logs
    }

    return jsonify({
        "gemini": {
            "calls_today": gemini_calls_today,
            "tokens_today": gemini_tokens_today,
            "errors_today": gemini_errors_today,
            "error_rate_pct": round((gemini_errors_today / max(gemini_calls_today, 1)) * 100, 1),
        },
        "cache": {
            "hits_today": cache_hits_today,
            "misses_today": cache_misses_today,
            "hit_rate_pct": round((cache_hits_today / cache_total) * 100, 1),
        },
        "pipeline": {
            "avg_generation_ms": _metric_int("metrics:avg_gen_ms"),
            "p95_generation_ms": _metric_int("metrics:p95_gen_ms"),
            "latest_event": latest_pipeline,
        },
        "app": {
            "users_total": db.session.query(User).count(),
            "trips_total": db.session.query(Trip).count(),
            "destinations_total": db.session.query(Destination).count(),
            "pending_destination_requests": db.session.query(DestinationRequest).filter_by(status="pending").count(),
            "trips_generated_today": trips_today,
            "signals_recorded_today": signals_today,
        },
        "quality": {
            "last_run": get_metric("quality:last_run"),
            "scored_count": _metric_int("quality:scored_count"),
        },
        "affiliate": {
            "health": _metric_json("affiliate:health", default={}),
        },
        "agents": agents,
        "celery_tasks": celery_tasks,
        "job_health": job_health,
    }), 200


@dashboard_bp.route("/api/ops/live-metrics", methods=["GET"])
def live_metrics():
    """SSE endpoint with query-param auth — EventSource API cannot send custom headers."""
    import hmac
    from flask import request as _req
    from flask_jwt_extended import decode_token

    token = _req.args.get("token")
    if not token:
        return jsonify({"error": "Missing token query parameter"}), 401

    # Try JWT decode first, fall back to raw admin key comparison
    try:
        claims = decode_token(token)
        if claims.get("role") != "admin":
            return jsonify({"error": "Admin role required"}), 403
    except Exception:
        expected = current_app.config.get("ADMIN_ACCESS_KEY", "")
        if not expected or not hmac.compare_digest(token, expected):
            return jsonify({"error": "Invalid token"}), 401

    client = get_metrics_redis()

    def generate():
        if not client:
            yield f"data: {json.dumps({'heartbeat': True, 'redis': 'unavailable'})}\n\n"
            return

        last_id = "$"
        while True:
            try:
                events = client.xread({"pipeline:metrics": last_id}, count=20, block=2000)
            except Exception:
                yield f"data: {json.dumps({'heartbeat': True, 'error': 'stream_read_failed'})}\n\n"
                time.sleep(2)
                continue

            if not events:
                yield f"data: {json.dumps({'heartbeat': True})}\n\n"
                continue

            for _stream_name, messages in events:
                for message_id, payload in messages:
                    last_id = message_id
                    yield f"data: {json.dumps(payload)}\n\n"

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
