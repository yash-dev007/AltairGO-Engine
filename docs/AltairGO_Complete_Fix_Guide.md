# AltairGO Intelligence — Complete Technical Fix Guide + Mission Control Dashboard

> **Series A Pre-Launch Audit · March 2026**
> Overall Risk Score: **5 / 10** | 7 Critical Blockers | Estimated Fix Time: **3–4 days**

---

## Table of Contents

- [Part 1 — Bug & Security Fix Register](#part-1--bug--security-fix-register)
- [Part 2 — Architecture Repairs](#part-2--architecture-repairs)
- [Part 3 — Mission Control Dashboard Specification](#part-3--mission-control-dashboard-specification)
- [Part 4 — Backend API Endpoints for Dashboard](#part-4--backend-api-endpoints-for-dashboard)
- [Part 5 — Engine Control Panel](#part-5--engine-control-panel)
- [Part 6 — Real-Time Data Strategy](#part-6--real-time-data-strategy)
- [Part 7 — Implementation Roadmap](#part-7--implementation-roadmap)
- [Part 8 — Production Deployment Checklist](#part-8--production-deployment-checklist)
- [Final Assessment](#final-assessment)

---

# Part 1 — Bug & Security Fix Register

> Every issue found in the codebase. Each item has a severity rating, affected file, exact BEFORE/AFTER code, and why it matters in production.

---

## 1.1 Issue Summary Table

| Severity | File | Problem | Root Cause | Fix Summary |
|---|---|---|---|---|
| 🔴 CRITICAL | `database.py` | DummyDBWrapper breaks Flask-Migrate — migrations never run | `db.metadata` / `db.get_engine()` do not exist | Replace with Flask-SQLAlchemy `init_app()` |
| 🔴 CRITICAL | `database.py` | Hardcoded PostgreSQL password in fallback | Fallback URL `altairgo:altairgo_dev_pass` used if `DATABASE_URL` unset | Raise `RuntimeError` instead of fallback |
| 🔴 CRITICAL | `extensions.py` | Rate limiter uses `memory://` — 4× ineffective with Gunicorn workers | Each worker has own counter; no Redis coordination | Require `REDIS_URL`; raise if missing |
| 🔴 CRITICAL | `admin.py` | No rate limit on `/api/admin/verify-key` — brute-forceable | Unlimited POST attempts, no throttle | Add `@limiter.limit("10 per minute")` |
| 🔴 CRITICAL | `trips.py` | Module-level `polish_itinerary_text()` uses `gemini-1.5-flash`, no retries | `GeminiService` class (2.0-flash + retry) is never called in production | Wire `GeminiService` class; delete old function |
| 🔴 CRITICAL | `trips.py` / `orchestrator.py` | `VALIDATION_STRICT` env var never reaches `ItineraryValidator` | Strict mode and auto-scaling budgets are dead code in production | Pass `_is_truthy(os.getenv("VALIDATION_STRICT"))` to validator |
| 🔴 CRITICAL | `app.py` | No `/health` endpoint — Dockerfile HEALTHCHECK kills container in a loop | `HEALTHCHECK CMD curl /health` returns 404; container marked unhealthy | Add `/health` route checking DB + Redis |
| 🟠 HIGH | `auth.py` | JWT tokens have 7-day expiry, no refresh endpoint, non-revocable | Stolen token valid for 7 days; no graceful renewal for clients | Add `/auth/refresh`, shorten access to 1h |
| 🟠 HIGH | `app.py` | `os.environ` mutation inside `create_app()` breaks multi-worker safety | Gunicorn fork workers inherit mutated env; test config leaks to prod | Remove `os.environ` mutations; pass values directly |
| 🟠 HIGH | `orchestrator.py` | `HotelPrice` / `FlightRoute` queries crash if tables not migrated yet | `ProgrammingError: relation does not exist` on first deploy | Wrap in `try/except`; gracefully return `None` |
| 🟠 HIGH | `engine/filter_engine.py` | `compatible_traveler_types` stored as Python repr string, not JSON | String `"couple"` matches any dest containing the substring — wrong results | Parse with `json.loads()`; default `[]` on error |
| 🟠 HIGH | `engine/cluster_engine.py` | Attractions with null `h3_index_r7` all land in `day_1` | Any attraction with missing GPS clusters into day 1; other days empty | Skip null h3_index attractions with warning log |
| 🟠 HIGH | `assembler.py` | `smart_insights` and `packing_tips` always return empty arrays | Gemini polish never writes back these fields; users see blank panels | Merge polish response fields back into assembled result |
| 🟡 MEDIUM | `schemas.py` | No minimum password length validation | Users can register with 1-character passwords | Add `validate.Length(min=8, max=128)` |
| 🟡 MEDIUM | `schemas.py` | No `duration >= 1` validation — division by zero in BudgetAllocator | `duration=0` payload causes `ZeroDivisionError` → 500 to user | Add `validate.Range(min=1, max=30)` |
| 🟡 MEDIUM | `admin.py` | `create_access_token` imported twice (module + inside function) | Signals hasty editing; harmless but reduces code clarity | Remove duplicate inner import |
| 🟡 MEDIUM | `app.py` | `_configure_logging` uses mutable function attribute anti-pattern | `_configured` attribute is non-obvious; can cause double-init race | Use module-level `_logging_configured = False` |
| 🟡 MEDIUM | `.env.example` | `JWT_SECRET_KEY=change-me-in-dev` (16 chars) fails the 32-char guard | Copying `.env.example` to `.env` causes `RuntimeError` on startup | Replace with 64-char placeholder instructions |
| 🔵 LOW | `engine/assembler.py` | `detect_theme()` requires ≥2 type matches; single-attraction days never match | Every day with 1 attraction shows "Explore & Discover" regardless of type | Lower threshold to ≥1 |
| 🔵 LOW | `orchestrator.py` | Metrics write failures (Redis down) propagate and crash itinerary generation | Redis blip kills entire generation; should be fire-and-forget | Wrap `mark_status()` calls in `try/except` |
| 🔵 LOW | `engine/*` | Magic numbers hardcoded in 4 files (25 km/h, score ≥ 25, cap of 2) | Cannot tune without hunting through source files | Extract to `engine/config.py` constants file |
| 🔵 LOW | `gemini_service.py` | `destination_data[:3]` silently drops destinations 4, 5, 6+ | User selects 5 destinations; itinerary only covers 3 with no warning | Use all destinations or log a warning when truncated |

---

## Fix 1 — Replace DummyDBWrapper with Flask-SQLAlchemy `[CRITICAL]`

**File:** `backend/database.py` and `backend/app.py`

**Why this matters:** Flask-Migrate (Alembic) calls `db.metadata`, `db.get_engine()`, and `db.Model` — none of which exist on `DummyDBWrapper`. Every `flask db migrate` and `flask db upgrade` command silently fails or crashes. Your production schema is never tracked, meaning schema drift between code and database is guaranteed after your first deployment.

### `database.py` — Replace the entire file

```python
# BEFORE — DummyDBWrapper approach (broken with Flask-Migrate)
class DummyDBWrapper:
    def __init__(self, engine, session):
        self.engine = engine
        self.session = session

db = DummyDBWrapper(engine, db_session)
```

```python
# AFTER — Proper Flask-SQLAlchemy
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

def configure_database(app, database_url: str):
    """Call this once from create_app() with the resolved URL."""
    app.config["SQLALCHEMY_DATABASE_URI"] = database_url
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
        "pool_pre_ping": True,
        "pool_recycle": 300,
        "connect_args": {}
          if not database_url.startswith("sqlite")
          else {"check_same_thread": False}
    }
    db.init_app(app)

Base = db.Model  # All models inherit from db.Model

def init_db(app):
    """Test-only. Production uses: flask db upgrade."""
    if not app.config.get("TESTING"):
        raise RuntimeError("init_db() is for tests only.")
    with app.app_context():
        db.create_all()
```

### `app.py` — Wire correctly

```python
# Replace:
database.configure_database(app.config["SQLALCHEMY_DATABASE_URI"])
Migrate(app, database.db)

# With:
database.configure_database(app, app.config["SQLALCHEMY_DATABASE_URI"])
Migrate(app, database.db)  # Now works correctly
```

---

## Fix 2 — Remove Hardcoded Database Credentials `[CRITICAL]`

**File:** `backend/database.py` lines 28-32

**Why this matters:** The fallback URL `"postgresql://altairgo:altairgo_dev_pass@localhost:5432/altairgo"` will be used silently if `DATABASE_URL` is not set. In production, this either connects to the wrong database or exposes credentials committed to source control.

```python
# BEFORE
else:
    DATABASE_URL = "postgresql://altairgo:altairgo_dev_pass@localhost:5432/altairgo"
```

```python
# AFTER
else:
    raise RuntimeError(
        "DATABASE_URL env var is required.\n"
        "Set it in backend/.env"
    )
```

---

## Fix 3 — Fix Rate Limiter to Use Redis `[CRITICAL]`

**File:** `backend/extensions.py`

**Why this matters:** `memory://` storage means each Gunicorn worker process has its own independent counter. With 4 workers, the actual effective limit for a single IP is **4 × 5 = 20** itinerary requests per minute instead of 5. One motivated person can exhaust your entire Gemini API quota.

```python
# BEFORE
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=[],
    storage_uri=os.getenv(
        "RATE_LIMIT_STORAGE_URL",
        os.getenv("REDIS_URL", "memory://")
    ),
)
```

```python
# AFTER
_redis_url = os.getenv("REDIS_URL")
if not _redis_url:
    raise RuntimeError(
        "REDIS_URL is required for rate limiting across workers."
    )

limiter = Limiter(
    key_func=get_remote_address,
    default_limits=[],
    storage_uri=_redis_url,
)
```

---

## Fix 4 — Rate Limit Admin Verify Endpoint `[CRITICAL]`

**File:** `backend/routes/admin.py`

**Why this matters:** Without any rate limit, an automated script can try thousands of admin keys per second. The `ADMIN_ACCESS_KEY` is a single shared secret with no complexity requirements.

```python
# BEFORE
@admin_bp.route('/api/admin/verify-key', methods=['POST'])
def verify_key():
```

```python
# AFTER
from backend.extensions import limiter

@admin_bp.route('/api/admin/verify-key', methods=['POST'])
@limiter.limit("10 per minute; 50 per hour")
def verify_key():
```

---

## Fix 5 — Wire GeminiService Class in `trips.py` `[CRITICAL]`

**File:** `backend/routes/trips.py` and `backend/services/gemini_service.py`

**Why this matters:** The module-level `polish_itinerary_text()` function uses `gemini-1.5-flash` (old model) with no retry logic and no fallback. The `GeminiService` class was built with `gemini-2.0-flash`, 3-retry logic, and fallback to `gemini-2.0-flash-lite`. **Production is running on the old path.**

```python
# BEFORE — trips.py using old module function
from backend.services import gemini_service
...
polished = gemini_service.polish_itinerary_text(assembled, user_prefs)
```

```python
# AFTER — trips.py using correct class
from backend.services.gemini_service import GeminiService

GEMINI_SERVICE = GeminiService(api_key=os.getenv("GEMINI_API_KEY"))
...
polished = GEMINI_SERVICE.polish_itinerary_text(assembled, user_prefs)
```

> **Also:** Delete the module-level `polish_itinerary_text()` function from `gemini_service.py` and the `GEMINI_URL` constant pointing to `gemini-1.5-flash` at the top of the file.

---

## Fix 6 — Wire `VALIDATION_STRICT` to `ItineraryValidator` `[CRITICAL]`

**File:** `backend/engine/orchestrator.py`

**Why this matters:** The auto-scale budget correction in `ItineraryValidator` is the main validation feature. The env var is read but never passed, so every over-budget itinerary is logged as an error but never fixed. **Users receive itineraries that cost more than they specified.**

```python
# BEFORE — strict never set
validator = ItineraryValidator(strict=False)
result = validator.validate(assembled, request_data["budget"])
```

```python
# AFTER — wired correctly
import os
strict = _is_truthy(os.getenv("VALIDATION_STRICT", "false"))
validator = ItineraryValidator(strict=strict)
result = validator.validate(assembled, request_data["budget"])
```

---

## Fix 7 — Add `/health` Endpoint `[CRITICAL]`

**File:** `backend/app.py` (add after blueprint registration)

**Why this matters:** The Dockerfile `HEALTHCHECK` uses `curl /health`. Without this endpoint, the health check returns 404, the container is marked **unhealthy**, and Kubernetes/ECS will restart it in a loop — taking the backend offline within minutes of deployment.

```python
# Add to app.py, after all blueprint registrations
@app.route("/health")
def health():
    checks = {"status": "ok", "db": "unknown", "redis": "unknown"}
    try:
        db.session.execute(text("SELECT 1"))
        checks["db"] = "ok"
    except Exception as e:
        checks["db"] = f"error: {e}"
        checks["status"] = "degraded"
    try:
        r = redis.from_url(app.config["REDIS_URL"])
        r.ping()
        checks["redis"] = "ok"
    except Exception as e:
        checks["redis"] = f"error: {e}"
        checks["status"] = "degraded"
    code = 200 if checks["status"] == "ok" else 503
    return jsonify(checks), code
```

---

## Fix 8 — JWT Refresh Endpoint + Short Expiry `[HIGH]`

**File:** `backend/routes/auth.py` and `backend/app.py`

**Why this matters:** 7-day tokens cannot be revoked. If stolen via XSS or log leakage, an attacker has 7 days of access. Frontend clients also have no way to silently renew — after 7 days they get hard 401 errors requiring a full re-login.

```python
# app.py — add to create_app() config section
from datetime import timedelta
app.config["JWT_ACCESS_TOKEN_EXPIRES"] = timedelta(hours=1)
app.config["JWT_REFRESH_TOKEN_EXPIRES"] = timedelta(days=30)
```

```python
# auth.py — update login to return both tokens
from flask_jwt_extended import (
    create_access_token, create_refresh_token,
    jwt_required, get_jwt_identity
)

@auth_bp.route("/login", methods=["POST"])
def login():
    ...
    access = create_access_token(identity=str(user.id))
    refresh = create_refresh_token(identity=str(user.id))
    return jsonify({
        "token": access,
        "refresh_token": refresh,
        "user": {...}
    }), 200

@auth_bp.route("/refresh", methods=["POST"])
@jwt_required(refresh=True)
def refresh():
    user_id = get_jwt_identity()
    new_token = create_access_token(identity=user_id)
    return jsonify({"token": new_token}), 200
```

---

## Fix 9 — Fix ClusterEngine Null `h3_index_r7` Bug `[HIGH]`

**File:** `backend/engine/cluster_engine.py`

**Why this matters:** After OSM ingestion, many attractions have NULL coordinates or `0,0` GPS values. All of them get assigned to the same cluster key (`None`), which collapses into `day_1`. A 7-day itinerary might have 10 activities on day 1 and nothing on days 2–7.

```python
# BEFORE — no null check
for attraction in attractions:
    key = attraction.h3_index_r7
    buckets[key].append(attraction)
```

```python
# AFTER — skip attractions without valid coords
for attraction in attractions:
    key = attraction.h3_index_r7
    if not key:  # None or empty string
        log.warning(
            "Skipping attraction with null h3",
            id=attraction.id,
            name=getattr(attraction, "name", "?")
        )
        continue
    buckets[key].append(attraction)
```

---

## Fix 10 — Fix `traveler_type` JSON Deserialisation in FilterEngine `[HIGH]`

**File:** `backend/engine/filter_engine.py`

**Why this matters:** The `enrich_destinations.py` script stores `compatible_traveler_types` as a Python repr string like `"['solo', 'couple']"` instead of valid JSON. `FilterEngine`'s `"couple" in compatible_traveler_types` check then does **substring matching on a string** — `"solo_male"` accidentally matches because the string contains `"solo"`. Wrong attractions get included.

```python
# BEFORE — direct membership test on raw field
if traveler_type not in attraction.compatible_traveler_types:
    return False
```

```python
# AFTER — parse defensively first
import json

raw = attraction.compatible_traveler_types
if isinstance(raw, str):
    try:
        compatible = json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        compatible = []  # corrupt data → no restriction
elif isinstance(raw, list):
    compatible = raw
else:
    compatible = []

if compatible and traveler_type not in compatible:
    return False
```

---

## Fix 11 — Populate `smart_insights` and `packing_tips` `[HIGH]`

**File:** `backend/engine/orchestrator.py`

**Why this matters:** `Assembler.assemble()` always returns empty lists for `smart_insights` and `packing_tips`. Gemini polish generates them but the orchestrator never merges them back into the result. **Users see blank panels on the frontend.**

```python
# In orchestrator.py, after the Gemini polish step:
polished = self.gemini.polish_itinerary_text(assembled, user_prefs)

# Merge AI-generated narrative fields back
if isinstance(polished, dict):
    assembled["smart_insights"] = polished.get("smart_insights") or []
    assembled["packing_tips"] = polished.get("packing_tips") or []
    # Merge enriched activity descriptions
    for i, day in enumerate(assembled.get("itinerary", [])):
        polished_day = (polished.get("itinerary") or [])[i:i+1]
        if polished_day:
            for key in ["description", "why_this_fits", "local_secret"]:
                if key in polished_day[0]:
                    day[key] = polished_day[0][key]
```

---

## Fix 12 — Guard `HotelPrice` / `FlightRoute` Queries `[HIGH]`

**File:** `backend/engine/orchestrator.py`

**Why this matters:** If tables don't exist yet (first deployment before migrations run), the query throws `ProgrammingError: relation "hotel_price" does not exist` — crashing the entire itinerary generation with a 500 error.

```python
# BEFORE — crashes if table missing
hotel = self.db.query(HotelPrice).filter_by(
    destination_id=primary_dest.id,
    category=tier
).first()
```

```python
# AFTER — graceful fallback
try:
    hotel = self.db.query(HotelPrice).filter_by(
        destination_id=primary_dest.id,
        category=tier
    ).order_by(HotelPrice.last_synced.desc()).first()
except Exception as exc:
    log.warning("HotelPrice query failed", error=str(exc))
    hotel = None
```

---

## Fix 13 — Add Password & Duration Validation `[MEDIUM]`

**File:** `backend/schemas.py`

```python
# In RegisterSchema — add length validation
from marshmallow import validate

class RegisterSchema(Schema):
    name = fields.Str(required=True, validate=validate.Length(min=1, max=100))
    email = fields.Email(required=True)
    password = fields.Str(required=True, validate=validate.Length(min=8, max=128))

# In GenerateItinerarySchema — prevent division by zero
class GenerateItinerarySchema(Schema):
    duration = fields.Int(required=True, validate=validate.Range(min=1, max=30))
    budget = fields.Int(required=True, validate=validate.Range(min=100))
```

---

## Fix 14 — Guard Metrics Writes Against Redis Blips `[MEDIUM]`

**File:** `backend/engine/orchestrator.py` — wrap every call to `mark_status()`

```python
# BEFORE — Redis failure crashes generation
mark_status("agent", "memory", "ok", {...})
```

```python
# AFTER — fire-and-forget
try:
    mark_status("agent", "memory", "ok", {...})
except Exception as metrics_err:
    log.warning("metrics_write_failed", error=str(metrics_err))
```

---

## Fix 15 — Fix `.env.example` with Valid Placeholder Values `[MEDIUM]`

**File:** `backend/.env.example`

Current `JWT_SECRET_KEY=change-me-in-dev` (16 chars) fails the 32-char guard in `_validate_jwt_secret()`. Anyone who copies `.env.example` to `.env` cannot start the app.

```env
# CORRECT .env.example
DATABASE_URL=postgresql://altairgo:CHANGE_ME@localhost:5432/altairgo
REDIS_URL=redis://localhost:6379/0

# Generate with: python -c "import secrets; print(secrets.token_hex(32))"
JWT_SECRET_KEY=REPLACE_WITH_64_CHAR_HEX_FROM_COMMAND_ABOVE
ADMIN_ACCESS_KEY=REPLACE_WITH_STRONG_RANDOM_KEY

GEMINI_API_KEY=
PEXELS_API_KEY=
VALIDATION_STRICT=true
ALLOWED_ORIGINS=https://yourdomain.com,http://localhost:5173
```

---

## Fix 16 — Lower `detect_theme` Threshold to 1 `[LOW]`

**File:** `backend/engine/assembler.py`

```python
# BEFORE — requires 2 matching types
return best_match if best_overlap >= 2 else "Explore & Discover"
```

```python
# AFTER — works with even a single attraction
return best_match if best_overlap >= 1 else "Explore & Discover"
```

---

# Part 2 — Architecture Repairs

---

## 2.1 Celery Beat High Availability — Prevent Silent Job Failures

**File:** `backend/celery_config.py` and `requirements.txt`

The current Celery Beat process stores the schedule in memory. If it crashes, all 9 scheduled jobs stop running **silently** — no alert, no retry. `celery-redbeat` stores the schedule in Redis so it survives crashes.

```bash
pip install celery-redbeat
```

```python
# celery_config.py — add to conf.update()
celery_app.conf.beat_scheduler = "redbeat.RedBeatScheduler"
celery_app.conf.redbeat_redis_url = os.getenv("REDIS_URL")
celery_app.conf.result_expires = 3600  # 1 hour
```

---

## 2.2 Docker — Add `.dockerignore` to Prevent Secret Leakage

Without `.dockerignore`, the `COPY . .` instruction copies `.env`, `__pycache__`, and test fixtures into the Docker image. Anyone who pulls your image can extract your secrets.

Create file: `.dockerignore` in project root:

```
.env
.env.*
__pycache__/
*.pyc
*.pyo
.pytest_cache/
node_modules/
dummy-frontend/node_modules/
.git/
dist/
build/
*.egg-info/
backend/tests/
```

---

## 2.3 GitHub Actions CI Pipeline

Create file: `.github/workflows/ci.yml`

```yaml
name: CI
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgis/postgis:15-3.3
        env:
          POSTGRES_USER: altairgo
          POSTGRES_PASSWORD: testpass
          POSTGRES_DB: altairgo_test
      redis:
        image: redis:7
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.11" }
      - run: pip install -r backend/requirements.txt
      - run: |
          export TESTING=true
          export JWT_SECRET_KEY=test-secret-key-altairgo-ci-minimum-32-chars
          export ADMIN_ACCESS_KEY=test-admin-key-2026
          pytest backend/tests/ -v --tb=short
```

---

## 2.4 Gunicorn Configuration for Production

Create file: `gunicorn.conf.py` in project root:

```python
workers = 4
worker_class = "gevent"   # async workers — required for Gemini I/O
bind = "0.0.0.0:5000"
timeout = 120             # Gemini calls can take 15s
graceful_timeout = 30
keepalive = 5
access_logfile = "-"      # stdout for Docker
error_logfile = "-"
loglevel = "info"
```

```bash
pip install gevent
```

---

# Part 3 — Mission Control Dashboard Specification

> **Design Philosophy:**
> Every metric is real — pulled from PostgreSQL + Redis in real time.
> Every button does something — no decorative UI, each action calls a live backend endpoint.
> Non-technical friendly — plain language labels, no terminal commands needed.
> Always current — summary panel auto-refreshes every 30 seconds.
> Live feed — pipeline event stream updates in real time via Server-Sent Events.

---

## 3.1 Dashboard Panels

### Panel 1: System Status Bar *(Top of page, always visible)*

Shows the health of 3 core services at a glance. Green dot = healthy, Red dot = problem.

**Data source:** `GET /health` — checks live DB + Redis connection.

| Indicator | Data Source | What it checks |
|---|---|---|
| Database | `SELECT 1` via SQLAlchemy | Can the app write to the DB? |
| Redis | `PING` command | Is the cache/broker alive? |
| Celery | Redis key `celery:worker:last_seen` | Did a worker run in the last 5 minutes? |
| Last updated | Client timestamp | Is the dashboard data fresh? |

---

### Panel 2: AI Engine Metrics *(Left column)*

Shows Gemini API usage for today. Data resets at midnight IST.

| Metric | Redis Key | Description |
|---|---|---|
| Gemini calls today | `gemini:calls:today` | Total API calls made |
| Gemini errors today | `gemini:errors:today` | Failed API calls |
| Error rate % | calculated | `errors / max(calls, 1) × 100` |
| Estimated cost today (INR) | calculated | `calls × avg_tokens × per_token_price` |
| Cache hit rate % | `cache:hits:today` / `cache:misses:today` | How often Redis serves cached results |
| Avg generation time | `metrics:avg_gen_ms` | Rolling average over last 200 generations |
| P95 generation time | `metrics:p95_gen_ms` | 95th percentile — the "slow" trips |

---

### Panel 3: App Stats *(Right column)*

Live counts from PostgreSQL.

| Metric | Source | Description |
|---|---|---|
| Total users | `COUNT(user)` | All registered accounts |
| Total trips generated | `COUNT(trip)` | All saved itineraries |
| Total destinations in engine | `COUNT(destination)` | Available destinations |
| Pending destination requests | `COUNT(destination_request WHERE status='pending')` | Awaiting your approval |
| Trips generated today | `COUNT(trip WHERE created_at >= today)` | Today's activity |
| Signals recorded today | `COUNT(attraction_signal WHERE created_at >= today)` | User behaviour events |

---

### Panel 4: Pipeline Event Stream *(Full-width, live)*

Every itinerary generation appears here in real time as it happens. Powered by Server-Sent Events from `/api/ops/live-metrics`.

Each event shows:
- City name being planned
- Trip style (budget / mid / luxury)
- Number of days
- Generation time in milliseconds
- Which engine phases ran
- Whether result was served from cache or freshly generated

---

### Panel 5: Job Control Centre

Run any background job with one click. No terminal needed.

| Job Name | What It Does | Recommended Schedule | Button |
|---|---|---|---|
| OSM Data Fetch | Downloads attractions from OpenStreetMap for all destinations | Weekly / after adding a new city | ▶ Run Now |
| Enrich Attractions | Fetches images, descriptions, and Wikidata info for every attraction | After OSM fetch | ▶ Run Now |
| Score Attractions | Calculates popularity scores based on OSM data quality and user signals | Monthly | ▶ Run Now |
| Sync Prices | Updates hotel prices, flight routes, and activity costs | Daily (auto) / on demand | ▶ Run Now |
| Warm Cache | Pre-generates itineraries for the 7 most popular cities × 4 trip styles | Nightly (auto) / before launch | ▶ Run Now |
| Validate Destinations | AI reviews pending destination requests and auto-approves quality ones | Daily (auto) / after new requests | ▶ Run Now |
| Score Trip Quality | Reviews all saved trips and assigns quality scores | Daily (auto) | ▶ Run Now |
| Affiliate Health Check | Tests all booking affiliate links for broken URLs | Every 6 hours (auto) | ▶ Run Now |
| Update Behaviour Scores | Processes user interaction signals to update attraction popularity | Daily (auto) | ▶ Run Now |

---

### Panel 6: Job Run History

Shows the last run time and result for every background job.

- Job name and type (Celery task vs Agent)
- Last run timestamp in IST
- Status: `success` / `failed` / `running` / `never_run`
- Result summary (e.g. `"Warmed 28 itineraries"`, `"OSM: 142 attractions ingested for Jaipur"`)

---

### Panel 7: Destination Management

Full CRUD for destinations — no terminal needed.

- Browse all destinations with search and filter
- Edit any destination field inline (name, description, budget, rating, tags)
- Approve or reject pending destination requests with one click
- View attraction count per destination
- Manually trigger OSM ingestion for a specific city

---

### Panel 8: User & Trip Management

- User list with registration date and trip count
- Trip list with destination, budget, duration, style, and quality score
- View full itinerary JSON for any trip
- Delete trips if needed

---

### Panel 9: Affiliate Revenue Tracker

- Clicks today / this week / this month
- Estimated revenue (INR) by partner (MakeMyTrip, Booking.com)
- Breakdown by link type (flight, hotel, activity)
- Health status of each affiliate partner link

---

# Part 4 — Backend API Endpoints for Dashboard

| Method | Endpoint | Auth | Returns | Status |
|---|---|---|---|---|
| GET | `/health` | None | DB status, Redis status, Celery status | ⚠️ ADD NOW |
| GET | `/api/ops/summary` | Admin | All dashboard panel data in one call | ✅ EXISTS |
| GET | `/api/ops/live-metrics` | Admin | SSE stream of pipeline events | ✅ EXISTS |
| POST | `/api/ops/trigger-job` | Admin | Triggers a named Celery task | ⚠️ ADD NOW |
| GET | `/api/ops/job-status/:name` | Admin | Last run time, status, result for a job | ⚠️ ADD NOW |
| GET/POST | `/api/ops/engine-config` | Admin | Get/set engine tuning parameters | ⚠️ ADD NOW |
| POST | `/api/ops/trigger-osm/:city` | Admin | Trigger OSM ingestion for a specific city | ⚠️ ADD NOW |
| GET | `/api/admin/stats` | Admin | User/trip/destination counts | ✅ EXISTS |
| GET | `/api/admin/destinations` | Admin | Paginated destination list | ✅ EXISTS |
| PUT | `/api/admin/destinations/:id` | Admin | Update destination fields | ✅ EXISTS |
| DELETE | `/api/admin/destinations/:id` | Admin | Delete destination | ✅ EXISTS |
| GET | `/api/admin/requests` | Admin | Pending destination requests | ✅ EXISTS |
| POST | `/api/admin/requests/:id/approve` | Admin | Approve request | ✅ EXISTS |
| POST | `/api/admin/requests/:id/reject` | Admin | Reject request | ✅ EXISTS |
| GET | `/api/admin/users` | Admin | Paginated user list | ✅ EXISTS |
| GET | `/api/admin/trips` | Admin | Paginated trip list with quality score | ✅ EXISTS |
| GET | `/api/admin/affiliate-stats` | Admin | Clicks, revenue, breakdown | ✅ EXISTS |
| POST | `/api/admin/verify-key` | None | Validate admin key, return JWT | ✅ EXISTS |

---

## 4.1 New Endpoint — `POST /api/ops/trigger-job`

Add to `backend/routes/dashboard.py`:

```python
JOB_MAP = {
    "osm_ingestion":          "backend.celery_tasks.run_osm_ingestion",
    "enrichment":             "backend.celery_tasks.run_enrichment",
    "scoring":                "backend.celery_tasks.run_scoring",
    "price_sync":             "backend.celery_tasks.run_price_sync",
    "score_update":           "backend.celery_tasks.run_score_update",
    "destination_validation": "backend.celery_tasks.run_destination_validation",
    "cache_warm":             "backend.celery_tasks.run_cache_warm",
    "affiliate_health":       "backend.celery_tasks.run_affiliate_health",
    "quality_scoring":        "backend.celery_tasks.run_quality_scoring",
}

@dashboard_bp.route("/api/ops/trigger-job", methods=["POST"])
@require_admin
@limiter.limit("5 per minute")
def trigger_job():
    data = request.get_json() or {}
    job_name = data.get("job")
    if job_name not in JOB_MAP:
        return jsonify({
            "error": f"Unknown job: {job_name}",
            "valid_jobs": list(JOB_MAP)
        }), 400

    task_path = JOB_MAP[job_name]
    module_path, task_name = task_path.rsplit(".", 1)
    import importlib
    module = importlib.import_module(module_path)
    task = getattr(module, task_name)
    task.delay()  # fire async via Celery

    try:
        mark_status("job_trigger", job_name, "queued", {
            "triggered_at": datetime.utcnow().isoformat()
        })
    except Exception:
        pass

    return jsonify({
        "message": f"Job {job_name} has been queued.",
        "job": job_name
    }), 202
```

---

## 4.2 New Endpoint — `GET /api/ops/job-status/:job_name`

```python
@dashboard_bp.route("/api/ops/job-status/<job_name>", methods=["GET"])
@require_admin
def job_status(job_name):
    client = get_metrics_redis()
    if not client:
        return jsonify({"error": "Redis unavailable"}), 503
    return jsonify({
        "job": job_name,
        "last_run": get_metric(f"celery:{job_name}:last_run"),
        "status": get_metric(f"celery:{job_name}:last_status", default="never_run"),
        "result": _metric_json(f"celery:{job_name}:last_result"),
    }), 200
```

---

## 4.3 New Endpoint — `POST /api/ops/trigger-osm/:city`

```python
@dashboard_bp.route("/api/ops/trigger-osm/<city_name>", methods=["POST"])
@require_admin
@limiter.limit("3 per minute")
def trigger_osm_for_city(city_name):
    from backend.celery_tasks import run_osm_ingestion
    # Pass city name as override to the ingestion task
    run_osm_ingestion.apply_async(kwargs={"city_override": city_name})
    return jsonify({
        "message": f"OSM ingestion queued for city: {city_name}",
        "city": city_name
    }), 202
```

---

# Part 5 — Engine Control Panel

---

## 5.1 Engine Tuning Controls

| Setting Name | Current Value Source | Control Type | Effect on Engine |
|---|---|---|---|
| Popularity Score Floor | Engine constant (25) | Number slider 0–100 | FilterEngine filters out attractions below this score. Lower = more results but lower quality. |
| Max Activities Per Day | Engine constant (6) | Number input 3–10 | ClusterEngine caps each day at this number. 5 is comfortable for most travelers. |
| Seasonal Score Gate | Engine constant (40) | Number slider 0–100 | FilterEngine skips attractions scoring below this for the travel month. |
| Budget Validation Strict Mode | Env: `VALIDATION_STRICT` | Toggle ON/OFF | When ON, itineraries over budget are auto-scaled to fit. |
| Gemini Polish Enabled | Redis: `gemini:polish:enabled` | Toggle ON/OFF | When OFF, the deterministic engine output is returned directly without Gemini text polish. Faster but less polished descriptions. |
| Cache TTL — Full Trip (hours) | Redis config (72h default) | Number input 1–168 | How long a cached itinerary is reused before regenerating. |
| Cache TTL — Gemini Polish (days) | Redis config (30d default) | Number input 1–90 | Gemini polish results are expensive. 30 days is appropriate. |
| Max Destinations in Prompt | Code constant (3) | Number input 1–10 | How many destination records are injected into the Gemini prompt. |
| Traveler Type Matching | FilterEngine logic | Toggle strict/relaxed | Strict: only attractions matching the exact traveler type. Relaxed: includes attractions with no type restriction. |

---

## 5.2 New Endpoint — `GET/POST /api/ops/engine-config`

```python
REDIS_ENGINE_KEYS = {
    "popularity_floor":       ("engine:config:popularity_floor", int),
    "max_activities_per_day": ("engine:config:max_activities_per_day", int),
    "seasonal_gate":          ("engine:config:seasonal_gate", int),
    "validation_strict":      ("engine:config:validation_strict", str),
    "gemini_polish_enabled":  ("engine:config:gemini_polish", str),
    "cache_ttl_trip_hours":   ("engine:config:cache_ttl_trip", int),
}

@dashboard_bp.route("/api/ops/engine-config", methods=["GET", "POST"])
@require_admin
def engine_config():
    client = get_metrics_redis()
    if request.method == "GET":
        config = {}
        for key, (redis_key, cast) in REDIS_ENGINE_KEYS.items():
            val = client.get(redis_key) if client else None
            config[key] = cast(val) if val else None
        return jsonify(config), 200
    data = request.get_json() or {}
    updated = {}
    for key, value in data.items():
        if key in REDIS_ENGINE_KEYS:
            redis_key, _ = REDIS_ENGINE_KEYS[key]
            client.set(redis_key, str(value))
            updated[key] = value
    return jsonify({"updated": updated}), 200
```

### Make FilterEngine read config from Redis

```python
# In filter_engine.py — read tuning params from Redis at runtime
import redis, os

def _get_config(key: str, default: int) -> int:
    try:
        r = redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379"))
        val = r.get(f"engine:config:{key}")
        return int(val) if val else default
    except Exception:
        return default

# Use these instead of hardcoded constants:
POPULARITY_FLOOR    = lambda: _get_config("popularity_floor", 25)
MAX_ACTIVITIES      = lambda: _get_config("max_activities_per_day", 6)
SEASONAL_GATE       = lambda: _get_config("seasonal_gate", 40)
```

---

# Part 6 — Real-Time Data Strategy

> Every number on the dashboard is real. This section specifies exactly where each metric comes from and how to ensure it is being recorded correctly.

---

## 6.1 Metrics Currently Being Written *(Already Working)*

| Redis Key | Written By | When |
|---|---|---|
| `gemini:calls:today` | `GeminiService` | After each API call |
| `gemini:errors:today` | `GeminiService` | On API failure |
| `cache:hits:today` | `CacheService` | On cache hit |
| `cache:misses:today` | `CacheService` | On cache miss |
| `pipeline:metrics` (stream) | `orchestrator.py` | After each generation |
| `celery:{task}:last_run` | `_run_and_record()` | After task completes |
| `celery:{task}:last_status` | `_run_and_record()` | After task completes |
| `agent:{agent}:last_run` | `mark_status()` | After agent runs |
| `agent:{agent}:last_status` | `mark_status()` | After agent runs |

---

## 6.2 Metrics That Need to Be Added

| Metric | Problem | Fix |
|---|---|---|
| `metrics:avg_gen_ms` | Set but calculated over all time, not rolling 24h | Store last 200 times in Redis list; calculate avg on read |
| `metrics:p95_gen_ms` | Not currently written anywhere | Store sorted times; calculate p95 on read |
| `gemini:tokens:today` | `GeminiService` does not count tokens | Parse `usageMetadata.totalTokenCount` from Gemini response |
| `celery:worker:last_seen` | Workers don't ping Redis | Add `@task_postrun_handler` that writes the timestamp |

---

## 6.3 Add Token Counting to GeminiService

```python
# In gemini_service.py — after successful API call
response_data = resp.json()

usage = response_data.get("usageMetadata", {})
total_tokens = usage.get("totalTokenCount", 0)
if total_tokens > 0:
    try:
        r = redis.from_url(os.getenv("REDIS_URL"))
        r.incrby("gemini:tokens:today", total_tokens)
        r.expire("gemini:tokens:today", 86400)
    except Exception:
        pass  # metrics failure never kills generation
```

---

## 6.4 Add Rolling Average for Generation Time

```python
# In metrics_service.py — add this function
def record_generation_time(ms: int):
    """Store last 200 gen times; update rolling average."""
    try:
        r = _get_redis()
        r.lpush("metrics:gen_times", ms)
        r.ltrim("metrics:gen_times", 0, 199)   # keep last 200
        times = [int(t) for t in r.lrange("metrics:gen_times", 0, -1)]
        avg = sum(times) // len(times)
        sorted_times = sorted(times)
        p95_idx = int(len(sorted_times) * 0.95)
        p95 = sorted_times[min(p95_idx, len(sorted_times) - 1)]
        r.set("metrics:avg_gen_ms", avg)
        r.set("metrics:p95_gen_ms", p95)
    except Exception:
        pass
```

Call this in `orchestrator.py` at the end of `generate()`:

```python
from backend.services.metrics_service import record_generation_time
total_ms = int((time.monotonic() - started) * 1000)
try:
    record_generation_time(total_ms)
except Exception:
    pass
```

---

## 6.5 Add Celery Worker Heartbeat

```python
# In celery_config.py — add task signal handler
from celery.signals import task_postrun
import redis, os, time

@task_postrun.connect
def record_worker_heartbeat(sender=None, **kwargs):
    try:
        r = redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379"))
        r.set("celery:worker:last_seen", int(time.time()))
        r.expire("celery:worker:last_seen", 600)  # 10 min TTL
    except Exception:
        pass
```

---

## 6.6 Dashboard Auto-Refresh Strategy

| Data Type | Method | Interval |
|---|---|---|
| Summary data (counts, totals, job statuses) | Polling `GET /api/ops/summary` | Every 30 seconds |
| Live pipeline events | SSE stream `GET /api/ops/live-metrics` | Real-time (persistent connection) |
| Job run status (while a job is running) | Polling `GET /api/ops/job-status/:name` | Every 5 seconds until complete, then 30s |
| Engine config | On demand (user opens panel) | Manual refresh button |

---

# Part 7 — Implementation Roadmap

| Phase | Tasks | Priority |
|---|---|---|
| **Day 1** | Fix 1: Replace DummyDBWrapper with Flask-SQLAlchemy | 🔴 CRITICAL |
| | Fix 2: Remove hardcoded database credentials | |
| | Fix 3: Move rate limiter to Redis storage | |
| | Fix 4: Add rate limit to `/api/admin/verify-key` | |
| | Fix 7: Add `/health` endpoint (DB + Redis check) | |
| | Add `.dockerignore` file | |
| **Day 2** | Fix 5: Wire GeminiService class in `trips.py`; delete module-level function | 🔴 CRITICAL |
| | Fix 6: Wire `VALIDATION_STRICT` to `ItineraryValidator` | |
| | Fix 8: Add JWT refresh endpoint; shorten access token to 1 hour | |
| | Fix 9: Guard null `h3_index_r7` in ClusterEngine | |
| | Fix 10: Fix `traveler_type` JSON deserialisation in FilterEngine | |
| | Fix 11: Merge `smart_insights` and `packing_tips` from Gemini polish | |
| **Day 3** | Fix 12: Guard `HotelPrice`/`FlightRoute` queries in `orchestrator.py` | 🟠 HIGH |
| | Fix 13: Add password length and duration range validation to `schemas.py` | |
| | Fix 14: Wrap all `mark_status()` calls in `try/except` in `orchestrator.py` | |
| | Fix 15: Update `.env.example` with valid placeholder values | |
| | Fix 16: Lower `detect_theme` threshold to 1 in `assembler.py` | |
| | Add `celery-redbeat` for Celery Beat HA | |
| **Day 4** | Add `POST /api/ops/trigger-job` endpoint with `JOB_MAP` | 🟠 HIGH |
| | Add `GET /api/ops/job-status/:name` endpoint | |
| | Add `GET/POST /api/ops/engine-config` endpoint | |
| | Add rolling average metrics (`record_generation_time()`) | |
| | Add token counting to GeminiService | |
| | Add Celery worker heartbeat signal | |
| | Add `gunicorn.conf.py` with gevent workers | |
| **Week 2** | Build full Mission Control dashboard React frontend (all 9 panels) | 🟡 MEDIUM |
| | Wire all "Run Now" buttons to `/api/ops/trigger-job` | |
| | Wire Engine Config panel to `/api/ops/engine-config` | |
| | Set up GitHub Actions CI pipeline | |
| | Run OSM ingestion for top 10 cities; verify attractions are stored | |
| **Week 3** | Run full data pipeline: OSM → Enrich → Score → Warm Cache | 🟡 MEDIUM |
| | Add `POST /api/ops/trigger-osm/:city` for per-city OSM control | |
| | Add trip quality scoring display in Trip Management panel | |
| | Test all Celery tasks end-to-end with real Redis/Postgres | |
| | Smoke test itinerary generation with real data | |
| **Week 4** | Production deployment to Railway (backend) + Vercel (frontend) | 🔵 LOW |
| | Set up staging environment that mirrors production | |
| | Final security review: no `.env` in Docker image, no hardcoded secrets | |
| | Load test: simulate 10 concurrent itinerary generations | |
| | Document all environment variables and deployment steps | |

---

# Part 8 — Production Deployment Checklist

Run through every item before going live. All items must be checked.

---

## 8.1 Security Checklist

- [ ] `DATABASE_URL` contains a strong password, not `altairgo_dev_pass`
- [ ] `JWT_SECRET_KEY` is 64+ character random hex (`python -c "import secrets; print(secrets.token_hex(32))"`)
- [ ] `ADMIN_ACCESS_KEY` is a strong random string, not `change-me-in-dev`
- [ ] `GEMINI_API_KEY` is set from Google AI Studio
- [ ] `ALLOWED_ORIGINS` is set to your exact production domain (not `*`)
- [ ] `.env` file is NOT in the Docker image (`docker run cat /.env` should fail)
- [ ] Rate limiter is using Redis, not memory (`REDIS_URL` is set)
- [ ] `/api/admin/*` endpoints reject requests without `X-Admin-Key` header
- [ ] `/health` endpoint returns `200` and `{"status": "ok"}`

---

## 8.2 Database Checklist

- [ ] Run: `flask db upgrade` — all migrations applied successfully
- [ ] `SELECT COUNT(*) FROM destination` returns > 0
- [ ] `SELECT COUNT(*) FROM attraction` returns > 0 (OSM ingestion ran)
- [ ] `SELECT COUNT(*) FROM attraction WHERE h3_index_r7 IS NOT NULL` — majority should have valid h3
- [ ] `HotelPrice` table exists (even if empty — the query guard handles empty)
- [ ] `FlightRoute` table exists (even if empty)

---

## 8.3 Celery Checklist

- [ ] Celery worker is running: `celery -A backend.celery_config:celery_app worker`
- [ ] Celery beat is running: `celery -A backend.celery_config:celery_app beat`
- [ ] Redis is accessible from Celery workers (same `REDIS_URL`)
- [ ] Trigger one manual job from dashboard to confirm end-to-end (trigger `price_sync`)
- [ ] After 5 minutes, job status shows `success` not `never_run`

---

## 8.4 Engine Checklist

- [ ] Generate a test itinerary for Jaipur, 3 days, budget style — should return `200` with full itinerary
- [ ] Verify `smart_insights` array is **NOT empty** in the response
- [ ] Verify `packing_tips` array is **NOT empty** in the response
- [ ] Set `VALIDATION_STRICT=true` and test with a budget lower than expected cost — verify auto-scaling activates
- [ ] Run cache warm job — check Redis has keys matching `trip:cache:*`
- [ ] Second generation for same parameters should be significantly faster (cache hit)

---

## 8.5 Dashboard Checklist

- [ ] Login with admin key succeeds and returns JWT token
- [ ] Summary panel shows real counts (not zeros or errors)
- [ ] SSE live-metrics stream connects and shows heartbeat events
- [ ] Trigger OSM ingestion job — button shows queued, then status updates to success
- [ ] Job history shows last run time for at least one job
- [ ] Destination management loads and allows editing
- [ ] Affiliate stats panel shows click data (even if 0 clicks — should not error)

---

# Final Assessment

> **Risk Score: 5 / 10** — Do not ship in current state. Ship after Day 1–2 fixes are complete.
>
> **Effort to fix all blockers: 3–4 focused developer-days.**
>
> **Architecture quality: GOOD** — Deterministic engine + Gemini polish is the right design. The structured logging, Marshmallow validation, timing-safe admin auth, and test suite design all show senior engineering judgement.
>
> **Code quality: MIXED** — Senior-quality patterns in auth/logging/validation; junior-level integration gaps in the wiring between components.
>
> The foundation is worth building on. The blockers are fixable, not architectural. After fixing all 16 items in this document, the project is ready for investor preview.

---

### Top 5 Priorities (in order)

1. **Replace DummyDBWrapper → Flask-SQLAlchemy** — breaks migrations, guarantees data integrity problems in production
2. **Add `/health` endpoint** — production container will restart-loop within minutes without it
3. **Move rate limiter to Redis** — Gemini quota abuse is trivially possible with `memory://` and Gunicorn workers
4. **Wire GeminiService class in `trips.py`** — you are running the wrong model with no retries in production
5. **Merge `smart_insights` from Gemini polish** — the flagship feature shows blank panels to every single user right now

---

*AltairGO Intelligence — Confidential Technical Document | March 2026*
