# CLAUDE.md

> Technical reference for Claude Code. Read before making changes.

---

## Commands

```bash
python -m pytest backend/tests/ -q --tb=short          # all tests
python -m pytest backend/tests/ -k "test_generate" -q  # filter by name
.venv/Scripts/python.exe -m flask --app backend.app:create_app run --port 5000 --reload
cd "D:/Projects/AltairGO-Platform" && npm run dev
docker compose up -d redis   # Redis only
docker compose up            # all services
```

---

## 1. Project Purpose

**AltairGO Travel Intelligence** — India-first AI travel platform. Generates AI-powered day-by-day itineraries with real cost breakdowns, automates hotel/flight/activity bookings, and provides day-of intelligence (weather alerts, crowd warnings, local events).

**Stack:** Python Flask + Celery + SQLAlchemy (PostgreSQL/Supabase) + Redis + Gemini 2.0 Flash + Ollama (fallback) + React 19 (Vite) + Tailwind CSS v4

**DB:** Supabase PostgreSQL (project `amdtitsokkounoscgova`, ap-southeast-2)

**Migrations:** Supabase MCP `apply_migration` with targeted DDL only. **Never** `flask db upgrade` in prod — autogenerate drops PostGIS tables.

---

## 2. Key Directories

```
backend/
  app.py              # Flask factory + all blueprints
  models.py           # 30+ SQLAlchemy models
  engine/             # orchestrator, filter_engine, cluster_engine, budget_allocator,
                      # route_optimizer, assembler
  routes/             # trips, auth, admin, bookings, expenses, discover, trip_tools,
                      # trip_editor, profile, sharing, search, feedback, blogs, ops, dashboard
  services/           # gemini_service, cache_service, booking_providers/, feature_flags
  agents/             # destination_validator, itinerary_qa, memory_agent, mcp_context
  tasks/              # score_updater, weather_sync, quality_scorer, embedding_sync
frontend: D:\Projects\AltairGO-Platform  (React 19, Vite 7, Tailwind v4)
```

---

## 3. Environment Variables

```bash
# Required
DATABASE_URL        # Direct Supabase: postgresql://postgres:***@db.amdtitsokkounoscgova.supabase.co:5432/postgres
                    # NOT pooler URL — causes "Tenant not found"
REDIS_URL           # Celery broker + rate limiting + metrics + share cache
JWT_SECRET_KEY      # Min 32 chars
ADMIN_ACCESS_KEY
GEMINI_API_KEY

# Optional
GEMINI_MODEL             # default: gemini-2.0-flash
OLLAMA_URL               # default: http://localhost:11434
OLLAMA_MODEL             # default: llama3.2:3b
BOOKINGCOM_AFFILIATE_ID  # enables real hotel links; falls back to SimulatedProvider if unset
ALLOWED_ORIGINS          # default: https://altairgo.in,http://localhost:5173
THEME_THRESHOLD          # default: 0.20

# Local dev
DEV_EAGER=true      # task_always_eager + SQLite broker — no Celery worker needed
TESTING=true        # DEV_EAGER + SQLite in-memory DB
```

---

## 4. Flask App Factory (`backend/app.py`)

Blueprint registration order (first wins on duplicate routes):
`trips → admin → auth → destinations → dashboard` ← **authoritative for `/api/ops/summary`** `→ signals → ops → bookings → expenses → discover → trip_tools → trip_editor → profile → sharing → search → feedback → webhooks → blogs`

---

## 5. Database Layer

- `db.session` in routes; `SessionLocal()` in Celery workers
- `pool_pre_ping=True`, `pool_recycle=300` — restart Flask after live migrations to flush stale connections
- **Always verify schema before coding:** `SELECT column_name, data_type FROM information_schema.columns WHERE table_name='...'` — models and DB have drifted before

---

## 6. Key Models (`backend/models.py`)

| Model | Notes |
|-------|-------|
| `User` | email/password_hash |
| `UserProfile` | preferences (JSON), embedding |
| `Destination` | 40+ fields; `state_id` FK — manual join (no ORM relationship); 179/186 NULL popularity_score |
| `Attraction` | 11,539 rows; seasonal_score via PL/pgSQL; has opening_hours, closed_days, accessibility_level, dietary_options, min_age |
| `HotelPrice` | 562 rows (186 destinations × 3 tiers); `category` must be "budget"/"mid"/"luxury" |
| `FlightRoute` | 86 rows seeded |
| `Trip` | itinerary_json (JSON); `user_notes["_share_token"]` for sharing; `is_customized` flag |
| `AsyncJob` | status: queued/processing/completed/failed |
| `Booking` | full lifecycle; status + user_approved + booking_ref + partner_name |
| `WeatherAlert` | alert_date VARCHAR(10); 89 active alerts; nightly sync |
| `DestinationInfo` | 29 rows seeded; injected as `pre_trip_info` in every itinerary |
| `LocalEvent` | 23 events; start_date/end_date are DATE type → returns `datetime.date` (not string) |
| `ExpenseEntry` | planned vs actual budget tracking |
| `EngineSetting` | 10 keys; runtime config without redeploy |
| `FeatureFlag` | flag_key, is_active, traffic_pct (60s DB cache) |
| `Feedback` | corrections `{"tags": [...]}` — accepts hyphenated tags (great-value, well-paced, etc.) |

**Known mismatch:** `LocalEvent.start_date/end_date` — model `String(10)`, DB `DATE` → always serialize with `.isoformat()`.

---

## 7. Itinerary Generation Pipeline

### Flow
```
POST /generate-itinerary → validate → cache check → AsyncJob(queued) → Celery task [202]
GET  /get-itinerary-status/<job_id>         → poll status
GET  /get-itinerary-status/<job_id>/stream  → SSE (Redis stream → DB poll fallback)
```
`DEV_EAGER=true` → runs synchronously (~17s), no worker needed.

### base_date computation (orchestrator.py)
No `start_date` → uses `travel_month` (10th day default) or first day of current month. Drives POIClosure filtering, LocalEvent window, WeatherAlert lookups.

### 5-Step Pipeline
1. **FilterEngine** — Popularity ≥25, seasonal gate (≥40 default 70), traveler compat, budget cap, accessibility/dietary/children/senior/min_age
2. **ClusterEngine** — H3 r7 hex grouping (~5km), NULL GPS guard (`0.0,0.0` = missing), theme diversity
3. **BudgetAllocator** — Tier auto-demotion (<2000/<1000 INR/person/day), real hotel costs from HotelPrice, group discounts (5-9: 10%, 10+: 15%)
4. **RouteOptimizer** — 15 km/h, sunrise priority, W→E ordering, queue_time_minutes added
5. **Assembler** — Day themes (20% overlap threshold), document_checklist, daily_transport_guide

### Post-Assembly
- **Gemini polish chain:** `gemini-2.0-flash` → (429) `flash-lite` → (429) `Ollama llama3.2:3b` → graceful unpolished fallback (trip_title = "Trip to X")
- **Enrichment:** DestinationInfo → `pre_trip_info`; LocalEvent (by trip window) → `local_events`; WeatherAlert (high/extreme) → per-day `weather_alert`

### Itinerary JSON shape
```json
{
  "trip_title", "total_cost", "cost_breakdown",
  "itinerary": [{"day","location","theme","pacing_level","activities","accommodation","day_total"}],
  "smart_insights", "packing_tips", "travel_between_cities",
  "document_checklist", "daily_transport_guide",
  "pre_trip_info", "local_events", "weather_alerts", "traveler_profile"
}
```

---

## 8. Authentication

- **JWT:** Access 1hr / Refresh 30d
- **Tokens:** `ag_token` + `ag_refresh_token` (traveler), `ag_admin_token` (admin) in localStorage
- **Admin:** `X-Admin-Key` header OR JWT `role="admin"`. Token via `POST /api/admin/verify-key`
- **Lockout:** Redis `login:fail:<email>` — 5 failures → 429 for 15min (`_LOCKOUT_WINDOW=900`). Degrades silently if Redis down.
- **Expired token:** `ag:unauthorized` CustomEvent → AuthContext auto-logout

---

## 9. Celery Beat Schedule

| Task | Schedule | Purpose |
|------|----------|---------|
| `run_weather_sync` | Daily 05:30 | Open-Meteo → WeatherAlert |
| `run_score_update` | Daily 02:00 | Popularity + quality scores |
| `run_quality_scoring` | Daily 04:30 | Trip quality scoring |
| `run_price_sync` | Daily 06:00 & 18:00 | Hotel/flight pricing |
| `run_cache_warm` | Daily 03:30 | Pre-warm Redis |
| `run_post_trip_summaries` | Daily | Post-trip summaries |
| `run_destination_validation` | Daily 01:00 | AI validate destination requests |
| `run_affiliate_health` | Every 6h | Partner API health |
| `run_osm_ingestion` | Sunday 03:00 | POIs from Overpass API |
| `run_embedding_sync` | Weekly | Destination embeddings |
| `heartbeat` | Every 5min | Worker health |

---

## 10. Frontend (`D:\Projects\AltairGO-Platform`)

**Stack:** React 19, Vite 7, Tailwind v4, React Router v7, Framer Motion, Recharts
**Proxy:** `/api/*`, `/auth/*`, `/generate-*`, `/get-trip`, `/get-itinerary-status`, `/countries`, `/destinations`, `/blogs` → `http://127.0.0.1:5000`

**Generation flow (GeneratingPage.jsx):** `POST /generate-itinerary` → SSE stream → on `completed`: `saveTrip()` → redirect `/trip/:id`. Polls every 2s if SSE fails.

**Review tags:** Frontend sends hyphenated (`great-value`, `well-paced`, `hidden-gems`, `family-friendly`, `romantic`, `adventure`, `foodie`, `budget-friendly`). Backend `_VALID_TAGS` accepts both hyphenated and underscore formats.

**Design:** Primary `#4F46E5`, Accent `#F59E0B`, Background `#F8FAFC`. Currency: `₹{n.toLocaleString('en-IN')}`.

---

## 11. Critical Business Logic

**Schema gotchas:**
- `selected_destinations` → `[{"name": "Jaipur"}]` not `["Jaipur"]`
- `travel_month` → `"12"` (string) not `12`

**Activity proxy** (trip_tools.py, trip_editor.py): RouteOptimizer expects SQLAlchemy objects; wrap plain dicts:
```python
type("_Proxy", (), {"attr": value, ...})()
```

**Safe itinerary mutation:**
```python
itinerary = copy.deepcopy(trip.itinerary_json or {})
# modify...
trip.itinerary_json = itinerary
trip.is_customized = 1
db.session.commit()
```

**LocalEvent date serialization:** DB returns `datetime.date` — always serialize before JSON:
```python
def _date_str(v):
    return v.isoformat() if hasattr(v, "isoformat") else (v or None)
```

**Budget auto-demotion:**
```python
daily_per_person = total_budget / (num_days * travelers)
if tier == 'luxury' and daily_per_person < 2000: tier = 'mid'
if tier == 'mid'    and daily_per_person < 1000: tier = 'budget'
```

**Booking provider:** All execution via `get_provider(booking_type).execute(booking)` (services/booking_providers/registry.py). Default: `SimulatedProvider` (`simulated=True`). Real Booking.com needs `BOOKINGCOM_AFFILIATE_ID`.

**Sharing:** Token in `trip.user_notes["_share_token"]`; Redis `share:<token>` → trip_id (30d TTL); falls back to DB scan when Redis cold.

**Booking execute-all:** Only `status="approved"` — naturally excludes `self_arranged`.

**H3 guards:** Missing `h3_index_r7` → compute from lat/lng; `(0.0, 0.0)` treated as missing GPS.

**Cache key:** SHA-256 of: origin_city, destinations (sorted), budget, duration, travelers, style, traveler_type, travel_month, start_date, date_type, use_engine, dietary, accessibility, children, interests.

---

## 12. Tests

```bash
python -m pytest backend/tests/ -q --tb=short  # 188 passed, 1 skipped
```
Config: `TESTING=true` → SQLite in-memory DB + memory:// rate limiter; `RATELIMIT_ENABLED=False`.

---

## 13. Local Dev

```bash
docker compose up -d redis
ollama serve   # optional: needs `ollama pull llama3.2:3b` first
.venv/Scripts/python.exe -m flask --app backend.app:create_app run --port 5000 --reload
cd "D:/Projects/AltairGO-Platform" && npm run dev
# Frontend: http://localhost:5173  |  API health: http://127.0.0.1:5000/health
```

---

## 14. Production Deployment

- **Docker services:** `redis`, `app` (Gunicorn :5000), `worker` (`--pool=solo`), `beat` (RedBeatScheduler)
- **DB:** Direct connection only — pooler URL → "Tenant not found"
- **Migrations:** `mcp__claude_ai_Supabase__apply_migration` with targeted DDL; never `flask db upgrade`
- **Frontend:** `npm run build` → `dist/` → nginx/CDN

---

## 15. Architecture Patterns

1. **Async-first** — Celery runs pipeline; HTTP returns job_id immediately (DEV_EAGER = synchronous)
2. **SSE real-time** — `/stream` pushes result on completion; Redis stream → DB poll fallback
3. **Cache-first** — SHA-256 Redis cache, 7-day TTL
4. **Graceful degradation** — Gemini → Ollama → unpolished; Redis down → rate limiting disabled
5. **Dual session** — `db.session` in routes / `SessionLocal()` in Celery workers
6. **Activity proxy** — dict-to-model shim for RouteOptimizer re-optimization after edits
7. **Safe mutation** — `deepcopy` itinerary JSON before edits, reassign whole field
8. **Blueprint order** — `dashboard_bp` before `ops_bp` wins `/api/ops/summary`
9. **Supabase MCP only** for DDL — avoids PostGIS autogenerate conflicts

---

## 16. Status & Remaining Work

**Production-ready as of 2026-04-06:**
- All 190 destinations have `popularity_score` (min 5, max 95, avg 58) — scored by attraction count + rating + richness
- Embeddings: `vector(384)` on destination/attraction/user_profiles — uses local `all-MiniLM-L6-v2` via sentence-transformers (no API key)
- Blog posts: 23 posts seeded across 8 categories (Budget, Monsoon, Offbeat, Food, Family, Adventure, Luxury, Solo)
- Docker: healthchecks on all 5 services, resource limits, Gunicorn preload + max_requests jitter

**Remaining limitations:**
- Free-tier Gemini → 429 → unpolished fallback (fix: paid API key or Ollama)
- Embeddings not yet generated for existing destinations (run `make embeddings` or trigger `embedding_sync` Celery task)

**Embedding model:** `all-MiniLM-L6-v2` (384-dim, normalized cosine, local inference, no API key)
- Run once: `make embeddings` or `python -m backend.scripts.generate_embeddings`
- Nightly: Celery beat `run_embedding_sync` task handles incremental updates
