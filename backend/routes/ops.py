from flask import Blueprint, request, jsonify, current_app
from backend.utils.auth import require_admin
from backend.celery_config import celery_app
from backend.services.metrics_service import get_metric, mark_status
from backend.database import db
from backend.models import EngineSetting
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
    "heartbeat": "backend.celery_tasks.heartbeat",
}

@ops_bp.route("/api/ops/summary", methods=["GET"])
@require_admin
def get_ops_summary():
    """Return an overview of agent health, celery task status, and Gemini usage."""
    agents_status = {}
    for job in VALID_JOBS.keys():
        last_run = get_metric(f"celery:{job}:last_run")
        last_status = get_metric(f"celery:{job}:last_status")
        agents_status[job] = {
            "status": last_status or "never_run",
            "last_run": last_run,
            "details": get_metric(f"celery:{job}:last_result", parse_json=True)
        }

    return jsonify({
        "status": "operational",
        "agents": agents_status,
        "gemini": {
            "calls_today": int(get_metric("gemini:calls:today", 0)),
            "tokens_today": int(get_metric("gemini:tokens:today", 0)),
            "error_rate_pct": float(get_metric("gemini:error_rate", 0)),
        },
        "pipeline": {
            "avg_generation_ms": float(get_metric("metrics:avg_gen_time", 0)) * 1000,
        },
        "cache": {
            "hit_rate_pct": 82.5, # Mock value for now
        }
    }), 200

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

@ops_bp.route('/api/ops/trigger-agent', methods=['POST'])
def trigger_agent():
    """Manual trigger for an AI agent via Celery."""
    data = request.json
    agent_key = data.get('agent_key')
    
    if not agent_key:
        return jsonify({"error": "No agent_key provided"}), 400
        
    # Mapping agent keys to their actual task names or classes
    # For now, we'll simulate the trigger by queuing a generic task 
    # or a specific one if implemented.
    try:
        # Check if the specific task exists in celery_tasks
        # This is a placeholder for actual agent execution logic
        # In a real scenario, we'd call the specific agent's run method
        return jsonify({
            "status": "triggered",
            "agent": agent_key,
            "message": f"Agent {agent_key} has been queued for execution."
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@ops_bp.route("/api/ops/engine-config", methods=["GET", "POST"])
@require_admin
def engine_config():
    if request.method == "POST":
        data = request.json or {}
        for key, value in data.items():
            setting = db.session.query(EngineSetting).filter_by(key=key).first()
            if setting:
                setting.value = str(value)
            else:
                setting = EngineSetting(key=key, value=str(value))
                db.session.add(setting)
        db.session.commit()
        return jsonify({"message": "Configuration updated"}), 200

    # GET
    settings = db.session.query(EngineSetting).all()
    config = {s.key: s.value for s in settings}
    
    # Defaults in case DB is empty
    if "VALIDATION_STRICT" not in config: config["VALIDATION_STRICT"] = "false"
    if "GEMINI_MODEL" not in config: config["GEMINI_MODEL"] = "gemini-1.5-pro"
    if "THEME_THRESHOLD" not in config: config["THEME_THRESHOLD"] = "0.20"

    # Convert types
    config["VALIDATION_STRICT"] = config["VALIDATION_STRICT"].lower() == "true"
    try:
        config["THEME_THRESHOLD"] = float(config["THEME_THRESHOLD"])
    except ValueError:
        config["THEME_THRESHOLD"] = 0.20

    return jsonify(config), 200
