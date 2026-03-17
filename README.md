<div align="center">

<img src="https://img.shields.io/badge/AltairGO-Engine-22c55e?style=for-the-badge&logo=airplane&logoColor=white" alt="AltairGO Engine" />

# AltairGO Engine

**AI-powered travel itinerary generation platform with a deterministic 5-step pipeline, real-time ops dashboard, Celery job orchestration, and Gemini 2.0 Flash polish.**

[![Python 3.10+](https://img.shields.io/badge/Python-3.10+-3776AB?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![Flask 3.x](https://img.shields.io/badge/Flask-3.x-000000?style=flat-square&logo=flask&logoColor=white)](https://flask.palletsprojects.com)
[![React 19](https://img.shields.io/badge/React-19-61DAFB?style=flat-square&logo=react&logoColor=black)](https://react.dev)
[![PostgreSQL + PostGIS](https://img.shields.io/badge/PostgreSQL-PostGIS-336791?style=flat-square&logo=postgresql&logoColor=white)](https://postgresql.org)
[![Redis](https://img.shields.io/badge/Redis-7-DC382D?style=flat-square&logo=redis&logoColor=white)](https://redis.io)
[![Gemini 2.0](https://img.shields.io/badge/Gemini-2.0%20Flash-4285F4?style=flat-square&logo=google&logoColor=white)](https://deepmind.google/technologies/gemini/)
[![Tests](https://img.shields.io/badge/Tests-188%20passed-22c55e?style=flat-square)](backend/tests/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green?style=flat-square)](LICENSE)

<br/>

[Quick Start](#-quick-start) &bull; [Architecture](#-architecture) &bull; [Dashboard](#-mission-control-dashboard) &bull; [API Reference](#-api-reference) &bull; [Deployment](#-deployment)

</div>

---

## Overview

AltairGO Engine generates hyper-personalized, budget-accurate, day-by-day travel itineraries through a **deterministic 5-step pipeline**. AI (Google Gemini 2.0 Flash) is used only to polish the final output — not to decide structure, budget allocation, or routing.

The platform ships with a full **Mission Control** admin dashboard built in React 19 that provides real-time visibility into every backend workflow.

### Key Differentiators

| Feature | Details |
|---|---|
| **Deterministic pipeline** | Filter &rarr; Cluster &rarr; Budget &rarr; Route &rarr; Assemble. AI adds polish, not structure |
| **Mission Control dashboard** | 6-page admin UI covering every backend endpoint with SSE live metrics |
| **Post-generation validation** | `ItineraryValidator` auto-corrects budget overruns, generic names, cost inconsistencies |
| **Real-time streaming** | Server-Sent Events stream pipeline latency, cache hits, and agent health |
| **Geospatial intelligence** | H3 hexagonal cells + PostGIS for attraction clustering into walkable day plans |
| **Celery orchestration** | 10+ scheduled jobs for ingestion, enrichment, scoring, and cache warming |
| **188 passing tests** | Comprehensive test suite covering auth, API contracts, engine, pipeline, and validation |

---

## Architecture

### System Overview

```
+---------------------------------------------------------------+
|                   React 19 Frontend (Vite)                     |
|   Dashboard  |  Planner  |  Agents  |  Network  |  Data Lab   |
+-------------------------------+-------------------------------+
                                | REST + SSE
+-------------------------------v-------------------------------+
|                    Flask API (8 Blueprints)                    |
|  auth | trips | destinations | admin | ops | dashboard | signals
+---------------+-------------------------------+---------------+
                |                               |
+---------------v---------------+  +------------v--------------+
|     Itinerary Pipeline        |  |      Service Layer         |
|                               |  |                            |
|  1. FilterEngine              |  |  GeminiService (polish)    |
|  2. ClusterEngine (H3)       |  |  CacheService (Redis)      |
|  3. BudgetAllocator          |  |  MetricsService (SSE)      |
|  4. RouteOptimizer           |  |  ImageService (5-source)   |
|  5. Assembler                |  |  AffiliateService          |
+---------------+---------------+  +------------+--------------+
                |                               |
+---------------v-------------------------------v---------------+
|               Data & Infrastructure Layer                      |
|    PostgreSQL + PostGIS  |  Redis  |  Celery Beat + Worker     |
+---------------------------------------------------------------+
```

### The Itinerary Pipeline

```
User Request (destination, budget, duration, travelers, style, traveler_type)
     |
     v
[FilterEngine]       Filters by popularity, traveler type, seasonality, budget
     |
     v
[ClusterEngine]      Groups nearby attractions into day buckets using H3 cells
     |
     v
[BudgetAllocator]    Distributes: transport 20%, accommodation 35%, food 25%,
     |                activities 15%, misc 5%
     v
[RouteOptimizer]     Orders activities by time with travel pacing
     |
     v
[Assembler]          Builds frontend-facing itinerary JSON with metadata
     |
     v
[GeminiService]      AI-polished descriptions, trip title, insights, packing tips
     |
     v
[ItineraryValidator] Budget +/-5% check, quality assurance, cost consistency
     |
     v
  Response
```

### Background Jobs (Celery Beat)

All times in `Asia/Kolkata` timezone.

| Job | Schedule | Purpose |
|---|---|---|
| Destination validation | Daily 01:00 | AI-validates destination data quality |
| Behavioral score update | Daily 02:00 | Updates attraction popularity scores |
| OSM ingestion | Sunday 03:00 | Fetches new POIs from Overpass API |
| Cache warming | Daily 03:30 | Pre-warms Redis for top destinations |
| Attraction enrichment | Monday 04:00 | Enriches from Wikidata + Wikipedia |
| Trip quality scoring | Daily 04:30 | Scores saved trips for quality metrics |
| Attraction scoring | 1st of month 05:00 | Monthly popularity recalculation |
| Price sync | Daily 06:00 + 18:00 | Refreshes hotel, flight, activity pricing |
| Affiliate health check | Every 6 hours | Validates partner booking API health |
| Worker heartbeat | Every 5 mins | Signals worker availability to dashboard |

---

## Mission Control Dashboard

A 6-page admin dashboard built with React 19 + Tailwind CSS that covers **every** backend admin endpoint.

| Page | Route | What It Does |
|---|---|---|
| **Dashboard** | `/` | KPI cards, Gemini metrics, cache stats, P95 latency, agent fleet health, pipeline job control with real polling, SSE live activity feed, pending requests banner |
| **Trip Planner** | `/planner` | Full itinerary generation form with destination, budget, duration, travelers, traveler type, experience style. Async polling with status updates |
| **AI Agent Matrix** | `/agents` | Agent grid with trigger buttons, dispatch status, fleet health summary, distributed pipeline health panel |
| **Network Hub** | `/network` | Paginated user management, trip inspection (full JSON viewer), delete operations |
| **Data Laboratory** | `/data` | Destination CRUD table, destination request review queue with approve/reject workflow |
| **Intelligence Config** | `/settings` | Engine config tuning: strict validation toggle, theme threshold slider, Gemini model selector |

### Dashboard Features
- **SSE live metrics** with error-counted auto-close (stops reconnecting after 3 failures)
- **Real job polling** via `task_id` with progress indicators
- **Static Tailwind color map** to prevent JIT purging in production builds
- **Interval cleanup** on all polling components to prevent memory leaks
- **Client-side routing** with `react-router-dom` throughout (no full page reloads)

---

## Quick Start

### Prerequisites

- Python 3.10+
- Node.js 18+
- Docker Desktop (PostgreSQL + Redis)
- [Google Gemini API key](https://aistudio.google.com/app/apikey) (optional, enables AI polish)

### 1. Clone & Install

```bash
git clone https://github.com/yash-dev007/AltairGO-Engine.git
cd AltairGO-Engine

# Backend
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r backend/requirements.txt

# Frontend
cd dummy-frontend && npm install && cd ..
```

### 2. Start Infrastructure

```bash
docker compose up -d postgres redis
```

This starts **PostgreSQL 15 + PostGIS** on `localhost:5432` and **Redis 7** on `localhost:6379`.

### 3. Configure Environment

```bash
cp .env.example .env
```

Edit `.env` with your values:

```env
DATABASE_URL=postgresql://altairgo:altairgo_dev_pass@localhost:5432/altairgo
REDIS_URL=redis://localhost:6379/0
JWT_SECRET_KEY=your-secret-key-minimum-32-characters-long
ADMIN_ACCESS_KEY=your-admin-portal-key
GEMINI_API_KEY=your-gemini-api-key        # optional
```

### 4. Run the Backend

```bash
python -m flask --app backend.app:create_app run --port 5000 --reload
```

### 5. Run the Frontend

```bash
cd dummy-frontend && npm run dev
```

Open `http://localhost:5173` and login with your admin key.

### 6. Run Celery Workers (Optional)

```bash
# Worker (processes background jobs)
celery -A backend.celery_config:celery_app worker --loglevel=info

# Beat (triggers scheduled jobs)
celery -A backend.celery_config:celery_app beat --loglevel=info
```

### Makefile Shortcuts

```bash
make dev            # Start Docker + Flask backend
make dev-infra      # Start PostgreSQL + Redis only
make dev-backend    # Flask dev server on port 5000
make dev-frontend   # Vite dev server on port 5173
make dev-worker     # Celery worker
make dev-beat       # Celery beat scheduler
make run-all        # Start everything in parallel
make test           # Run pytest suite
make build-frontend # Production frontend build
make clean          # Stop Docker containers
```

---

## Project Structure

```
AltairGO-Engine/
├── backend/
│   ├── app.py                     # Flask factory, 8 blueprints, JWT, CORS, /health
│   ├── celery_config.py           # Celery app + beat schedule registry
│   ├── celery_tasks.py            # All Celery task definitions
│   ├── database.py                # SQLAlchemy engine + configure_database()
│   ├── extensions.py              # Rate limiter (Redis-backed)
│   ├── models.py                  # 18 SQLAlchemy models
│   ├── schemas.py                 # Marshmallow validation schemas
│   ├── utils/auth.py              # @require_admin decorator, JWT helpers
│   │
│   ├── engine/                    # Deterministic itinerary pipeline
│   │   ├── orchestrator.py        # TripGenerationOrchestrator.generate()
│   │   ├── filter_engine.py       # Popularity + compatibility filtering
│   │   ├── cluster_engine.py      # H3 geospatial day clustering
│   │   ├── budget_allocator.py    # Budget distribution logic
│   │   ├── route_optimizer.py     # Time-based activity ordering
│   │   └── assembler.py           # Frontend schema builder
│   │
│   ├── routes/
│   │   ├── auth.py                # Register, login, refresh, /me
│   │   ├── trips.py               # Itinerary generation + save/get
│   │   ├── destinations.py        # Countries, destinations, budget calc
│   │   ├── signals.py             # Attraction engagement signals
│   │   ├── admin.py               # Admin CRUD (users, trips, destinations, requests)
│   │   ├── ops.py                 # Job triggers, engine config, agent triggers
│   │   └── dashboard.py           # /api/ops/summary, SSE live-metrics
│   │
│   ├── services/
│   │   ├── gemini_service.py      # Gemini 2.0 Flash + lite fallback + 3 retries
│   │   ├── cache_service.py       # Redis cache wrapper
│   │   ├── metrics_service.py     # Pipeline metrics + SSE streaming
│   │   └── image_service.py       # Multi-source image pipeline
│   │
│   ├── agents/                    # AI helper agents (memory, QA, scraper, etc.)
│   ├── scripts/                   # Data pipeline scripts (OSM, enrichment, scoring)
│   └── tests/                     # 188 passing tests
│       ├── conftest.py            # SQLite in-memory fixtures, admin JWT
│       ├── test_auth.py           # Registration, login, JWT flows
│       ├── test_api.py            # Endpoint contracts + status codes
│       ├── test_engine.py         # Pipeline step unit tests
│       ├── test_pipeline.py       # Price sync, scoring, enrichment
│       ├── test_trips.py          # Itinerary generation + save/get
│       ├── test_signals.py        # Attraction signal recording
│       └── test_validation.py     # ItineraryValidator edge cases
│
├── dummy-frontend/                # React 19 + Vite admin dashboard
│   └── src/
│       ├── App.jsx                # Router + auth gate
│       ├── App.css                # Animations + custom scrollbar
│       ├── contexts/AuthContext.jsx
│       ├── components/Layout.jsx  # Sidebar + header with route-aware titles
│       ├── services/api.js        # Authenticated fetch wrapper, all API methods
│       └── pages/
│           ├── Dashboard.jsx      # Mission Control (KPIs, jobs, SSE feed)
│           ├── Planner.jsx        # Trip generation form + async polling
│           ├── AIAgentHub.jsx     # Agent fleet management + triggers
│           ├── NetworkHub.jsx     # User + trip management
│           ├── DataLaboratory.jsx # Destination CRUD + request review
│           └── IntelligenceHub.jsx# Engine config tuning
│
├── docker-compose.yml             # Full stack: Postgres, Redis, Flask, Celery
├── Dockerfile                     # Python 3.11-slim, Gunicorn, non-root user
├── railway.toml                   # Railway deployment config
├── Makefile                       # Dev shortcuts
└── .env.example                   # Environment template
```

---

## API Reference

### Health Check

```
GET /health    # Returns DB + Redis connectivity status
```

### Authentication

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| `POST` | `/auth/register` | &mdash; | Create user account |
| `POST` | `/auth/login` | &mdash; | Login, returns access + refresh tokens |
| `POST` | `/auth/refresh` | Refresh JWT | Refresh access token |
| `GET` | `/auth/me` | JWT | Current user profile |

### Trip Planning

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| `POST` | `/generate-itinerary` | Optional | Triggers async itinerary generation |
| `GET` | `/get-itinerary-status/<job_id>` | &mdash; | Poll for generation completion |
| `POST` | `/api/save-trip` | JWT | Save itinerary to user account |
| `GET` | `/get-trip/<trip_id>` | JWT | Retrieve saved trip (owner only) |
| `GET` | `/api/user/trips` | JWT | List user's saved trips |

**Sample request:**

```json
{
  "destination_country": "India",
  "selected_destinations": [{ "name": "Jaipur" }],
  "start_city": "Jaipur",
  "budget": 15000,
  "duration": 3,
  "travelers": 2,
  "style": "balanced",
  "traveler_type": "couple"
}
```

### Destinations

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| `GET` | `/countries` | &mdash; | List all countries |
| `GET` | `/destinations` | &mdash; | Browse/filter destinations (paginated) |
| `GET` | `/destinations/<id>` | &mdash; | Destination detail + attractions |
| `POST` | `/calculate-budget` | &mdash; | Estimate trip budget |
| `POST` | `/api/destination-request` | &mdash; | Submit destination suggestion |

### Signals

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| `POST` | `/api/attraction-signal` | Optional | Log engagement (view, save, swap, book_click) |

### Admin (JWT Required)

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/admin/verify-key` | Verify admin key, returns JWT |
| `GET` | `/api/admin/stats` | Total users, trips, destinations, attractions |
| `GET/POST` | `/api/admin/destinations` | List + create destinations |
| `PUT/DELETE` | `/api/admin/destinations/<id>` | Update + delete destination |
| `GET` | `/api/admin/users` | Paginated user list |
| `DELETE` | `/api/admin/users/<id>` | Delete user + all their data |
| `GET` | `/api/admin/requests` | Destination request queue |
| `POST` | `/api/admin/requests/<id>/approve` | Approve + create destination |
| `POST` | `/api/admin/requests/<id>/reject` | Reject request |
| `GET` | `/api/admin/trips` | All generated trips |
| `GET/DELETE` | `/api/admin/trips/<id>` | Get/delete specific trip |

### Operations (JWT Required)

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/ops/summary` | Full system health snapshot |
| `GET` | `/api/ops/live-metrics` | SSE stream (token via query param) |
| `POST` | `/api/ops/trigger-job` | Trigger background job by name |
| `GET` | `/api/ops/job-status/<task_id>` | Check Celery task status |
| `POST` | `/api/ops/trigger-agent` | Manually trigger an AI agent |
| `GET/POST` | `/api/ops/engine-config` | Read/update engine configuration |

---

## Configuration

### Environment Variables

| Variable | Required | Description |
|---|---|---|
| `DATABASE_URL` | Yes | PostgreSQL connection string |
| `REDIS_URL` | Yes | Redis broker URL |
| `JWT_SECRET_KEY` | Yes | Minimum 32 chars for signing JWTs |
| `ADMIN_ACCESS_KEY` | Yes | Admin portal authentication key |
| `GEMINI_API_KEY` | Optional | Enables AI polish on itineraries |
| `VALIDATION_STRICT` | Optional | Enables stricter post-generation validation |
| `ALLOWED_ORIGINS` | Optional | CORS whitelist (default: localhost + altairgo.in) |
| `PEXELS_API_KEY` | Optional | Image source integration |

---

## Database

### Populating Data

The database initializes with PostGIS extensions only. Run the data pipeline to seed destinations:

```bash
# 1. Ingest POIs from OpenStreetMap
python backend/scripts/ingest_osm_data.py --city "Jaipur"

# 2. Enrich with Wikidata + Wikipedia metadata
python backend/scripts/enrich_attractions.py

# 3. Compute popularity and seasonal scores
python backend/scripts/score_attractions.py

# 4. Seed pricing data
python backend/scripts/sync_prices.py
```

### Core Models (18 tables)

**Primary:** `User`, `Trip`, `Destination`, `Attraction`, `Country`, `State`, `AsyncJob`

**Pricing:** `HotelPrice`, `FlightRoute`, `CurrencyRate`

**Intelligence:** `AttractionSignal`, `AnalyticsEvent`, `UserProfile`, `Feedback`

**Admin:** `DestinationRequest`, `FeatureFlag`, `EngineSetting`, `DataSourceLog`, `POIClosure`

---

## Testing

```bash
python -m pytest backend/tests/ -v --tb=short
```

**Result: 188 passed, 1 skipped**

Tests run against SQLite in-memory with `TESTING=true`. No external services required.

| Test File | Coverage |
|---|---|
| `test_auth.py` | Registration, login, JWT refresh, /me |
| `test_api.py` | Admin CRUD, endpoint contracts, status codes |
| `test_engine.py` | Filter, cluster, budget, route, assembler |
| `test_pipeline.py` | OSM ingestion, enrichment, price sync, scoring |
| `test_trips.py` | Generation, save, get, user trips, validation |
| `test_signals.py` | Signal recording, event type validation |
| `test_validation.py` | Budget checks, quality scoring, edge cases |

---

## Security

- **JWT authentication** with short-lived access tokens (1h) and long-lived refresh tokens (30d)
- **Rate limiting** via Redis-backed `Flask-Limiter` on sensitive endpoints
- **SSE auth** via query-param token (EventSource API cannot send headers)
- **Admin isolation** with `@require_admin` decorator on all admin/ops endpoints
- **Strict validation** mode for production-grade itinerary quality checks
- **Non-root Docker** user in production container

---

## Deployment

### Docker Compose (Full Stack)

```bash
docker compose up --build
```

Starts 5 services: PostgreSQL 15 + PostGIS, Redis 7, Flask + Gunicorn, Celery worker, Celery beat.

### Railway

Pre-configured via `railway.toml`. Deploys using the included `Dockerfile` with Gunicorn (4 workers, 120s timeout). Health checks on `/health`.

### Vercel (Frontend)

```bash
cd dummy-frontend
npm run build
vercel --prod
```

`vercel.json` handles SPA rewrites and API proxy.

---

## Contributing

1. Fork the repository
2. Create your branch: `git checkout -b feature/my-feature`
3. Run tests: `make test`
4. Commit: `git commit -m 'feat: add my feature'`
5. Push and open a Pull Request

---

## License

This project is licensed under the **MIT License** &mdash; see [LICENSE](LICENSE) for details.

---

<div align="center">

Built by **[yash-dev007](https://github.com/yash-dev007)**

</div>
