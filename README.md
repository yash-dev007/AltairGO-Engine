<div align="center">

<img src="https://img.shields.io/badge/AltairGO-Engine-22c55e?style=for-the-badge&logo=airplane&logoColor=white" alt="AltairGO Engine" />

# AltairGO Engine

**India-first AI travel intelligence backend. Deterministic 5-step itinerary pipeline, full booking automation, and day-of intelligence — powered by Flask + Celery + Gemini 2.0 Flash.**

[![Python 3.10+](https://img.shields.io/badge/Python-3.10+-3776AB?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![Flask 3.x](https://img.shields.io/badge/Flask-3.x-000000?style=flat-square&logo=flask&logoColor=white)](https://flask.palletsprojects.com)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-Supabase-336791?style=flat-square&logo=postgresql&logoColor=white)](https://supabase.com)
[![Redis](https://img.shields.io/badge/Redis-7-DC382D?style=flat-square&logo=redis&logoColor=white)](https://redis.io)
[![Celery](https://img.shields.io/badge/Celery-5-37814A?style=flat-square&logo=celery&logoColor=white)](https://docs.celeryq.dev)
[![Gemini 2.0](https://img.shields.io/badge/Gemini-2.0%20Flash-4285F4?style=flat-square&logo=google&logoColor=white)](https://deepmind.google/technologies/gemini/)
[![Tests](https://img.shields.io/badge/Tests-188%20passed-22c55e?style=flat-square)](backend/tests/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green?style=flat-square)](LICENSE)

<br/>

[Quick Start](#-quick-start) &bull; [Architecture](#-architecture) &bull; [API Reference](#-api-reference) &bull; [Features](#-traveler-features) &bull; [Deployment](#-deployment)

</div>

---

## Overview

AltairGO Engine is the **backend-only** core of the AltairGO travel intelligence platform. It exposes a REST API that powers the full travel lifecycle — from "where should I go?" discovery through to one-click booking and day-of briefings.

The frontend lives in a separate repository: [AltairGO-Platform](https://github.com/yash-dev007/AltairGO-Platform).

### Key Features

| Feature | Details |
|---|---|
| **Deterministic pipeline** | Filter → Cluster → Budget → Route → Assemble. AI adds polish, not structure |
| **48 traveler improvements** | Senior pacing, children filters, dietary restrictions, queue buffers, group discounts, weather alerts, and more |
| **Full booking automation** | One-click hotel, flight, activity, restaurant, airport transfer, and daily cab bookings |
| **Day-of intelligence** | Daily briefing: what to carry, weather alerts, crowd warnings, confirmed bookings, emergency contacts |
| **Geospatial clustering** | H3 hexagonal cells for grouping attractions into walkable day plans |
| **Free image sources** | Wikipedia → Wikidata → Pexels — no Google Places API required |
| **188 passing tests** | Auth, API contracts, engine, pipeline, validation — all on SQLite in-memory |

---

## Architecture

```
+-------------------------------------------------------------------+
|                        REST API Clients                            |
|         (AltairGO-Platform frontend or any HTTP client)           |
+-----------------------------------+-------------------------------+
                                    | REST + SSE
+-----------------------------------v-------------------------------+
|                    Flask API (15 Blueprints)                       |
|  auth | trips | destinations | bookings | expenses | discover      |
|  trip_tools | trip_editor | profile | sharing | search | admin     |
|  ops | dashboard | signals                                         |
+---------------+-------------------------------+-------------------+
                |                               |
+---------------v---------------+  +-----------v-------------------+
|     Itinerary Pipeline        |  |      Service Layer             |
|                               |  |                                |
|  1. FilterEngine              |  |  GeminiService (polish)        |
|  2. ClusterEngine (H3)        |  |  CacheService (Redis, SHA-256) |
|  3. BudgetAllocator           |  |  MetricsService (SSE)          |
|  4. RouteOptimizer            |  |  ImageService (Wikipedia →     |
|  5. Assembler                 |  |    Wikidata → Pexels)          |
+---------------+---------------+  +-----------+-------------------+
                |                               |
+---------------v-------------------------------v-------------------+
|               Data & Infrastructure Layer                          |
|  PostgreSQL (Supabase) + PostGIS | Redis | Celery Beat + Worker    |
+-------------------------------------------------------------------+
```

### The 5-Step Itinerary Pipeline

```
POST /generate-itinerary
  → validate schema → SHA-256 cache check → create AsyncJob → Celery task

[1. FilterEngine]
  Popularity ≥25, traveler compatibility, seasonal gate (≥40, default 70),
  budget cap, category max 2, accessibility, children, dietary, senior, min_age,
  POI closures, repeat-traveler dedup

[2. ClusterEngine]
  H3 r7 hex grouping (~5km radius), NULL GPS guard,
  theme diversity across days, top N hexes for N days

[3. BudgetAllocator]
  Tier splits (budget/mid/luxury), auto-demotion (<₹2000/₹1000 per person/day),
  real hotel cost from HotelPrice table, group discounts (5-9: 10%, 10+: 15%)

[4. RouteOptimizer]
  15 km/h urban pacing, sunrise priority, W→E ordering,
  queue_time_minutes buffered, enriched output (difficulty, photo tips, dress code)

[5. Assembler]
  Day themes, document_checklist, daily_transport_guide, pre_trip_info, local_events

[GeminiService]
  polish_itinerary_text() + meta (trip_title, smart_insights, packing_tips)
  Fallback: gemini-2.0-flash-lite, 3 retries, 15s timeout
  Gracefully degrades to unpolished itinerary on failure
```

### Background Jobs (Celery Beat)

| Job | Schedule | Purpose |
|---|---|---|
| Destination validation | Daily 01:00 | AI-validates destination data quality |
| Score update | Daily 02:00 | Popularity + quality score blending |
| OSM ingestion | Sunday 03:00 | Fetch new POIs from Overpass API |
| Cache warming | Daily 03:30 | Pre-warm Redis for top destinations |
| Attraction enrichment | Monday 04:00 | Wikidata + Wikipedia enrichment |
| Trip quality scoring | Daily 04:30 | Score saved trips for quality metrics |
| Attraction scoring | 1st of month 05:00 | Monthly popularity recalculation |
| Weather sync | Daily 05:30 | Open-Meteo → WeatherAlert rows |
| Price sync | Daily 06:00 + 18:00 | Hotel + flight pricing refresh |
| Affiliate health | Every 6h | Partner API health checks |
| Worker heartbeat | Every 5min | Worker availability |

---

## Traveler Features

48 improvements across the full travel lifecycle:

### Filtering
- Dietary restrictions (veg/vegan/halal — filters non-compatible attractions)
- Accessibility filtering (level 3 excluded when `accessibility=1`)
- Children-friendly filter (skips non-family attractions)
- Senior pacing (max 3-4 activities/day; strenuous filtered)
- Min-age filtering per attraction
- POI closure filtering (removes attractions closed during travel window)
- Repeat-traveler dedup (skips already-visited attractions from last 10 trips)

### Budget
- Budget auto-demotion (luxury → mid if <₹2000/person/day; mid → budget if <₹1000)
- Real hotel costs from `HotelPrice` table
- Group discounts (5-9 travelers: 10%; 10+: 15%)
- Multi-currency display via `CurrencyRate` table
- Budget estimator endpoint before committing to generation

### Itinerary Output
- Day-type scheduling (arrival: 3pm start, departure: end by noon)
- Queue time buffers added to realistic scheduling
- Activity enrichment in output (difficulty, is_photo_spot, photo tip, dress_code, guide_available, queue wait)
- Document checklist (personalised by children/seniors/international trip)
- Daily transport guide (per-day cab mode + cost estimate)
- Pre-trip info block (visa, safety advisory, vaccinations, water safety, emergency contacts, tipping)
- Local events injection (festivals, holidays — avoid-impact events as warnings)
- Weather alerts (Open-Meteo sync; rainy day alternatives promoted on high/extreme alerts)

### Trip Lifecycle
- Full booking automation (hotel, outbound+return flights, airport transfers, activity tickets, restaurant reservations, daily cabs)
- Batch execute-all approved bookings
- Booking cancellation and self-arranged booking support
- Expense tracker (planned vs actual per category)
- Trip readiness check (0-100% score + checklist)
- Daily briefing (what to carry, dress code, weather alerts, crowd warnings, confirmed bookings)
- Activity swap (replace any activity, re-runs RouteOptimizer)
- Full trip editor (hotel swap, add/remove/edit/reorder activities, per-day notes)
- Trip sharing (public share link with 30-day Redis TTL)
- Next-trip ideas (post-trip recommendations based on activity types enjoyed)
- Trip variants (relaxed/balanced/intense activity count variants)

---

## Quick Start

### Prerequisites

- Python 3.10+
- Docker Desktop (Redis)
- Supabase account or local PostgreSQL
- [Google Gemini API key](https://aistudio.google.com/app/apikey) — enables AI polish
- [Pexels API key](https://www.pexels.com/api/) — free, 200 req/hr, attraction photos (optional)

### 1. Clone & Install

```bash
git clone https://github.com/yash-dev007/AltairGO-Engine.git
cd AltairGO-Engine

python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r backend/requirements.txt
```

### 2. Start Infrastructure

```bash
docker compose up -d redis
```

### 3. Configure Environment

```bash
cp .env.example .env
```

Edit `.env`:

```env
# Required
DATABASE_URL=postgresql://user:pass@host:5432/dbname
REDIS_URL=redis://localhost:6379/0
JWT_SECRET_KEY=your-secret-key-minimum-32-characters-long
ADMIN_ACCESS_KEY=your-admin-portal-key
GEMINI_API_KEY=your-gemini-api-key

# Optional — all free
PEXELS_API_KEY=your-pexels-key   # pexels.com/api
DEV_EAGER=true                   # Celery runs in-process — no worker needed locally
```

### 4. Run

```bash
python -m flask --app backend.app:create_app run --port 5000 --reload
```

API available at `http://localhost:5000`. Health check: `GET /health`.

### 5. Seed Data

```bash
# Ingest attractions from OpenStreetMap
python -m backend.scripts.ingest_osm_data --city "Jaipur"

# Enrich with Wikidata + Wikipedia (no Google Places needed)
python -m backend.scripts.enrich_attractions

# Compute H3 geospatial indices
python -m backend.scripts.h3_indexer

# Score attractions
python -m backend.scripts.score_attractions

# Seed pricing
python -m backend.scripts.sync_prices

# Initialise engine settings
python -m backend.scripts.init_settings
```

### Makefile Shortcuts

```bash
make dev-backend    # Flask dev server on port 5000
make dev-worker     # Celery worker (production)
make dev-beat       # Celery beat scheduler (production)
make test           # Run pytest suite
```

---

## Project Structure

```
AltairGO-Engine/
├── backend/
│   ├── app.py                     # Flask factory, 15 blueprints, /health
│   ├── celery_config.py           # Celery + beat schedule (11 jobs)
│   ├── celery_tasks.py            # All Celery task definitions
│   ├── database.py                # SQLAlchemy db + SessionLocal()
│   ├── extensions.py              # Rate limiter (memory:// in DEV/TESTING)
│   ├── models.py                  # 28+ SQLAlchemy models
│   ├── schemas.py                 # Marshmallow validation schemas
│   ├── constants.py               # All magic numbers centralised
│   ├── validation.py              # ItineraryValidator
│   │
│   ├── engine/                    # Deterministic itinerary pipeline
│   │   ├── orchestrator.py        # TripGenerationOrchestrator.generate()
│   │   ├── filter_engine.py       # 9-step filtering
│   │   ├── cluster_engine.py      # H3 geospatial clustering + theme diversity
│   │   ├── budget_allocator.py    # Tier splits + auto-demotion + group discounts
│   │   ├── route_optimizer.py     # Time scheduling + enriched activity output
│   │   └── assembler.py           # Final JSON + checklist + transport guide
│   │
│   ├── routes/
│   │   ├── auth.py                # Register, login, refresh, /me (lockout-protected)
│   │   ├── trips.py               # Generation, save, get, variants
│   │   ├── destinations.py        # Countries, destinations, budget calc
│   │   ├── bookings.py            # Full booking automation + execute-all + dashboard
│   │   ├── expenses.py            # Expense tracker (planned vs actual)
│   │   ├── discover.py            # Recommend, best-time, compare, estimate-budget
│   │   ├── trip_tools.py          # Readiness, daily briefing, swap, next-trip ideas
│   │   ├── trip_editor.py         # Hotel/activity/notes/reorder editing
│   │   ├── profile.py             # GET/PUT profile, DELETE account (GDPR)
│   │   ├── sharing.py             # Share link create/revoke + public view
│   │   ├── search.py              # Full-text search (destinations + countries)
│   │   ├── admin.py               # Admin CRUD
│   │   ├── dashboard.py           # /api/ops/summary + SSE live-metrics
│   │   ├── ops.py                 # Job triggers, engine config, agent triggers
│   │   └── signals.py             # Behavioral signal tracking
│   │
│   ├── services/
│   │   ├── gemini_service.py      # Gemini 2.0 Flash + lite fallback + 3 retries
│   │   ├── cache_service.py       # SHA-256 Redis cache keys + env-var TTLs
│   │   ├── metrics_service.py     # Pipeline metrics + SSE streaming
│   │   └── image_service.py       # Wikipedia → Wikidata → Pexels → SVG placeholder
│   │
│   ├── agents/                    # AI agents (memory, QA, validator, scraper)
│   ├── tasks/                     # Celery task implementations
│   ├── scripts/                   # Data pipeline (OSM, enrichment, H3, scoring, prices)
│   └── tests/                     # 188 passed, 1 skipped
│       ├── conftest.py
│       ├── test_auth.py
│       ├── test_api.py
│       ├── test_engine.py
│       ├── test_pipeline.py
│       ├── test_trips.py
│       ├── test_signals.py
│       └── test_validation.py
│
├── docker-compose.yml
├── Dockerfile
├── gunicorn.conf.py
├── Makefile
└── .env.example
```

---

## API Reference

### Health

```
GET /health    # DB + Redis connectivity status
```

### Authentication

| Method | Endpoint | Rate Limit | Description |
|---|---|---|---|
| `POST` | `/auth/register` | 5/min | Create account (password min 12 chars) |
| `POST` | `/auth/login` | 10/min | Login — 5 fails → 15min lockout |
| `POST` | `/auth/refresh` | 30/min | Refresh access token |
| `GET` | `/auth/me` | — | Current user |

Access token: 1h | Refresh token: 30d

### Trips

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| `POST` | `/generate-itinerary` | — | Create async job |
| `GET` | `/get-itinerary-status/<job_id>` | — | Poll status |
| `POST` | `/api/save-trip` | JWT | Save trip |
| `GET` | `/get-trip/<trip_id>` | JWT | Fetch trip |
| `GET` | `/api/user/trips` | JWT | Paginated list |
| `POST` | `/api/trip/<id>/variants` | JWT | relaxed/balanced/intense variants |

**Sample request body:**

```json
{
  "destination_country": "India",
  "selected_destinations": [{ "name": "Jaipur" }],
  "start_city": "Jaipur",
  "budget": 15000,
  "duration": 3,
  "travelers": 2,
  "style": "balanced",
  "traveler_type": "couple",
  "travel_month": "12",
  "dietary_restrictions": "vegetarian",
  "children_count": 0,
  "senior_count": 0
}
```

> Note: `selected_destinations` is a list of objects `[{"name": "..."}]`, not plain strings. `travel_month` is a string `"12"`, not an integer.

### Discovery

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/discover/recommend` | AI-scored destination recommendations |
| `GET` | `/api/discover/best-time/<dest_id>` | Month-by-month seasonal score matrix |
| `GET` | `/api/discover/is-good-time?dest_id&month` | Quick verdict + best alternative month |
| `POST` | `/api/discover/estimate-budget` | Full cost breakdown before committing |
| `POST` | `/api/discover/compare` | Side-by-side comparison with winner |

### Bookings

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| `GET` | `/api/trip/<id>/booking-plan` | JWT | Full booking plan |
| `POST` | `/api/booking/<id>/approve` | JWT | Approve one booking |
| `POST` | `/api/booking/<id>/reject` | JWT | Reject one booking |
| `POST` | `/api/trip/<id>/booking-plan/execute-all` | JWT | Execute all approved bookings |
| `POST` | `/api/booking/<id>/cancel` | JWT | Cancel booking |
| `GET` | `/api/trip/<id>/bookings` | JWT | Dashboard grouped by type |
| `PUT` | `/api/booking/<id>/customize` | JWT | Edit or mark self-arranged |
| `POST` | `/api/trip/<id>/booking-plan/add-custom` | JWT | Add self-arranged booking |

### Expenses

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| `POST` | `/api/trip/<id>/expense` | JWT | Log actual spending |
| `GET` | `/api/trip/<id>/expenses` | JWT | Planned vs actual per category |
| `DELETE` | `/api/expense/<id>` | JWT | Delete expense entry |

### Trip Tools

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| `GET` | `/api/trip/<id>/readiness` | JWT | 0-100% readiness score + checklist |
| `GET` | `/api/trip/<id>/daily-briefing/<day>` | JWT | Full day-of briefing |
| `POST` | `/api/trip/<id>/activity/swap` | JWT | Swap activity + re-optimize |
| `GET` | `/api/trip/<id>/next-trip-ideas` | JWT | Post-trip destination ideas |

### Trip Editor

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| `GET` | `/api/trip/<id>/hotel-options` | JWT | Browse hotels by category/price |
| `PUT` | `/api/trip/<id>/hotel` | JWT | Swap hotel |
| `POST` | `/api/trip/<id>/day/<n>/activity/add` | JWT | Add activity (DB or custom) |
| `DELETE` | `/api/trip/<id>/day/<n>/activity/remove` | JWT | Remove + re-optimize |
| `PUT` | `/api/trip/<id>/day/<n>/activity/edit` | JWT | Edit cost/note/time |
| `PUT` | `/api/trip/<id>/day/<n>/reorder` | JWT | Reorder + re-optimize |
| `PUT` | `/api/trip/<id>/notes` | JWT | Save trip + per-day notes |

### Sharing & Profile

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| `POST` | `/api/trip/<id>/share` | JWT | Create public share link (30-day TTL) |
| `DELETE` | `/api/trip/<id>/share` | JWT | Revoke share link |
| `GET` | `/api/shared/<token>` | — | Public read-only itinerary view |
| `GET` | `/api/user/profile` | JWT | Get profile + preferences |
| `PUT` | `/api/user/profile` | JWT | Update name + preferences |
| `DELETE` | `/api/user/account` | JWT | GDPR anonymise account |

### Search

```
GET /api/search?q=<query>&type=all|destination|country&limit=10
```

Results sorted: exact match → prefix match → contains.

### Admin & Ops

All admin endpoints require `X-Admin-Key` header or admin JWT (`POST /api/admin/verify-key`).

| Endpoint | Description |
|---|---|
| `GET /api/admin/stats` | Aggregate counts |
| `GET/POST /api/admin/destinations` | List / create destinations |
| `PUT/DELETE /api/admin/destinations/<id>` | Update / delete |
| `GET /api/admin/users` | Paginated user list |
| `GET /api/admin/trips` | All generated trips |
| `GET /api/admin/requests` | Destination suggestion queue |
| `POST /api/admin/requests/<id>/approve` | Approve destination request |
| `POST /api/admin/requests/<id>/reject` | Reject destination request |
| `GET /api/ops/summary` | Full system health snapshot |
| `GET /api/ops/live-metrics` | SSE stream (`?token=<jwt>`) |
| `POST /api/ops/trigger-job` | Fire Celery job by name |
| `POST /api/ops/trigger-agent` | Fire AI agent |
| `GET/POST /api/ops/engine-config` | Read/update engine settings |

---

## Configuration

### Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `DATABASE_URL` | Yes | — | PostgreSQL connection string |
| `REDIS_URL` | Yes | — | Redis broker + rate limit + cache |
| `JWT_SECRET_KEY` | Yes | — | Min 32 chars |
| `ADMIN_ACCESS_KEY` | Yes | — | Admin portal key |
| `GEMINI_API_KEY` | Optional | — | AI itinerary polish |
| `PEXELS_API_KEY` | Optional | — | Attraction photos (free at pexels.com/api) |
| `DEV_EAGER` | Optional | false | Celery runs synchronously (no worker needed) |
| `VALIDATION_STRICT` | Optional | false | Stricter post-generation validation |
| `GEMINI_MODEL` | Optional | gemini-2.0-flash | Override Gemini model |
| `ALLOWED_ORIGINS` | Optional | localhost + altairgo.in | CORS whitelist |
| `THEME_THRESHOLD` | Optional | 0.20 | Day-theme overlap threshold |

### No Google Places Required

Images are served through a free priority chain:

1. **Wikipedia REST API** — thumbnails for named attractions (no key needed)
2. **Wikidata SPARQL (P18)** — Wikimedia Commons images (no key needed)
3. **Pexels API** — free tier, 200 req/hr, no credit card required

For attraction ratings, the enrichment script uses Wikidata. [OpenTripMap](https://opentripmap.com/docs) (free, 50 req/min) can be integrated as a drop-in replacement for Google Places ratings.

### Runtime Engine Settings

Tunable via `POST /api/ops/engine-config` without redeploy:

| Key | Default | Description |
|---|---|---|
| `strict_validation` | false | Enable strict itinerary validation |
| `theme_threshold` | 0.20 | Day-theme overlap threshold |
| `gemini_model` | gemini-2.0-flash | Active Gemini model |
| `seasonal_gate` | 70 | Minimum seasonal score |
| `popularity_floor` | 25 | Minimum popularity score |
| `cache_ttl_hours` | 168 | Itinerary cache TTL |
| `max_daily_activities` | 6 | Hard cap per day |
| `group_discount_small` | 0.10 | Discount for 5-9 travelers |
| `group_discount_large` | 0.15 | Discount for 10+ travelers |
| `score_blend_weight` | 0.3 | Quality score blend into popularity |

---

## Database

### Models (28+ tables)

**Users:** `User`, `UserProfile`

**Geography:** `Country`, `State`, `Destination`, `Attraction`

**Trips:** `Trip`, `AsyncJob`

**Bookings:** `Booking`, `TripPermissionRequest`, `ExpenseEntry`

**Pricing:** `HotelPrice`, `FlightRoute`, `CurrencyRate`

**Intelligence:** `AttractionSignal`, `AnalyticsEvent`, `Feedback`, `WeatherAlert`, `LocalEvent`

**Destination Info:** `DestinationInfo` (visa, safety, health, emergency contacts, local phrases)

**Admin:** `DestinationRequest`, `FeatureFlag`, `EngineSetting`, `DataSourceLog`, `POIClosure`

### Migrations

Production schema is managed via **Supabase MCP**. Never run `flask db upgrade` against production — autogenerate tries to drop PostGIS system tables. Use targeted `ALTER TABLE` / `CREATE TABLE IF NOT EXISTS` DDL instead.

---

## Testing

```bash
python -m pytest backend/tests/ -v --tb=short
```

**Result: 188 passed, 1 skipped**

Runs against SQLite in-memory + memory:// Redis with `TESTING=true`. No external services required.

| Test File | Coverage |
|---|---|
| `test_auth.py` | Registration, login, JWT refresh, brute-force lockout |
| `test_api.py` | Admin CRUD, endpoint contracts, status codes |
| `test_engine.py` | Filter, cluster, budget, route, assembler |
| `test_pipeline.py` | OSM ingestion, enrichment, price sync, scoring |
| `test_trips.py` | Generation, save, get, user trips, validation |
| `test_signals.py` | Signal recording, event type validation |
| `test_validation.py` | Budget checks, quality scoring, edge cases |

---

## Security

- **JWT authentication** — 1h access tokens, 30d refresh tokens
- **Brute-force lockout** — 5 failed logins → 429 for 15 minutes (Redis-backed, degrades silently if Redis down)
- **Rate limiting** — Flask-Limiter on all sensitive endpoints
- **SSE auth** — query-param token (EventSource API cannot send headers)
- **Admin isolation** — `@require_admin` on all admin/ops endpoints
- **GDPR anonymisation** — DELETE account clears PII without breaking FK references
- **SPARQL injection prevention** — Wikidata queries sanitized (strip non-alphanumeric, 100-char limit)
- **Non-root Docker** — production container runs as non-root user

---

## Deployment

### Docker Compose

```bash
docker compose up --build
```

Starts: PostgreSQL, Redis, Flask + Gunicorn, Celery worker, Celery beat.

### Gunicorn (Production)

```bash
gunicorn -c gunicorn.conf.py "backend.app:create_app()"
```

CPU-count workers, 120s timeout.

### Celery Workers

```bash
# Worker
celery -A backend.celery_config:celery_app worker --loglevel=info

# Beat scheduler
celery -A backend.celery_config:celery_app beat --loglevel=info
```

### Supabase (Recommended DB)

Use the Supabase dashboard or MCP tools for DDL changes. Never run `flask db upgrade` in production.

---

## Contributing

1. Fork the repository
2. Create your branch: `git checkout -b feature/my-feature`
3. Run tests: `make test`
4. Commit: `git commit -m 'feat: add my feature'`
5. Push and open a Pull Request

---

## License

This project is licensed under the **MIT License** — see [LICENSE](LICENSE) for details.

---

<div align="center">

Built by **[yash-dev007](https://github.com/yash-dev007)**

</div>
