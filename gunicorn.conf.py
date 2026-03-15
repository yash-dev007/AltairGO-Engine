import multiprocessing
import os

# ── General ─────────────────────────────────────────────────────────────
bind = "0.0.0.0:5000"
workers = int(os.getenv("GUNICORN_WORKERS", multiprocessing.cpu_count() * 2 + 1))
worker_class = "gevent" # Recommended for high concurrency in trip generation
timeout = int(os.getenv("GUNICORN_TIMEOUT", 120))
keepalive = 5

# ── Logging ─────────────────────────────────────────────────────────────
accesslog = "-"
errorlog = "-"
loglevel = os.getenv("LOG_LEVEL", "info").lower()

# ── Security ─────────────────────────────────────────────────────────────
limit_request_line = 4094
limit_request_fields = 100
limit_request_field_size = 8190

def on_starting(server):
    print("AltairGO Engine: Gunicorn starting on port 5000...")

def post_fork(server, worker):
    server.log.info("Worker spawned (pid: %s)", worker.pid)
