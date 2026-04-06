import multiprocessing
import os

# ── Binding ──────────────────────────────────────────────────────────────────
bind = "0.0.0.0:5000"

# ── Workers ──────────────────────────────────────────────────────────────────
# gevent for async/SSE support; 2-4 workers per CPU is the sweet spot
workers = int(os.getenv("GUNICORN_WORKERS", multiprocessing.cpu_count() * 2 + 1))
worker_class = "gevent"
worker_connections = int(os.getenv("GUNICORN_WORKER_CONNECTIONS", 1000))

# Restart workers after N requests to prevent memory leaks
max_requests = int(os.getenv("GUNICORN_MAX_REQUESTS", 1000))
max_requests_jitter = int(os.getenv("GUNICORN_MAX_REQUESTS_JITTER", 100))

# ── Timeouts ─────────────────────────────────────────────────────────────────
# 300s for long-running Ollama/Gemini requests
timeout = int(os.getenv("GUNICORN_TIMEOUT", 300))
graceful_timeout = int(os.getenv("GUNICORN_GRACEFUL_TIMEOUT", 30))
keepalive = 5

# ── Performance ──────────────────────────────────────────────────────────────
# Load app before forking — shares memory, faster cold start
preload_app = os.getenv("GUNICORN_PRELOAD", "true").lower() == "true"

# ── Logging ──────────────────────────────────────────────────────────────────
accesslog = "-"
errorlog = "-"
loglevel = os.getenv("LOG_LEVEL", "info").lower()
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)sμs'

# ── Security ─────────────────────────────────────────────────────────────────
limit_request_line = 4094
limit_request_fields = 100
limit_request_field_size = 8190
forwarded_allow_ips = os.getenv("FORWARDED_ALLOW_IPS", "127.0.0.1")


def on_starting(server):
    server.log.info("AltairGO Engine: Gunicorn starting on port 5000 "
                    f"(workers={workers}, worker_class=gevent, preload={preload_app})")


def post_fork(server, worker):
    server.log.info("Worker spawned (pid: %s)", worker.pid)


def worker_exit(server, worker):
    server.log.info("Worker exited (pid: %s)", worker.pid)
