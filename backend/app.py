import logging
import os
from uuid import uuid4
from dotenv import load_dotenv

load_dotenv()

import redis
import structlog
from flask import Flask, g, jsonify, request
from flask_cors import CORS
from flask_jwt_extended import JWTManager
from flask_migrate import Migrate
from sqlalchemy import text

from backend import database
from backend.celery_config import celery_app
from backend.extensions import limiter

log = structlog.get_logger(__name__)


_logging_configured = False

def _configure_logging():
    global _logging_configured
    if _logging_configured:
        return

    logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"), format="%(message)s")
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )
    _logging_configured = True


def _validate_jwt_secret(secret: str) -> str:
    if not secret or len(secret) < 32:
        raise RuntimeError(
            "JWT_SECRET_KEY must be at least 32 characters. "
            "Generate one with: python -c \"import secrets; print(secrets.token_hex(32))\""
        )
    return secret


def _parse_allowed_origins(value):
    if isinstance(value, list):
        return value
    if not value:
        return ["https://altairgo.in", "http://localhost:5173"]
    return [origin.strip() for origin in str(value).split(",") if origin.strip()]


def _assert_required_config(app, test_config=None):
    required = ["DATABASE_URL", "REDIS_URL", "JWT_SECRET_KEY", "ADMIN_ACCESS_KEY"]
    for var in required:
        config_key = "SQLALCHEMY_DATABASE_URI" if var == "DATABASE_URL" else var
        configured_value = (
            (test_config or {}).get(var)
            or (test_config or {}).get(config_key)
            or os.environ.get(var)
            or app.config.get(config_key)
        )
        assert configured_value, f"Missing required env var: {var}"


def create_app(test_config=None):
    _configure_logging()

    from datetime import timedelta
    app = Flask(__name__)
    app.config.from_mapping(
        SQLALCHEMY_DATABASE_URI=os.getenv("DATABASE_URL", ""),
        REDIS_URL=os.getenv("REDIS_URL", ""),
        JWT_SECRET_KEY=os.getenv("JWT_SECRET_KEY", ""),
        ADMIN_ACCESS_KEY=os.getenv("ADMIN_ACCESS_KEY", ""),
        GEMINI_API_KEY=os.getenv("GEMINI_API_KEY", ""),
        VALIDATION_STRICT=os.getenv("VALIDATION_STRICT", "false"),
        ALLOWED_ORIGINS=os.getenv("ALLOWED_ORIGINS", "https://altairgo.in,http://localhost:5173"),
        JWT_ACCESS_TOKEN_EXPIRES=timedelta(hours=1),
        JWT_REFRESH_TOKEN_EXPIRES=timedelta(days=30),
    )

    if test_config is None:
        app.config.from_pyfile("config.py", silent=True)
    else:
        app.config.from_mapping(test_config)

    _assert_required_config(app, test_config=test_config)
    app.config["JWT_SECRET_KEY"] = _validate_jwt_secret(app.config.get("JWT_SECRET_KEY", ""))
    CORS(app, origins=_parse_allowed_origins(app.config.get("ALLOWED_ORIGINS")))

    database.configure_database(app, app.config["SQLALCHEMY_DATABASE_URI"])
    _eager = bool(app.config.get("TESTING")) or os.getenv("DEV_EAGER", "false").lower() in ("1", "true", "yes")
    celery_app.conf.task_always_eager = _eager
    celery_app.conf.task_eager_propagates = _eager

    @app.before_request
    def bind_request_context():
        structlog.contextvars.clear_contextvars()
        request_id = str(uuid4())
        g.request_id = request_id
        structlog.contextvars.bind_contextvars(
            request_id=request_id,
            method=request.method,
            path=request.path,
        )

    @app.after_request
    def attach_request_metadata(response):
        response.headers["X-Request-Id"] = getattr(g, "request_id", "")
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
        if not app.debug:
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        log.info("request.completed", status_code=response.status_code)
        return response

    @app.teardown_request
    def clear_request_context(_exc):
        structlog.contextvars.clear_contextvars()

    from backend.routes.trips import trips_bp
    from backend.routes.admin import admin_bp
    from backend.routes.auth import auth_bp
    from backend.routes.destinations import destinations_bp
    from backend.routes.dashboard import dashboard_bp
    from backend.routes.signals import signals_bp
    from backend.routes.ops import ops_bp
    from backend.routes.bookings import bookings_bp
    from backend.routes.expenses import expenses_bp
    from backend.routes.discover import discover_bp
    from backend.routes.trip_tools import trip_tools_bp
    from backend.routes.trip_editor import trip_editor_bp
    from backend.routes.profile import profile_bp
    from backend.routes.sharing import sharing_bp
    from backend.routes.search import search_bp
    from backend.routes.blogs import blogs_bp
    from backend.routes.feedback import feedback_bp
    from backend.routes.webhooks import webhooks_bp

    app.register_blueprint(trips_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(destinations_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(signals_bp)
    app.register_blueprint(ops_bp)
    app.register_blueprint(bookings_bp)
    app.register_blueprint(expenses_bp)
    app.register_blueprint(discover_bp)
    app.register_blueprint(trip_tools_bp)
    app.register_blueprint(trip_editor_bp)
    app.register_blueprint(profile_bp)
    app.register_blueprint(sharing_bp)
    app.register_blueprint(search_bp)
    app.register_blueprint(blogs_bp)
    app.register_blueprint(feedback_bp)
    app.register_blueprint(webhooks_bp)

    # Register Booking.com affiliate provider for hotel bookings (no-op when
    # BOOKINGCOM_AFFILIATE_ID is not set — SimulatedProvider is used instead).
    from backend.services.booking_providers.bookingcom import BookingComProvider
    from backend.services.booking_providers.registry import register as register_provider
    register_provider("hotel", BookingComProvider())

    limiter.init_app(app)
    JWTManager(app)
    Migrate(app, database.db)

    # Schema creation/migrations are handled by Flask-Migrate / Alembic.

    @app.route("/health")
    def health():
        checks = {"status": "ok", "db": "unknown", "redis": "unknown"}
        try:
            database.db.session.execute(text("SELECT 1"))
            checks["db"] = "ok"
        except Exception:
            log.exception("health.db_check_failed")
            checks["db"] = "error"
            checks["status"] = "degraded"

        try:
            redis_url = app.config.get("REDIS_URL")
            if not redis_url:
                raise ValueError("REDIS_URL not configured")
            redis.from_url(redis_url, decode_responses=True).ping()
            checks["redis"] = "ok"
        except Exception:
            log.warning("health.redis_check_failed")
            checks["redis"] = "error"
            checks["status"] = "degraded"

        code = 200 if checks["status"] == "ok" else 503
        return jsonify(checks), code

    @app.errorhandler(Exception)
    def handle_unhandled_exception(exc):
        from werkzeug.exceptions import HTTPException
        if isinstance(exc, HTTPException):
            return jsonify({
                "error": exc.description,
                "request_id": getattr(g, "request_id", None),
            }), exc.code

        log.exception("unhandled_exception", error=str(exc))
        return jsonify({
            "error": "Internal server error",
            "request_id": getattr(g, "request_id", None),
        }), 500

    return app


if __name__ == "__main__":
    app = create_app()
    _debug = os.getenv("FLASK_DEBUG", "false").lower() in ("1", "true", "yes")
    app.run(host="127.0.0.1", port=5000, debug=_debug)
