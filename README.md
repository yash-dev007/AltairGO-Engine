<div align="center">

<img src="https://img.shields.io/badge/AltairGO-Intelligence-22c55e?style=for-the-badge&logo=airplane&logoColor=white" alt="AltairGO Intelligence" />

# ✈️ AltairGO Engine

**An AI-powered travel planning backend with a deterministic itinerary pipeline, Redis-backed caching, Celery maintenance jobs, and a premium "Mission Control" real-time ops dashboard.**

[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![Flask](https://img.shields.io/badge/Flask-3.x-000000?style=flat-square&logo=flask&logoColor=white)](https://flask.palletsprojects.com)
[![React](https://img.shields.io/badge/React-19-61DAFB?style=flat-square&logo=react&logoColor=black)](https://react.dev)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-PostGIS-336791?style=flat-square&logo=postgresql&logoColor=white)](https://postgresql.org)
[![Redis](https://img.shields.io/badge/Redis-Cache%20%26%20Broker-DC382D?style=flat-square&logo=redis&logoColor=white)](https://redis.io)
[![Gemini](https://img.shields.io/badge/Google-Gemini%202.0-4285F4?style=flat-square&logo=google&logoColor=white)](https://deepmind.google/technologies/gemini/)
[![License](https://img.shields.io/badge/License-MIT-green?style=flat-square)](LICENSE)

<br/>

[🚀 Quick Start](#-quick-start) • [🏗️ Architecture](#%EF%B8%8F-architecture) • [📡 API Reference](#-api-reference) • [⚙️ Configuration](#%EF%B8%8F-configuration) • [🧪 Testing](#-testing)

</div>

---

## 🌟 Overview

AltairGO Engine is the backend powering the **AltairGO Intelligence** travel platform. It generates hyper-personalized, budget-accurate, day-by-day trip itineraries through a five-step deterministic pipeline — and uses Google Gemini only to polish the final output.

### What sets it apart

| **Deterministic-first pipeline** | Filter → Cluster → Budget → Route → Assemble, AI only adds polish |
| **Mission Control UI** | Reimagined premium dashboard with emerald green aesthetic and modular design |
| **Post-generation validation** | `ItineraryValidator` auto-corrects budget overruns, generic names, cost inconsistencies |
| **Real-time ops dashboard** | Server-Sent Events stream pipeline latency, cache hit rate, and agent health |
| **Supabase Integration** | Transaction-aware database connection logic for high-concurrency safety |
| **Celery job scheduler** | 10+ background jobs for ingestion, enrichment, scoring, and cache warming |
| **Geospatial awareness** | H3 cells + PostGIS for intelligent destination clustering |

---

## 📺 Visuals

### "Mission Control" Dashboard
![Mission Control Dashboard](https://raw.githubusercontent.com/yash-dev007/AltairGo-Engine/main/docs/screenshots/dashboard.png)

### Itinerary Generation
![AI Itinerary](https://raw.githubusercontent.com/yash-dev007/AltairGo-Engine/main/docs/screenshots/planner.png)

---

## 🏗️ Architecture

### System Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                     React 19 Frontend (Vite)                     │
│              Demo UI  ·  Itinerary Viewer  ·  /ops Dashboard     │
└────────────────────────────┬────────────────────────────────────┘
                             │ REST + SSE
┌────────────────────────────▼────────────────────────────────────┐
│                        Flask API (8 Blueprints)                  │
│  auth  ·  trips  ·  destinations  ·  admin  ·  ops  ·  affiliates│
└──────────┬──────────────────────────────┬───────────────────────┘
           │                              │
┌──────────▼──────────┐      ┌────────────▼─────────────┐
│  Itinerary Pipeline  │      │      Service Layer        │
│                      │      │                           │
│  1. FilterEngine     │      │  GeminiService (polish)   │
│  2. ClusterEngine    │      │  ImageService (5-source)  │
│  3. BudgetAllocator  │      │  CacheService (Redis)     │
│  4. RouteOptimizer   │      │  MetricsService (SSE)     │
│  5. Assembler        │      │  AffiliateService         │
└──────────┬──────────┘      └────────────┬─────────────┘
           │                              │
┌──────────▼──────────────────────────────▼─────────────┐
│              Data & Infrastructure Layer                │
│   PostgreSQL + PostGIS  ·  Redis  ·  Celery Beat/Worker│
└────────────────────────────────────────────────────────┘
```

### The Itinerary Pipeline

The core innovation — AI is used to polish descriptions, not to decide structure:

```
User Request
     │
     ▼
┌─────────────┐    Filters by popularity, traveler type,
│ FilterEngine │◄── seasonality, and budget compatibility
└──────┬──────┘
       ▼
┌──────────────┐   Groups nearby attractions into day
│ ClusterEngine │◄── buckets using H3 geospatial cells
└──────┬───────┘
       ▼
┌────────────────┐  Allocates budget across transport (20%),
│ BudgetAllocator │◄── accommodation (35%), food (25%), activities (15%), misc (5%)
└──────┬─────────┘
       ▼
┌───────────────┐   Orders activities into a time-based day
│ RouteOptimizer │◄── plan with travel time and pacing
└──────┬────────┘
       ▼
┌──────────┐        Builds the frontend-facing itinerary
│ Assembler │◄────── schema with all metadata
└──────┬───┘
       ▼
┌──────────────┐    Enriches with AI-polished descriptions,
│ GeminiService │◄── trip title, insights, packing tips
└──────┬───────┘
       ▼
┌────────────────────┐
│ ItineraryValidator │ Budget ±5% check, quality checks, cost consistency
└────────────────────┘
       ▼
    Response
```

### Background Jobs (Celery Beat)

> All times use `Asia/Kolkata` timezone.

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
| Affiliate health check | Every 6 hours | Validates affiliate link integrity |
| Worker Heartbeat | Every 5 mins | Signals worker availability to Mission Control |

---

## 🔐 Security & Reliability

- **Hardened Validation**: `VALIDATION_STRICT` environment variable for post-generation sanity checks.
- **Fail-Safe Metrics**: All Redis/Metrics writes are wrapped in `try-except` to prevent engine crashes during minor cache blips.
- **JWT Refresh Flow**: Enhanced security with short-lived access tokens (1h) and long-lived refresh tokens (30d).
- **Rate Limiting**: Applied to sensitive admin and generation endpoints using Redis-backed `Flask-Limiter`.
- **Gunicorn gevent**: Production-ready concurrency model for handling high-latency AI requests.

---

## 🚀 Quick Start

### Prerequisites

- Python 3.10+
- Node.js 18+
- Docker Desktop (for local PostgreSQL + Redis)
- A [Google Gemini API key](https://aistudio.google.com/app/apikey) (optional — enables AI polish)

### 1. Clone & Install Backend

```bash
git clone https://github.com/yash-dev007/AltairGo-Intelligence.git
cd AltairGo-Intelligence

# Create and activate virtual environment
python -m venv .venv

# Windows
.venv\Scripts\Activate.ps1

# macOS / Linux
source .venv/bin/activate

pip install -r backend/requirements.txt
```

### 2. Start Infrastructure

```bash
docker compose up -d postgres redis
```

This spins up:
- **PostgreSQL + PostGIS** on `localhost:5432`
- **Redis** on `localhost:6379`

### 3. Configure Environment

```bash
cp .env.example .env
# Edit .env with your values (see Configuration section)
```

### 4. Run the Backend

**Windows PowerShell:**
```powershell
$env:DATABASE_URL="postgresql://altairgo:altairgo_dev_pass@localhost:5432/altairgo"
$env:REDIS_URL="redis://localhost:6379/0"
$env:JWT_SECRET_KEY="change-me-in-dev"
$env:ADMIN_ACCESS_KEY="change-me-in-dev"
$env:GEMINI_API_KEY="your-gemini-key"
python -m flask --app backend.app:create_app run --port 5000 --reload
```

**macOS / Linux:**
```bash
export DATABASE_URL="postgresql://altairgo:altairgo_dev_pass@localhost:5432/altairgo"
export REDIS_URL="redis://localhost:6379/0"
export JWT_SECRET_KEY="change-me-in-dev"
export ADMIN_ACCESS_KEY="change-me-in-dev"
export GEMINI_API_KEY="your-gemini-key"
python -m flask --app backend.app:create_app run --port 5000 --reload
```

API available at → `http://localhost:5000`

### 5. Run the Frontend

```bash
cd dummy-frontend
npm install
npm run dev
```

Frontend available at → `http://localhost:5173`

- Visit `/` for the itinerary demo (requests trips for Jaipur, Goa, Mumbai)
- Visit `/ops` for the real-time operations dashboard

### 6. Run Celery Workers (Optional)

```bash
# Worker (processes jobs)
celery -A backend.celery_config:celery_app worker --loglevel=info

# Beat (triggers scheduled jobs)
celery -A backend.celery_config:celery_app beat --loglevel=info
```

### Makefile Shortcuts

```bash
make dev-infra      # Start Docker services
make test           # Run pytest suite
make lint           # Run ESLint + flake8
make build-frontend # Build Vite production bundle
make clean          # Remove build artifacts
```

> ⚠️ **Note:** `docker/postgres/init.sql` only enables PostGIS. It does **not** seed destinations. The `/generate-itinerary` endpoint requires existing data — see [Populating the Database](#populating-the-database) below.

---

## 📁 Project Structure

```
AltairGo-Intelligence/
├── backend/
│   ├── app.py                      # Flask app factory, 8 blueprints, JWT, CORS
│   ├── celery_config.py            # Celery app + scheduled task registry
│   ├── database.py                 # SQLAlchemy engine, session, init_db()
│   ├── agents/                     # Optional AI helper agents
│   │   ├── memory_agent.py         # Conversation memory
│   │   ├── live_context_agent.py   # Real-time destination context
│   │   ├── token_optimizer.py      # Prompt token management
│   │   ├── itinerary_qa_agent.py   # Post-generation quality checks
│   │   ├── scraper_agent.py        # Web scraping for enrichment
│   │   └── destination_validator.py# AI destination validation
│   ├── engine/                     # Deterministic itinerary pipeline
│   │   ├── filter_engine.py        # Popularity + compatibility filtering
│   │   ├── cluster_engine.py       # H3 geospatial day clustering
│   │   ├── budget_allocator.py     # Budget distribution logic
│   │   ├── route_optimizer.py      # Time-based activity ordering
│   │   └── assembler.py            # Frontend schema builder
│   ├── routes/
│   │   ├── auth.py                 # Register, Login, Me (JWT)
│   │   ├── trips.py                # Itinerary generation + CRUD
│   │   ├── destinations.py         # Countries, destinations, requests
│   │   ├── admin.py                # Admin CRUD + analytics
│   │   ├── ops.py                  # /ops/summary + /ops/live-metrics (SSE)
│   │   └── affiliates.py           # Booking redirect + revenue stats
│   ├── services/
│   │   ├── gemini_service.py       # Gemini API integration (polish + chat)
│   │   ├── image_service.py        # 5-source image pipeline
│   │   ├── cache_service.py        # Redis cache wrapper + TTL management
│   │   ├── metrics_service.py      # Pipeline metrics + SSE streaming
│   │   └── affiliate_service.py    # URL builder, click tracker, revenue calc
│   ├── scripts/
│   │   ├── ingest_osm_data.py      # Overpass API → POI upsert
│   │   ├── enrich_attractions.py   # Wikidata + Wikipedia + Google Places
│   │   ├── score_attractions.py    # Popularity + seasonal scoring
│   │   └── sync_prices.py          # Hotel, flight, activity price seeding
│   ├── tasks/                      # Celery task implementations
│   └── tests/                      # pytest suite
│       ├── conftest.py             # SQLite in-memory test fixtures
│       ├── test_auth.py
│       ├── test_api.py
│       ├── test_engine.py
│       ├── test_pipeline.py
│       └── test_validation.py
│
├── dummy-frontend/                 # Vite/React demo + ops UI
│   ├── src/
│   │   ├── App.jsx                 # Router (demo + /ops routes)
│   │   ├── pages/ItineraryDemo.jsx # Trip planning demo
│   │   └── pages/OpsDashboard.jsx  # Real-time metrics viewer
│   └── vite.config.js
│
├── docker/
│   └── postgres/init.sql           # PostGIS extension setup (no seed data)
├── docs/                           # Strategy and technical notes
├── docker-compose.yml
├── Dockerfile                      # Gunicorn on port 5000
├── railway.toml                    # Railway deployment config
└── vercel.json                     # Frontend SPA rewrites
```

---

## 📡 API Reference

### Health

```
GET /health
```

### Auth

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| POST | `/auth/register` | — | Create a new user account |
| POST | `/auth/login` | — | Login and receive JWT token |
| GET | `/auth/me` | JWT | Get current user profile |

### Trip Planning

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| POST | `/generate-itinerary` | Optional | Run the full 5-step pipeline |
| POST | `/api/save-trip` | JWT | Persist trip to user account |
| GET | `/get-trip/<trip_id>` | — | Retrieve a saved trip |
| GET | `/api/user/trips` | JWT | List all user trips |

**Sample `/generate-itinerary` request:**
```json
{
  "destination": "Jaipur",
  "budget": 15000,
  "duration": 3,
  "travelers": 2,
  "style": "standard",
  "traveler_type": "couple"
}
```

### Destinations

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| GET | `/countries` | — | List all countries |
| GET | `/destinations` | — | Browse/filter destinations |
| GET | `/destinations/<id>` | — | Destination details + attractions |
| POST | `/calculate-budget` | — | Estimate trip budget |
| POST | `/api/destination-request` | — | Submit a new destination suggestion |

### Signals & Analytics

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| POST | `/api/attraction-signal` | — | Log user engagement with an attraction |

### Admin

> All admin routes require `X-Admin-Key` header.

| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/admin/verify-key` | Verify admin access |
| GET | `/api/admin/stats` | Dashboard overview stats |
| GET/PUT/DELETE | `/api/admin/destinations/<id>` | Full destination CRUD |
| GET | `/api/admin/users` | User list |
| GET | `/api/admin/trips` | All generated trips |
| GET | `/api/admin/requests` | Destination submission queue |
| POST | `/api/admin/requests/<id>/approve` | Approve and create destination |
| POST | `/api/admin/requests/<id>/reject` | Reject a submission |

### Operations

> Requires `X-Admin-Key` header.

| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/ops/trigger-job` | Manually trigger background pipeline stages |
| GET | `/api/ops/job-status/:name` | Check execution history of background tasks |
| GET | `/api/ops/engine-config` | View core engine settings and environment status |
| GET | `/api/ops/summary` | Snapshot of pipeline health + metrics |
| GET | `/api/ops/live-metrics` | **SSE stream** — real-time latency, cache hits, agent health |

---

## 🗺️ Data Architecture

The engine uses a relational schema designed for geospatial travel data, with a focus on personalization and real-time operational feedback.

### Core Entities
- **Trips**: Stores generated itineraries, audit metadata, and quality scoring.
- **User Profiles**: Tracks travel preferences (budget, pace, interests), history, and AI scoring weights.
- **Destinations & Attractions**: Rich geospatial data enriched with H3 indexing, best visit times, and popularity scores.
- **Async Jobs**: Manages long-running AI generation and background pipeline tasks.

### Supporting Infrastructure
- **Feedback**: Collects user qualitative metrics.
- **Analytics**: Tracks system usage patterns (`analytics_event`) for engine optimization.
- **Geodata**: Reference data for countries, places, and hotel pricing.

---

## ⚙️ Configuration

### Environment Variables

| Variable | Required | Purpose |
|---|---|---|
| `DATABASE_URL` | ✅ | Supabase connection (use port `6543` for Transaction Mode) |
| `REDIS_URL` | ✅ | Redis URI for cache and Celery broker |
| `JWT_SECRET_KEY` | ✅ | Secret for signing JWT tokens |
| `ADMIN_ACCESS_KEY` | ✅ | Key for `/api/admin/*` and `/api/ops/*` |
| `GEMINI_API_KEY` | ⚠️ Optional | Enables itinerary polish and AI chat |
| `VALIDATION_STRICT` | ⚠️ Optional | Enables stricter itinerary validation |
| `VITE_API_URL` | Frontend | Backend base URL (default: `http://localhost:5000/api`) |

### Example `.env`

```env
DATABASE_URL=postgresql://user:pass@aws-region.pooler.supabase.com:6543/postgres
REDIS_URL=redis://localhost:6379/0
JWT_SECRET_KEY=your-super-secret-key
ADMIN_ACCESS_KEY=your-admin-key
GEMINI_API_KEY=your-gemini-api-key
```

---

## 🗃️ Populating the Database

The database initializes with PostGIS extensions only. You need to run data pipeline scripts before the itinerary endpoints work:

```bash
# 1. Ingest POIs from OpenStreetMap Overpass API
python backend/scripts/ingest_osm_data.py --city "Jaipur"
python backend/scripts/ingest_osm_data.py --city "Goa"
python backend/scripts/ingest_osm_data.py --city "Mumbai"

# 2. Enrich with Wikidata + Wikipedia metadata
python backend/scripts/enrich_attractions.py

# 3. Compute popularity and seasonal scores
python backend/scripts/score_attractions.py

# 4. Seed pricing data
python backend/scripts/sync_prices.py
```

> The demo frontend requests trips for **Jaipur**, **Goa**, and **Mumbai** by default. If your data uses sub-region names like `North Goa`, either update the frontend payload or add a matching `Goa` row to the destinations table.

---

## 🧪 Testing

```bash
pip install -r backend/tests/requirements-test.txt
python -m pytest backend/tests -q
```

The suite uses `TESTING=true` with SQLite in-memory, configured via `backend/tests/conftest.py`. Sample destination and attraction records are created automatically.

**Test coverage:**

| File | What it covers |
|---|---|
| `test_auth.py` | Registration, login, JWT validation |
| `test_api.py` | All endpoint contracts + status codes |
| `test_engine.py` | Pipeline step unit tests |
| `test_pipeline.py` | End-to-end itinerary generation |
| `test_validation.py` | ItineraryValidator edge cases |

---

## 🚢 Deployment

### Railway (Backend)

The `railway.toml` deploys using the included `Dockerfile` which runs Gunicorn on port `5000`. Health checks are configured on `/health`.

```bash
# Build and push manually
docker build -t altairgo-engine .
```

### Vercel (Frontend)

`vercel.json` rewrites frontend `/api/*` requests to `https://api.altairgo.in/api/*`.

```bash
cd dummy-frontend
npm run build
vercel --prod
```

### Docker Compose (Full Stack Local)

```bash
docker compose up --build
```

## 🧹 Production Cleanup Sprint (March 2026)

A comprehensive audit was conducted to prepare the codebase for production release. The core architecture has been validated as high-quality, with specific cleanup actions identified:

- **Routing**: Validated clean; no duplicate destination routes found in current frontend.
- **Data Strategy**: Shift from static files (`blogs.js`, `destinations.js`) to API-driven database storage is in progress.
- **Prompt Engineering**: Inline prompts in `GeminiService` are targeted for extraction into a template directory.
- **Environment**: All secrets moved to `.env` with `.env.example` placeholders.
- **Database**: Schema synchronized with `pgvector` support and audit fields.

For the detailed audit report and implementation roadmap, see the architecture documents in `docs/`.

---

## 🤝 Contributing

1. Fork the repository
2. Create your feature branch: `git checkout -b feature/my-feature`
3. Commit your changes: `git commit -m 'feat: add my feature'`
4. Push to the branch: `git push origin feature/my-feature`
5. Open a Pull Request

Please run `make lint` and `make test` before submitting.

---

## 📄 License

This project is licensed under the **MIT License** — see the [LICENSE](LICENSE) file for details.

---

<div align="center">

Built with ❤️ by the **AltairGO Intelligence** team

⭐ Star this repo if it helped you!

</div>
