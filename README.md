<div align="center">

<img src="https://img.shields.io/badge/AltairGO-Engine-22c55e?style=for-the-badge&logo=airplane&logoColor=white" alt="AltairGO Engine" />

# AltairGO Engine

**India-first AI travel intelligence backend. Deterministic 5-step itinerary pipeline, full booking automation, and day-of intelligence — powered by Flask + Celery + Gemini 2.0 Flash + Ollama fallback.**

[![Python 3.10+](https://img.shields.io/badge/Python-3.10+-3776AB?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![Flask 3.x](https://img.shields.io/badge/Flask-3.x-000000?style=flat-square&logo=flask&logoColor=white)](https://flask.palletsprojects.com)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-Supabase-336791?style=flat-square&logo=postgresql&logoColor=white)](https://supabase.com)
[![Redis](https://img.shields.io/badge/Redis-7-DC382D?style=flat-square&logo=redis&logoColor=white)](https://redis.io)
[![Celery](https://img.shields.io/badge/Celery-5-37814A?style=flat-square&logo=celery&logoColor=white)](https://docs.celeryq.dev)
[![Gemini 2.0](https://img.shields.io/badge/Gemini-2.0%20Flash-4285F4?style=flat-square&logo=google&logoColor=white)](https://deepmind.google/technologies/gemini/)
[![Tests](https://img.shields.io/badge/Tests-198%20passed-22c55e?style=flat-square)](backend/tests/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green?style=flat-square)](LICENSE)

<br/>

[Quick Start](#-quick-start) &bull; [Architecture](#-architecture) &bull; [API Reference](#-api-reference) &bull; [Features](#-traveler-features) &bull; [Deployment](#-deployment) &bull; [Roadmap](#-roadmap)

</div>

---

## Overview

AltairGO Engine is the **backend-only** core of the AltairGO travel intelligence platform. It exposes a REST API that powers the full travel lifecycle — from "where should I go?" discovery through to one-click booking and day-of briefings.

The frontend lives in a separate repository: [AltairGO-Platform](https://github.com/yash-dev007/AltairGO-Platform).

### Key Features

| Feature | Details |
|---|---|
| **Deterministic pipeline** | Filter → Cluster → Budget → Route → Assemble. AI adds polish, not structure |
| **AI fallback chain** | Gemini 2.0 Flash → Flash-Lite → Ollama (llama3.2:3b) → graceful unpolished fallback |
| **Full booking automation** | One-click hotel, flight, activity, restaurant, airport transfer, and daily cab bookings |
| **Pluggable booking providers** | `SimulatedProvider` (default) + `BookingComProvider` (real affiliate links) via registry pattern |
| **Discover & Compare** | Recommend by budget/season/traveler; side-by-side compare; budget estimator before generation |
| **Day-of intelligence** | Daily briefing: carry list, weather alerts, crowd warnings, confirmed bookings, emergency contacts |
| **Geospatial clustering** | H3 hexagonal cells (~5km) for walkable day plans |
| **198 passing tests** | Auth, API contracts, engine, pipeline, validation — SQLite in-memory, no external services |
| **Operational metrics** | `/api/metrics` (admin-only): polished rate, cache hit rate, gen latency, embedding coverage, worker liveness |
| **Structured error envelopes** | All routes return `{success, data?, error?, code}` — `ERR_VALIDATION`, `ERR_UNAUTHORIZED`, `ERR_NOT_FOUND`, `ERR_RATE_LIMIT`, `ERR_SERVER` |

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
|  2. ClusterEngine (H3)        |  |    → Flash-Lite → Ollama       |
|  3. BudgetAllocator           |  |  CacheService (Redis, SHA-256) |
|  4. RouteOptimizer            |  |  BookingProviders (registry)   |
|  5. Assembler                 |  |  ImageService (Wiki→Pexels)    |
+-------------------------------+  +--------------------------------+
|               Data & Infrastructure Layer                          |
|  PostgreSQL (Supabase) + PostGIS | Redis | Celery Beat + Worker    |
+-------------------------------------------------------------------+
```

### The 5-Step Itinerary Pipeline

```
POST /generate-itinerary
  → validate schema → SHA-256 cache check → create AsyncJob → Celery task

[1. FilterEngine]  Popularity ≥25, seasonal gate (≥40, default 70), traveler compat,
                   budget cap, accessibility, children, dietary, senior, min_age, POI closures

[2. ClusterEngine] H3 r7 hex grouping (~5km), NULL GPS guard, theme diversity

[3. BudgetAllocator] Tier splits, auto-demotion (<₹2000/₹1000 per person/day),
                     real hotel costs from HotelPrice, group discounts (5-9: 10%, 10+: 15%)

[4. RouteOptimizer] 15 km/h, sunrise priority, W→E ordering, queue_time buffers

[5. Assembler]     Day themes, document_checklist, daily_transport_guide,
                   pre_trip_info, local_events, weather_alerts

[GeminiService]    gemini-2.0-flash → (429) flash-lite → (429) Ollama llama3.2:3b
                   → graceful unpolished fallback (trip_title = "Trip to X")
                   Gunicorn + SSE timeouts set to 300s for Ollama generation
```

### Background Jobs (Celery Beat)

| Job | Schedule | Purpose |
|---|---|---|
| Destination validation | Daily 01:00 | AI-validates destination data quality |
| Score update | Daily 02:00 | Popularity + quality score blending |
| OSM ingestion | Sunday 03:00 | Fetch POIs from Overpass API |
| Cache warming | Daily 03:30 | Pre-warm Redis for top destinations |
| Trip quality scoring | Daily 04:30 | Score saved trips |
| Weather sync | Daily 05:30 | Open-Meteo → WeatherAlert rows |
| Price sync | Daily 06:00 + 18:00 | Hotel + flight pricing refresh |
| Affiliate health | Every 6h | Partner API health checks |
| Worker heartbeat | Every 5min | Worker availability |

---

## Traveler Features

### Filtering & Personalization
- Dietary restrictions (veg/vegan/halal)
- Accessibility filtering, children-friendly filter, senior pacing
- Min-age filtering per attraction; POI closure filtering
- Repeat-traveler dedup (skips already-visited attractions from last 10 trips)

### Budget Intelligence
- Auto-demotion: luxury → mid if <₹2,000/person/day; mid → budget if <₹1,000
- Real hotel costs from `HotelPrice` table (562 rows, 186 destinations × 3 tiers)
- Group discounts: 5-9 travelers → 10%; 10+ travelers → 15%
- Pre-generation budget estimator with accommodation/food/transport/activities breakdown

### Trip Lifecycle
- Full booking automation — hotel, flights, transfers, tickets, restaurants, cabs
- `approve` / `reject` individual bookings; `execute-all` approved in one click
- Self-arranged bookings (excluded from execute-all naturally)
- Expense tracker (planned vs actual per category)
- Activity swap with RouteOptimizer re-optimization
- Full trip editor: hotel swap, add/remove/edit/reorder activities, per-day notes
- Trip sharing — public read-only link (30-day Redis TTL, DB fallback)
- Trip variants: relaxed / balanced / intense
- Post-trip summary, reviews (stars + tag chips + comment)

### Discovery
- Recommendations scored by: popularity + seasonal fit + traveler type compat + budget + interests
- Semantic search via Gemini text embeddings (cosine sim 40% + score 60%)
- Month-by-month seasonal score matrix with Excellent/Good/Fair/Avoid verdicts
- Side-by-side destination comparison with ranked winner

---

## Quick Start

### Prerequisites

- Python 3.10+, Docker Desktop
- Supabase project (or local PostgreSQL)
- Gemini API key (optional — Ollama fallback works without it)

### Install & Run

```bash
git clone https://github.com/yash-dev007/AltairGO-Engine.git
cd AltairGO-Engine
python -m venv .venv && source .venv/bin/activate
pip install -r backend/requirements.txt
docker compose up -d redis
cp .env.example .env  # fill in DATABASE_URL, REDIS_URL, JWT_SECRET_KEY, ADMIN_ACCESS_KEY
python -m flask --app backend.app:create_app run --port 5000 --reload
```

Health check: `GET http://localhost:5000/health`

### Key `.env` Variables

```env
DATABASE_URL=postgresql://...   # direct connection, NOT pooler URL
REDIS_URL=redis://localhost:6379/0
JWT_SECRET_KEY=<min-32-chars>
ADMIN_ACCESS_KEY=<your-key>
GEMINI_API_KEY=<optional>
OLLAMA_URL=http://localhost:11434   # optional local AI fallback
DEV_EAGER=true                      # run Celery in-process (no worker needed)
```

---

## Project Structure

```
backend/
├── app.py                     # Flask factory + 15 blueprints
├── engine/                    # 5-step itinerary pipeline
├── routes/                    # 15 route blueprints
├── services/
│   ├── gemini_service.py      # Gemini → Flash-Lite → Ollama fallback chain
│   ├── cache_service.py       # SHA-256 Redis cache
│   └── booking_providers/     # Abstract registry + SimulatedProvider + BookingComProvider
├── agents/                    # AI agents (memory, QA, validator)
├── tasks/                     # Celery task implementations
└── tests/                     # 188 passed (SQLite in-memory)
```

---

## API Reference

### Core Endpoints

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| `GET` | `/health` | — | DB + Redis status |
| `POST` | `/auth/register` | — | Create account |
| `POST` | `/auth/login` | — | Login (5 fails → 15min lockout) |
| `POST` | `/generate-itinerary` | — | Start async job → `job_id` |
| `GET` | `/get-itinerary-status/<id>/stream` | — | SSE real-time status |
| `POST` | `/api/save-trip` | JWT | Save generated trip |
| `GET` | `/api/user/trips` | JWT | Paginated trip list |

### Booking Flow

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| `POST` | `/api/trip/<id>/booking-plan` | JWT | Generate booking plan |
| `POST` | `/api/booking/<id>/approve` | JWT | Approve one booking |
| `POST` | `/api/booking/<id>/reject` | JWT | Reject one booking |
| `POST` | `/api/trip/<id>/booking-plan/execute-all` | JWT | Execute all approved |
| `POST` | `/api/booking/<id>/cancel` | JWT | Cancel booking |

### Trip Editor

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| `GET` | `/api/trip/<id>/hotel-options` | JWT | Browse hotels |
| `PUT` | `/api/trip/<id>/hotel` | JWT | Swap hotel |
| `POST` | `/api/trip/<id>/day/<n>/activity/add` | JWT | Add activity |
| `DELETE` | `/api/trip/<id>/day/<n>/activity/remove` | JWT | Remove + re-optimize |
| `PUT` | `/api/trip/<id>/day/<n>/activity/edit` | JWT | Edit (`cost_override`, `user_note`) |
| `PUT` | `/api/trip/<id>/notes` | JWT | Save notes (`{ trip: "...", days: {...} }`) |

### Discovery

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/discover/recommend` | Ranked recommendations; `?q=` for semantic search |
| `GET` | `/api/discover/best-time/<dest_id>` | 12-month score matrix → `monthly_guide` |
| `GET` | `/api/discover/is-good-time?dest_id&month` | `good_to_go` bool + `best_month_instead` |
| `POST` | `/api/discover/estimate-budget` | Cost breakdown → `estimated_total_inr`, `breakdown` |
| `POST` | `/api/discover/compare` | Winner comparison → `destinations`, `recommendation.winner` |

### Admin & Ops

All require `X-Admin-Key` header or admin JWT.

```
GET  /api/ops/summary              — system health snapshot
GET  /api/ops/live-metrics         — SSE live feed (?token=<jwt>)
POST /api/ops/trigger-job          — fire Celery job by name
GET/POST /api/ops/engine-config    — runtime engine settings
GET/POST /api/admin/feature-flags  — feature flag CRUD
POST /api/webhooks/<provider>      — booking webhook (HMAC-SHA256)
```

---

## Testing

```bash
python -m pytest backend/tests/ -q --tb=short   # 198 passed, 1 skipped
python -m pytest backend/tests/ -k "test_generate" -q   # filter by name
```

Runs against SQLite in-memory + memory:// rate limiter (`TESTING=true`). No external services required.

---

## Roadmap

**Current status (2026-04-21):** Production-ready core. Hardening sprints (Track A visual identity, Track B admin console, Track C error envelopes) complete. 198/198 tests green.

**Next phase — Quality-First Strategic Roadmap** — detailed plan in [`docs/superpowers/plans/2026-04-21-quality-first-strategic-roadmap.md`](docs/superpowers/plans/2026-04-21-quality-first-strategic-roadmap.md).

**Phase 0 (4–6 weeks):** Build eval infrastructure — golden dataset of 50 canonical prompts, 10-dimension quality harness (factual accuracy, closed-days violations, route sensibility, budget accuracy, pacing, personalization fidelity, narrative polish, safety info, diversity, latency), CI quality gates, A/B prompt harness, polish-failure detector, schema-drift CI, funnel instrumentation, prompt-injection hardening.

**Phase 1 (6–10 weeks):** Quality lifts — polish reliability (kill Gemini 429 cliff), embedding generation on 190 destinations + 11,539 attractions, attraction data enrichment (closed_days, opening_hours, accessibility), pacing heuristics, route optimizer upgrades, prompt engineering cycles via A/B harness, schema reconciliation.

**Phase 3 before Phase 2:** Monetization (Booking.com + flight + activity affiliates, pricing tiers via Razorpay) takes precedence over Personalization. Personalization without repeat users is unlearnable; BD runs in parallel during Phase 1.

**Phase 4–5:** Programmatic SEO (15,200 long-tail pages), sharing virality, mobile conversion, day-of intelligence, geographic expansion (Sri Lanka, Bhutan, Nepal first).

---

## Deployment

```bash
docker compose up --build
# Services: redis, app (Gunicorn :5000, 300s timeout), worker (--pool=solo), beat (RedBeatScheduler)
```

**Production notes:**
- Use direct Supabase connection — pooler URL causes "Tenant not found"
- Schema changes: use `mcp__claude_ai_Supabase__apply_migration` with targeted DDL, never `flask db upgrade`
- Ollama optional but recommended: `ollama serve && ollama pull llama3.2:3b`

---

## License

MIT — see [LICENSE](LICENSE) for details.

---

<div align="center">

Built by **[yash-dev007](https://github.com/yash-dev007)**

</div>
