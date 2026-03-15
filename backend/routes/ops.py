from flask import Blueprint, request, jsonify, current_app
from backend.utils.auth import require_admin
from backend.celery_config import celery_app
from backend.services.metrics_service import get_metric, mark_status
from backend.database import db
import structlog

log = structlog.get_logger(__name__)
ops_bp = Blueprint("ops", __name__)

VALID_JOBS = {
    "osm_ingestion": "backend.celery_tasks.run_osm_ingestion",
    "enrichment": "backend.celery_tasks.run_enrichment",
    "scoring": "backend.celery_tasks.run_scoring",
    "price_sync": "backend.celery_tasks.run_price_sync",
    "score_update": "backend.celery_tasks.run_score_update",
    "destination_validation": "backend.celery_tasks.run_destination_validation",
    "cache_warm": "backend.celery_tasks.run_cache_warm",
    "affiliate_health": "backend.celery_tasks.run_affiliate_health",
    "quality_scoring": "backend.celery_tasks.run_quality_scoring",
}

@ops_bp.route("/api/ops/trigger-job", methods=["POST"])
@require_admin
def trigger_job():
    data = request.json or {}
    job_name = data.get("job_name")
    
    if job_name not in VALID_JOBS:
        return jsonify({"error": f"Invalid job name. Valid jobs: {list(VALID_JOBS.keys())}"}), 400
    
    task_path = VALID_JOBS[job_name]
    task = celery_app.send_task(task_path)
    
    log.info("ops.job_triggered", job_name=job_name, task_id=task.id)
    return jsonify({
        "message": f"Job {job_name} triggered",
        "task_id": task.id
    }), 202

@ops_bp.route("/api/ops/job-status/<job_name>", methods=["GET"])
@require_admin
def get_job_status(job_name):
    if job_name not in VALID_JOBS:
        return jsonify({"error": "Invalid job name"}), 400
    
    # We check the status recorded in Redis by metrics_service.mark_status
    last_run = get_metric(f"celery:{job_name}:last_run")
    last_status = get_metric(f"celery:{job_name}:last_status")
    last_result = get_metric(f"celery:{job_name}:last_result", parse_json=True)
    
    return jsonify({
        "job_name": job_name,
        "last_run": last_run,
        "status": last_status,
        "details": last_result
    }), 200

@ops_bp.route("/api/ops/engine-config", methods=["GET"])
@require_admin
def get_engine_config():
    return jsonify({
        "VALIDATION_STRICT": current_app.config.get("VALIDATION_STRICT"),
        "GEMINI_MODEL": "gemini-1.5-pro", # Default
        "THEME_THRESHOLD": 0.20,
    }), 200
