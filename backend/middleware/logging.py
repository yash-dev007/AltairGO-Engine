import time

import structlog
from flask import Flask, g, request

log = structlog.get_logger(__name__)


def register_logging_middleware(app: Flask) -> None:
    """Emit one structured log entry per HTTP request."""

    @app.before_request
    def _start_timer() -> None:
        g._request_start = time.monotonic()

    @app.after_request
    def _log_request(response):
        started = g.get("_request_start", time.monotonic())
        duration_ms = int((time.monotonic() - started) * 1000)
        log.info(
            "http_request",
            method=request.method,
            path=request.path,
            status=response.status_code,
            duration_ms=duration_ms,
            ip=request.remote_addr,
        )
        return response
