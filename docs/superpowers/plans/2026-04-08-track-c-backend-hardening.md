# Track C — Backend Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Harden the Flask backend with structured logging, consistent error envelopes, a /api/metrics endpoint, activity reorder endpoint, and Celery retry/error tracking.

**Architecture:** Additive only — no existing logic removed. A new logging middleware registers on the Flask app. Error envelopes are applied uniformly across all route files. Celery tasks gain retry wrappers and write last-run metadata to Redis keys read by the admin panel.

**Tech Stack:** Python Flask, structlog, Celery, Redis (`backend.services.cache_service`), pytest (SQLite in-memory for tests)

**Executor tool:** Codex — all tasks are self-contained with full patterns provided.

---

## Codebase Patterns (read before starting)

**Admin route auth:**
```python
from backend.utils.auth import require_admin

@admin_bp.get("/api/admin/something")
@require_admin
def handler():
    return jsonify({"success": True, "data": {...}})
```

**JWT route auth:**
```python
from flask_jwt_extended import jwt_required, get_jwt_identity

@bp.post("/api/trip/<int:trip_id>/something")
@jwt_required()
def handler(trip_id):
    user_id = get_jwt_identity()
```

**Celery task (current pattern):**
```python
from backend.celery_config import celery_app

@celery_app.task(name="backend.celery_tasks.run_score_update")
def run_score_update():
    from backend.tasks.score_updater import run as _run
    _run()
```

**Redis client:**
```python
from backend.services.cache_service import _r, REDIS_OK

if REDIS_OK and _r:
    _r.set("some:key", "value")
```

**Safe itinerary mutation:**
```python
import copy
itinerary = copy.deepcopy(trip.itinerary_json or {})
# modify itinerary...
trip.itinerary_json = itinerary
trip.is_customized = 1
db.session.commit()
```

**Error envelope standard (apply everywhere):**
```python
# Error
return jsonify({"success": False, "error": "Human message", "code": "ERR_NOT_FOUND"}), 404
# Success
return jsonify({"success": True, "data": {...}}), 200
```

**Error codes:** `ERR_NOT_FOUND` · `ERR_UNAUTHORIZED` · `ERR_VALIDATION` · `ERR_SERVER` · `ERR_RATE_LIMIT`

**Test setup:**
```python
# conftest.py provides: app, client, admin_headers fixtures
# ADMIN_ACCESS_KEY in tests = "test-admin-key-2026"
# Database = SQLite in-memory
# Run: python -m pytest backend/tests/ -q --tb=short
```

---

## File Map

| File | Action | Responsibility |
|---|---|---|
| `backend/middleware/__init__.py` | CREATE | Package init |
| `backend/middleware/logging.py` | CREATE | HTTP request logging middleware |
| `backend/metrics.py` | CREATE | `/api/metrics` Blueprint + handler |
| `backend/tasks/task_registry.py` | CREATE | Task metadata map (used by admin panel) |
| `backend/celery_tasks.py` | MODIFY | Add retry + last-run tracking to all 12 scheduled tasks |
| `backend/routes/trip_tools.py` | MODIFY | Add `POST /api/trip/<id>/reorder-activity` |
| `backend/routes/admin.py` | MODIFY | Normalize error envelopes (template for all routes) |
| `backend/app.py` | MODIFY | Register logging middleware + metrics blueprint |
| `backend/tests/test_hardening.py` | CREATE | Tests for new endpoints |

---

## Task 1: Logging Middleware

**Files:**
- Create: `backend/middleware/__init__.py`
- Create: `backend/middleware/logging.py`
- Modify: `backend/app.py` (register middleware)

- [ ] **Step 1.1: Write the failing test**

```python
# backend/tests/test_hardening.py
import pytest

def test_logging_middleware_attaches(client):
    """Every response should complete without error — middleware registers cleanly."""
    resp = client.get("/health")
    assert resp.status_code == 200
```

- [ ] **Step 1.2: Run it — expect PASS (health endpoint exists, this is a smoke test)**

```bash
python -m pytest backend/tests/test_hardening.py::test_logging_middleware_attaches -v
```

- [ ] **Step 1.3: Create package init**

```python
# backend/middleware/__init__.py
```

- [ ] **Step 1.4: Create logging middleware**

```python
# backend/middleware/logging.py
import time

import structlog
from flask import Flask, g, request

log = structlog.get_logger(__name__)


def register_logging_middleware(app: Flask) -> None:
    """Attach before/after request hooks that emit structured JSON log lines."""

    @app.before_request
    def _start_timer() -> None:
        g._request_start = time.monotonic()

    @app.after_request
    def _log_request(response):
        duration_ms = int(
            (time.monotonic() - g.get("_request_start", time.monotonic())) * 1000
        )
        log.info(
            "http_request",
            method=request.method,
            path=request.path,
            status=response.status_code,
            duration_ms=duration_ms,
            ip=request.remote_addr,
        )
        return response
```

- [ ] **Step 1.5: Register in app factory**

Open `backend/app.py`. Find the line `def create_app(config=None):` and add the import + call inside the factory, after `db.init_app(app)`:

```python
# Add import near top of file
from backend.middleware.logging import register_logging_middleware

# Inside create_app(), after db.init_app(app):
register_logging_middleware(app)
```

- [ ] **Step 1.6: Run test again — expect PASS**

```bash
python -m pytest backend/tests/test_hardening.py::test_logging_middleware_attaches -v
```

- [ ] **Step 1.7: Commit**

```bash
git add backend/middleware/ backend/app.py backend/tests/test_hardening.py
git commit -m "feat: add structured HTTP request logging middleware"
```

---

## Task 2: Consistent Error Envelope — All Routes

**Files:**
- Modify: ALL `backend/routes/*.py` files (18 files)

**Pattern to apply to every route file:**

```python
# BEFORE (any of these patterns):
return jsonify({"error": "Not found"}), 404
return jsonify({"message": "ok"}), 200
return jsonify({"error": "Bad request", "details": x}), 400

# AFTER:
return jsonify({"success": False, "error": "Not found", "code": "ERR_NOT_FOUND"}), 404
return jsonify({"success": True, "data": {"message": "ok"}}), 200
return jsonify({"success": False, "error": "Bad request", "code": "ERR_VALIDATION", "details": x}), 400
```

**Code mapping:**

| Old pattern | New `code` value |
|---|---|
| 404 errors | `ERR_NOT_FOUND` |
| 401 / 403 | `ERR_UNAUTHORIZED` |
| 400 validation | `ERR_VALIDATION` |
| 429 rate limit | `ERR_RATE_LIMIT` |
| 500 / unexpected | `ERR_SERVER` |

- [ ] **Step 2.1: Write tests for envelope shape**

Add to `backend/tests/test_hardening.py`:

```python
def test_error_envelope_shape_on_missing_trip(client, auth_headers):
    """404 responses must have success=False and a code field."""
    resp = client.get("/api/trip/99999", headers=auth_headers)
    assert resp.status_code == 404
    body = resp.get_json()
    assert body["success"] is False
    assert "error" in body
    assert "code" in body
    assert body["code"] == "ERR_NOT_FOUND"

def test_success_envelope_has_success_true(client, auth_headers):
    """Successful list endpoints must include success=True."""
    resp = client.get("/api/user/trips", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["success"] is True
```

- [ ] **Step 2.2: Run — expect FAIL (envelopes not yet normalized)**

```bash
python -m pytest backend/tests/test_hardening.py::test_error_envelope_shape_on_missing_trip -v
```

- [ ] **Step 2.3: Apply envelope to all 18 route files**

Process each file in `backend/routes/`. For each `return jsonify(...)` call:
- If it's an error response (4xx/5xx): add `"success": False` and `"code": "ERR_*"`
- If it's a success response: add `"success": True`, wrap payload under `"data"` key if not already present

Work through files alphabetically:
`admin.py` → `auth.py` → `blogs.py` → `bookings.py` → `dashboard.py` → `destinations.py` → `discover.py` → `expenses.py` → `feedback.py` → `ops.py` → `profile.py` → `search.py` → `sharing.py` → `signals.py` → `trip_editor.py` → `trip_tools.py` → `trips.py` → `webhooks.py`

- [ ] **Step 2.4: Run all tests — fix any response shape failures**

```bash
python -m pytest backend/tests/ -q --tb=short
```

Expected: 188+ passed. Any failures are from tests asserting old envelope shapes — update the test assertions to match new envelope.

- [ ] **Step 2.5: Commit**

```bash
git add backend/routes/
git commit -m "refactor: normalize error envelopes across all 18 route files"
```

---

## Task 3: Expose Redis Client + /api/metrics Endpoint

**Files:**
- Modify: `backend/services/cache_service.py` (add `get_redis_client()`)
- Create: `backend/metrics.py`
- Modify: `backend/app.py` (register blueprint)

- [ ] **Step 3.1: Write failing test**

Add to `backend/tests/test_hardening.py`:

```python
def test_metrics_endpoint_requires_admin(client):
    resp = client.get("/api/metrics")
    assert resp.status_code in (401, 403)

def test_metrics_endpoint_returns_expected_fields(client, admin_headers):
    resp = client.get("/api/metrics", headers=admin_headers)
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["success"] is True
    data = body["data"]
    expected_fields = [
        "trips_generated_24h", "active_jobs", "cache_hit_rate",
        "embedding_coverage_pct", "gemini_429_count_24h",
        "worker_alive", "redis_memory_mb",
    ]
    for field in expected_fields:
        assert field in data, f"Missing field: {field}"
```

- [ ] **Step 3.2: Run — expect FAIL (endpoint doesn't exist)**

```bash
python -m pytest backend/tests/test_hardening.py::test_metrics_endpoint_returns_expected_fields -v
```

- [ ] **Step 3.3: Add `get_redis_client()` to cache_service**

Open `backend/services/cache_service.py`. Add at the end:

```python
def get_redis_client():
    """Return the Redis client instance, or None if Redis is unavailable."""
    return _r if REDIS_OK else None
```

- [ ] **Step 3.4: Create metrics blueprint**

```python
# backend/metrics.py
"""
metrics.py — /api/metrics endpoint.
Returns live operational stats for admin monitoring.
"""
import json

import structlog
from flask import Blueprint, jsonify

from backend.database import db
from backend.utils.auth import require_admin

log = structlog.get_logger(__name__)
metrics_bp = Blueprint("metrics", __name__)


@metrics_bp.get("/api/metrics")
@require_admin
def get_metrics():
    from backend.services.cache_service import get_redis_client, REDIS_OK
    from backend.models import AsyncJob

    r = get_redis_client()

    # Trips generated in last 24h (incremented by generate_itinerary_job task)
    trips_24h = 0
    cache_hits = 0
    cache_total = 0
    gemini_429 = 0
    worker_alive = False
    redis_memory_mb = 0.0

    if r:
        trips_24h = int(r.get("metrics:trips_generated_24h") or 0)
        cache_hits = int(r.get("metrics:cache_hits") or 0)
        cache_total = int(r.get("metrics:cache_total") or 1)
        gemini_429 = int(r.get("metrics:gemini_429_24h") or 0)
        # Worker alive if heartbeat written in last 10 minutes
        heartbeat = r.get("celery:heartbeat")
        if heartbeat:
            from datetime import datetime, timezone
            try:
                ts = datetime.fromisoformat(heartbeat)
                age_s = (datetime.now(timezone.utc) - ts).total_seconds()
                worker_alive = age_s < 600
            except Exception:
                pass
        # Redis memory
        try:
            info = r.info("memory")
            redis_memory_mb = round(info.get("used_memory", 0) / 1024 / 1024, 1)
        except Exception:
            pass

    cache_hit_rate = round(cache_hits / cache_total, 3) if cache_total > 0 else 0.0

    # Active jobs from DB
    try:
        active_jobs = AsyncJob.query.filter(
            AsyncJob.status.in_(["queued", "processing"])
        ).count()
    except Exception:
        active_jobs = 0

    # Embedding coverage
    try:
        from backend.models import Destination
        total = db.session.query(Destination).count()
        with_emb = db.session.query(Destination).filter(
            Destination.embedding.isnot(None)
        ).count()
        embedding_coverage_pct = round(with_emb / total, 3) if total > 0 else 0.0
    except Exception:
        embedding_coverage_pct = 0.0

    return jsonify({
        "success": True,
        "data": {
            "trips_generated_24h": trips_24h,
            "active_jobs": active_jobs,
            "cache_hit_rate": cache_hit_rate,
            "embedding_coverage_pct": embedding_coverage_pct,
            "gemini_429_count_24h": gemini_429,
            "worker_alive": worker_alive,
            "redis_memory_mb": redis_memory_mb,
        }
    })
```

- [ ] **Step 3.5: Register metrics blueprint in app.py**

In `backend/app.py`, inside `create_app()` where other blueprints are registered:

```python
from backend.metrics import metrics_bp
app.register_blueprint(metrics_bp)
```

- [ ] **Step 3.6: Run tests**

```bash
python -m pytest backend/tests/test_hardening.py::test_metrics_endpoint_returns_expected_fields backend/tests/test_hardening.py::test_metrics_endpoint_requires_admin -v
```

Expected: both PASS.

- [ ] **Step 3.7: Commit**

```bash
git add backend/metrics.py backend/services/cache_service.py backend/app.py backend/tests/test_hardening.py
git commit -m "feat: add /api/metrics endpoint with live operational stats"
```

---

## Task 4: Activity Reorder Endpoint

**Files:**
- Modify: `backend/routes/trip_tools.py`

- [ ] **Step 4.1: Write failing test**

Add to `backend/tests/test_hardening.py`:

```python
def test_reorder_activity_swaps_positions(client, auth_headers, saved_trip_id):
    """Reordering activities should change their positions in the itinerary."""
    # Get current activities for day 0
    resp = client.get(f"/api/trip/{saved_trip_id}", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.get_json()
    itinerary = body.get("data", body).get("itinerary_json", {})
    day0_activities = itinerary.get("itinerary", [{}])[0].get("activities", [])
    if len(day0_activities) < 2:
        pytest.skip("Trip has fewer than 2 activities on day 0")

    first_name = day0_activities[0]["name"]
    second_name = day0_activities[1]["name"]

    resp = client.post(
        f"/api/trip/{saved_trip_id}/reorder-activity",
        json={"day_index": 0, "from_index": 0, "to_index": 1},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["success"] is True
    new_activities = body["data"]["activities"]
    assert new_activities[0]["name"] == second_name
    assert new_activities[1]["name"] == first_name

def test_reorder_activity_invalid_index(client, auth_headers, saved_trip_id):
    resp = client.post(
        f"/api/trip/{saved_trip_id}/reorder-activity",
        json={"day_index": 0, "from_index": 999, "to_index": 0},
        headers=auth_headers,
    )
    assert resp.status_code == 400
    assert resp.get_json()["code"] == "ERR_VALIDATION"
```

- [ ] **Step 4.2: Run — expect FAIL (endpoint doesn't exist)**

```bash
python -m pytest backend/tests/test_hardening.py::test_reorder_activity_swaps_positions -v
```

- [ ] **Step 4.3: Add reorder endpoint to trip_tools.py**

Open `backend/routes/trip_tools.py`. Add this after the imports (add `import copy` if not present):

```python
import copy
```

Add this endpoint before the last line of the file:

```python
@trip_tools_bp.post("/api/trip/<int:trip_id>/reorder-activity")
@jwt_required()
def reorder_activity(trip_id: int):
    """Reorder activities within a day.

    Body: {"day_index": int, "from_index": int, "to_index": int}
    """
    user_id = get_jwt_identity()
    data = request.get_json() or {}
    day_index = data.get("day_index")
    from_index = data.get("from_index")
    to_index = data.get("to_index")

    if any(v is None for v in [day_index, from_index, to_index]):
        return jsonify({
            "success": False,
            "error": "day_index, from_index, and to_index are required",
            "code": "ERR_VALIDATION",
        }), 400

    trip = Trip.query.filter_by(id=trip_id, user_id=user_id).first()
    if not trip:
        return jsonify({"success": False, "error": "Trip not found", "code": "ERR_NOT_FOUND"}), 404

    itinerary = copy.deepcopy(trip.itinerary_json or {})
    days = itinerary.get("itinerary", [])

    if day_index >= len(days):
        return jsonify({"success": False, "error": "Day not found", "code": "ERR_VALIDATION"}), 400

    activities = days[day_index].get("activities", [])
    if from_index >= len(activities) or to_index >= len(activities):
        return jsonify({
            "success": False,
            "error": f"Activity index out of range (day has {len(activities)} activities)",
            "code": "ERR_VALIDATION",
        }), 400

    activities.insert(to_index, activities.pop(from_index))
    days[day_index]["activities"] = activities
    trip.itinerary_json = itinerary
    trip.is_customized = 1
    db.session.commit()

    log.info("activity_reordered", trip_id=trip_id, day=day_index, frm=from_index, to=to_index)
    return jsonify({"success": True, "data": {"activities": activities}})
```

- [ ] **Step 4.4: Run tests**

```bash
python -m pytest backend/tests/test_hardening.py -k "reorder" -v
```

Expected: PASS.

- [ ] **Step 4.5: Commit**

```bash
git add backend/routes/trip_tools.py backend/tests/test_hardening.py
git commit -m "feat: add POST /api/trip/:id/reorder-activity endpoint"
```

---

## Task 5: Task Registry + Celery Retry Hardening

**Files:**
- Create: `backend/tasks/task_registry.py`
- Modify: `backend/celery_tasks.py` (all 12 scheduled tasks)

- [ ] **Step 5.1: Create task registry**

```python
# backend/tasks/task_registry.py
"""
task_registry.py — Metadata for all scheduled Celery tasks.
Used by admin panel to display task status, schedule, and errors.
Redis keys written by tasks:
  celery:task:{name}:last  → JSON {ts, status, duration_s}
  celery:errors:{name}     → LIST of JSON {ts, error} (max 10)
"""

TASK_REGISTRY: dict[str, dict] = {
    "run_osm_ingestion":         {"label": "OSM POI Ingestion",        "schedule": "Sunday 03:00"},
    "run_enrichment":            {"label": "Destination Enrichment",    "schedule": "Daily"},
    "run_scoring":               {"label": "Attraction Scoring",        "schedule": "Daily"},
    "run_price_sync":            {"label": "Price Sync",                "schedule": "Daily 06:00 & 18:00"},
    "run_score_update":          {"label": "Popularity Score Update",   "schedule": "Daily 02:00"},
    "run_destination_validation":{"label": "Destination Validation",    "schedule": "Daily 01:00"},
    "run_cache_warm":            {"label": "Cache Warm",                "schedule": "Daily 03:30"},
    "run_affiliate_health":      {"label": "Affiliate Health",          "schedule": "Every 6h"},
    "run_quality_scoring":       {"label": "Trip Quality Scoring",      "schedule": "Daily 04:30"},
    "run_weather_sync":          {"label": "Weather Sync",              "schedule": "Daily 05:30"},
    "run_post_trip_summaries":   {"label": "Post-Trip Summaries",       "schedule": "Daily"},
    "run_embedding_sync":        {"label": "Embedding Sync",            "schedule": "Weekly"},
}
```

- [ ] **Step 5.2: Add `_write_task_result` helper to celery_tasks.py**

Open `backend/celery_tasks.py`. Add this helper function after the imports, before the first `@celery_app.task`:

```python
import json
import time
from datetime import datetime, timezone


def _write_task_result(task_name: str, status: str, duration_s: float, error: str | None = None) -> None:
    """Write task execution metadata to Redis for admin panel consumption."""
    try:
        from backend.services.cache_service import get_redis_client
        r = get_redis_client()
        if r is None:
            return
        payload = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "status": status,
            "duration_s": round(duration_s, 2),
        }
        r.set(f"celery:task:{task_name}:last", json.dumps(payload))
        if error:
            error_entry = json.dumps({"ts": payload["ts"], "error": error[:500]})
            r.lpush(f"celery:errors:{task_name}", error_entry)
            r.ltrim(f"celery:errors:{task_name}", 0, 9)  # keep last 10
    except Exception:
        pass  # never let monitoring crash the task
```

- [ ] **Step 5.3: Wrap all 12 scheduled tasks with retry + tracking**

Apply this pattern to each task. Example for `run_score_update`:

```python
# BEFORE:
@celery_app.task(name="backend.celery_tasks.run_score_update")
def run_score_update():
    from backend.tasks.score_updater import run as _run
    _run()

# AFTER:
@celery_app.task(name="backend.celery_tasks.run_score_update", bind=True, max_retries=3, default_retry_delay=60)
def run_score_update(self):
    _start = time.monotonic()
    try:
        from backend.tasks.score_updater import run as _run
        _run()
        _write_task_result("run_score_update", "success", time.monotonic() - _start)
    except Exception as exc:
        _write_task_result("run_score_update", "failed", time.monotonic() - _start, str(exc))
        raise self.retry(exc=exc)
```

Apply to all 12 tasks:
`run_osm_ingestion`, `run_enrichment`, `run_scoring`, `run_price_sync`, `run_score_update`, `run_destination_validation`, `run_cache_warm`, `run_affiliate_health`, `run_quality_scoring`, `run_weather_sync`, `run_post_trip_summaries`, `run_embedding_sync`

- [ ] **Step 5.4: Write test for task registry**

Add to `backend/tests/test_hardening.py`:

```python
def test_task_registry_has_all_scheduled_tasks():
    from backend.tasks.task_registry import TASK_REGISTRY
    expected = {
        "run_score_update", "run_weather_sync", "run_quality_scoring",
        "run_price_sync", "run_cache_warm", "run_embedding_sync",
        "run_affiliate_health", "run_destination_validation",
        "run_post_trip_summaries", "run_osm_ingestion",
        "run_enrichment", "run_scoring",
    }
    assert expected == set(TASK_REGISTRY.keys())
    for name, meta in TASK_REGISTRY.items():
        assert "label" in meta, f"{name} missing label"
        assert "schedule" in meta, f"{name} missing schedule"

def test_write_task_result_is_safe_without_redis(monkeypatch):
    """_write_task_result must never raise even when Redis is down."""
    from backend import celery_tasks
    monkeypatch.setattr("backend.services.cache_service.REDIS_OK", False)
    # Should not raise
    celery_tasks._write_task_result("run_score_update", "success", 1.5)
```

- [ ] **Step 5.5: Run tests**

```bash
python -m pytest backend/tests/test_hardening.py -v
python -m pytest backend/tests/ -q --tb=short
```

Expected: all 188+ original tests still pass, new tests pass.

- [ ] **Step 5.6: Commit**

```bash
git add backend/tasks/task_registry.py backend/celery_tasks.py backend/tests/test_hardening.py
git commit -m "feat: add Celery retry hardening + task result tracking to Redis"
```

---

## Self-Review Checklist

- [x] Spec coverage: logging ✓, error envelopes ✓, metrics ✓, reorder ✓, retry hardening ✓
- [x] No placeholders — all steps have complete code
- [x] `get_redis_client()` defined in Task 3 before used in Task 5
- [x] `_write_task_result` defined in Task 5 before wrapping tasks
- [x] Error codes consistent: `ERR_NOT_FOUND`, `ERR_VALIDATION`, `ERR_SERVER`, `ERR_UNAUTHORIZED`, `ERR_RATE_LIMIT`
- [x] All tests use `conftest.py` fixtures (`client`, `auth_headers`, `admin_headers`)
