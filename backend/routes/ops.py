from flask import Blueprint, request, jsonify, current_app
from backend.utils.auth import require_admin
from backend.celery_config import celery_app
from backend.constants import ALLOWED_ENGINE_CONFIG_KEYS
from backend.services.metrics_service import get_metric
from backend.database import db
from backend.models import EngineSetting
from backend.utils.responses import normalize_api_response
import structlog

log = structlog.get_logger(__name__)
ops_bp = Blueprint("ops", __name__)


@ops_bp.after_request
def _normalize_ops_response(response):
    return normalize_api_response(response)

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
    "weather_sync": "backend.celery_tasks.run_weather_sync",
    "heartbeat": "backend.celery_tasks.heartbeat",
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


@ops_bp.route("/api/ops/job-status/<task_id>", methods=["GET"])
@require_admin
def job_status(task_id):
    """Check the status of a triggered Celery task."""
    result = celery_app.AsyncResult(task_id)
    response = {
        "task_id": task_id,
        "status": result.state,
    }
    if result.ready():
        response["result"] = result.result if result.successful() else str(result.result)
    return jsonify(response), 200


# Maps frontend agent_key values to real Celery task paths
AGENT_TASK_MAP = {
    "affiliate_health":      "backend.celery_tasks.run_affiliate_health",
    "cache_warmer":          "backend.celery_tasks.run_cache_warm",
    "destination_validator": "backend.celery_tasks.run_destination_validation",
    "quality_scorer":        "backend.celery_tasks.run_quality_scoring",
    "memory_agent":          "backend.celery_tasks.run_scoring",
    "itinerary_qa":          "backend.celery_tasks.run_quality_scoring",
    "token_optimizer":       "backend.celery_tasks.heartbeat",
    "mcp_context":           "backend.celery_tasks.run_enrichment",
    "web_scraper":           "backend.celery_tasks.run_enrichment",
}

@ops_bp.route('/api/ops/trigger-agent', methods=['POST'])
@require_admin
def trigger_agent():
    """Manual trigger for an AI agent via Celery."""
    data = request.json or {}
    agent_key = data.get('agent_key')

    if not agent_key:
        return jsonify({"error": "No agent_key provided"}), 400

    task_path = AGENT_TASK_MAP.get(agent_key)
    if not task_path:
        return jsonify({"error": f"Unknown agent key: {agent_key}. Valid: {list(AGENT_TASK_MAP.keys())}"}), 400

    try:
        task = celery_app.send_task(task_path)
        log.info("ops.agent_triggered", agent_key=agent_key, task_id=task.id)
        return jsonify({
            "status": "triggered",
            "agent": agent_key,
            "task_id": task.id,
            "message": f"Agent {agent_key} dispatched to Celery worker.",
        }), 202
    except Exception as e:
        log.error("ops.agent_trigger_failed", agent_key=agent_key, error=str(e))
        return jsonify({"error": str(e)}), 500

@ops_bp.route("/api/ops/engine-config", methods=["GET", "POST"])
@require_admin
def engine_config():
    if request.method == "POST":
        data = request.json or {}
        # Only allow whitelisted keys to prevent arbitrary config injection
        rejected_keys = [k for k in data if k not in ALLOWED_ENGINE_CONFIG_KEYS]
        if rejected_keys:
            return jsonify({
                "error": f"Unknown config key(s): {rejected_keys}. "
                         f"Allowed: {sorted(ALLOWED_ENGINE_CONFIG_KEYS)}"
            }), 400

        for key, value in data.items():
            setting = db.session.query(EngineSetting).filter_by(key=key).first()
            if setting:
                setting.value = str(value)
            else:
                setting = EngineSetting(key=key, value=str(value))
                db.session.add(setting)
        db.session.commit()
        log.info("ops.engine_config_updated", keys=list(data.keys()))
        return jsonify({"message": "Configuration updated"}), 200

    # GET
    settings = db.session.query(EngineSetting).all()
    config = {s.key: s.value for s in settings}
    
    # Defaults in case DB is empty
    defaults = {
        "VALIDATION_STRICT":             "false",
        "GEMINI_MODEL":                  "gemini-2.0-flash",
        "THEME_THRESHOLD":               "0.20",
        "MAX_ATTRACTIONS_PER_GENERATION": "500",
        "POPULARITY_HARD_FLOOR":         "25",
        "POPULARITY_SOFT_FLOOR":         "10",
        "SEASONAL_SCORE_GATE":           "40",
        "INTERESTS_CATEGORY_MULTIPLIER": "2",
        "AVG_URBAN_SPEED_KMH":           "15",
        "MAX_ACTIVITIES_PER_DAY":        "6",
    }
    for k, v in defaults.items():
        if k not in config:
            config[k] = v

    # Convert types
    config["VALIDATION_STRICT"] = config["VALIDATION_STRICT"].lower() == "true"
    for float_key in ("THEME_THRESHOLD",):
        try:
            config[float_key] = float(config[float_key])
        except (ValueError, KeyError):
            config[float_key] = float(defaults[float_key])
    for int_key in (
        "MAX_ATTRACTIONS_PER_GENERATION", "POPULARITY_HARD_FLOOR", "POPULARITY_SOFT_FLOOR",
        "SEASONAL_SCORE_GATE", "INTERESTS_CATEGORY_MULTIPLIER", "AVG_URBAN_SPEED_KMH",
        "MAX_ACTIVITIES_PER_DAY",
    ):
        try:
            config[int_key] = int(config[int_key])
        except (ValueError, KeyError):
            config[int_key] = int(defaults[int_key])

    return jsonify(config), 200
