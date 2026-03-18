# AltairGO Engine — CLAUDE.md

> Complete technical reference for Claude Code. Always read this before making changes.

---

## 1. Project Purpose

**AltairGO Travel Intelligence** is a production-grade, India-first AI travel platform that takes a traveler from "I don't know where to go" all the way through to "everything is booked." It generates AI-powered day-by-day itineraries with real cost breakdowns, automates hotel/flight/activity/restaurant bookings with a single click, and provides day-of intelligence (weather alerts, crowd warnings, local events, daily briefings).

**Stack:** Python Flask + Celery + SQLAlchemy (PostgreSQL/Supabase) + Redis + Gemini 2.0 Flash + React 19 (Vite) + Tailwind CSS v4

**DB:** Supabase PostgreSQL (project ID: `amdtitsokkounoscgova`, region: ap-southeast-2)

**Schema migrations:** Managed via **Supabase MCP** (`mcp__claude_ai_Supabase__apply_migration`). Do NOT use `flask db upgrade` against production — autogenerate tries to drop PostGIS system tables. Write targeted `ALTER TABLE` / `CREATE TABLE IF NOT EXISTS` SQL instead.

---

## 2. Repository Structure

```
AltairGO-Engine-main/
├── backend/
│   ├── app.py                      # Flask factory + all 17 blueprint registrations
│   ├── database.py                 # SQLAlchemy db + Celery-safe SessionLocal
│   ├── extensions.py               # Rate limiter — memory:// when TESTING or DEV_EAGER
│   ├── models.py                   # 28+ SQLAlchemy models (see §6)
│   ├── celery_config.py            # Celery broker + beat schedule; DEV_EAGER uses SQLite broker
│   ├── celery_tasks.py             # Task wrappers
│   ├── validation.py               # ItineraryValidator
│   ├── schemas.py                  # Marshmallow schemas (BaseSchema unknown=EXCLUDE)
│   ├── constants.py                # All magic numbers / config constants (centralised)
│   ├── request_validation.py       # load_request_json(schema) helper
│   ├── engine/
│   │   ├── orchestrator.py         # TripGenerationOrchestrator — main coordinator
│   │   ├── filter_engine.py        # 6+ filter steps incl. dietary/accessibility/senior/min_age
│   │   ├── cluster_engine.py       # H3 geospatial day grouping + theme diversity
│   │   ├── budget_allocator.py     # Tier splits + auto-demotion + real hotel cost + group discounts
│   │   ├── route_optimizer.py      # Time scheduling + queue buffers + activity enrichment output
│   │   ├── assembler.py            # Final JSON + document_checklist + daily_transport_guide
│   │   └── simulation_data.py      # Test data fixtures
│   ├── routes/
│   │   ├── trips.py                # /generate-itinerary, /get-itinerary-status, /save-trip, /api/user/trips
│   │   ├── auth.py                 # /auth/* — register/login/refresh/me + brute-force lockout
│   │   ├── admin.py                # Admin CRUD, verify-key
│   │   ├── destinations.py         # Destination browsing, budget calculator
│   │   ├── ops.py                  # Job trigger, engine config (whitelist of 10 keys)
│   │   ├── dashboard.py            # /api/ops/summary (authoritative), SSE live-metrics
│   │   ├── signals.py              # Behavioral signal tracking
│   │   ├── bookings.py             # Full booking automation + execute-all + cancel + dashboard
│   │   ├── expenses.py             # Expense tracker — planned vs actual
│   │   ├── discover.py             # Discovery engine — recommend/best-time/compare/estimate
│   │   ├── trip_tools.py           # Readiness check, daily briefing, activity swap, next-trip ideas
│   │   ├── trip_editor.py          # Full plan editing — hotel/activity/notes/booking customisation
│   │   ├── profile.py              # GET/PUT /api/user/profile, DELETE /api/user/account
│   │   ├── sharing.py              # POST/DELETE /api/trip/<id>/share, GET /api/shared/<token>
│   │   └── search.py               # GET /api/search?q=&type=&limit=
│   ├── services/
│   │   ├── gemini_service.py       # GeminiService — Gemini 2.0 Flash + fallback + _merge_polish_updates
│   │   ├── metrics_service.py      # Redis metrics helpers; gen_times list 7-day TTL
│   │   ├── cache_service.py        # SHA-256 cache keys + env-var TTLs
│   │   └── image_service.py        # Multi-source image fetching
│   ├── agents/
│   │   ├── destination_validator_agent.py
│   │   ├── itinerary_qa_agent.py
│   │   ├── memory_agent.py
│   │   ├── token_optimizer.py
│   │   ├── mcp_context_agent.py
│   │   └── web_scraper_agent.py
│   ├── tasks/
│   │   ├── score_updater.py        # update_scores() + update_scores_from_quality()
│   │   ├── cache_warmer.py
│   │   ├── quality_scorer.py
│   │   ├── affiliate_health.py
│   │   └── weather_sync.py         # Open-Meteo → WeatherAlert rows
│   ├── scripts/                    # Data ingestion & enrichment (OSM, Wikidata, pricing, H3)
│   ├── utils/
│   │   ├── auth.py                 # @require_admin decorator
│   │   └── helpers.py
│   └── tests/                      # 188 passed, 1 skipped — run: python -m pytest backend/tests/ -q
├── dummy-frontend/                 # React 19 traveler-facing + admin UI (see §12)
│   ├── package.json                # recharts + react-hot-toast + framer-motion + lucide-react
│   ├── vite.config.js              # Dev proxy to :5000 + manualChunks code splitting
│   └── src/
│       ├── App.jsx                 # Full router — public / protected / admin routes
│       ├── contexts/AuthContext.jsx # Unified traveler + admin auth; tokens: ag_token / ag_admin_token
│       ├── services/api.js         # 50+ API functions; ag:unauthorized event dispatch
│       ├── components/ui/index.jsx # Button/Card/Input/Badge/Modal/Spinner/ProgressBar/StatCard
│       ├── components/layout/      # TravelerLayout (sticky glass navbar) + AdminLayout (sidebar)
│       └── pages/                  # 14 traveler pages + 6 admin pages (see §12)
├── migrations/                     # Flask-Migrate init — do NOT run against Supabase prod
├── docker-compose.yml
├── Dockerfile
├── gunicorn.conf.py
├── Makefile
└── .env                            # Contains DEV_EAGER=true for local dev without Docker
```

---

## 3. Environment Variables

### Required in production
```bash
DATABASE_URL        # PostgreSQL (Supabase) connection string
REDIS_URL           # Redis for Celery broker + rate limiting + metrics + share token cache
JWT_SECRET_KEY      # Min 32 chars
ADMIN_ACCESS_KEY    # Admin portal API key
GEMINI_API_KEY      # Google Gemini API key
```

### Optional / defaults
```bash
LOG_LEVEL           # default: INFO
VALIDATION_STRICT   # default: false
ALLOWED_ORIGINS     # default: https://altairgo.in,http://localhost:5173
GEMINI_MODEL        # default: gemini-2.0-flash
FLASK_ENV           # production | development | testing
THEME_THRESHOLD     # default: 0.20 (Assembler day-theme overlap threshold)
```

### Local dev only
```bash
DEV_EAGER=true      # Celery uses SQLite in-memory broker + task_always_eager=True
                    # Extensions uses memory:// for rate limiter
                    # Result: full itinerary generation works without a Celery worker process
TESTING=true        # Same as DEV_EAGER but also switches DB to SQLite in-memory
```

---

## 4. Flask Application Factory (`backend/app.py`)

`create_app(test_config=None)` — main factory. Blueprint registration order matters (first wins on duplicate routes):

1. `trips_bp`
2. `admin_bp`
3. `auth_bp`
4. `destinations_bp`
5. `dashboard_bp` ← **authoritative for `/api/ops/summary`**
6. `signals_bp`
7. `ops_bp`
8. `bookings_bp`
9. `expenses_bp`
10. `discover_bp`
11. `trip_tools_bp`
12. `trip_editor_bp`
13. `profile_bp`
14. `sharing_bp`
15. `search_bp`

**DEV_EAGER wiring in app.py:**
```python
_eager = bool(app.config.get("TESTING")) or os.getenv("DEV_EAGER","false").lower() in ("1","true","yes")
celery_app.conf.task_always_eager = _eager
celery_app.conf.task_eager_propagates = _eager
```

---

## 5. Database Layer

- `db = SQLAlchemy()` — Flask app-context sessions (routes)
- `SessionLocal()` — Standalone factory for Celery workers
- Pool: `pool_pre_ping=True`, `pool_recycle=300`
- Tests: SQLite in-memory when `TESTING=true`
- **Prod migrations:** Use Supabase MCP `apply_migration` — never `flask db upgrade` (autogenerate breaks on PostGIS tables)

---

## 6. SQLAlchemy Models (`backend/models.py`)

### Core Models
| Model | Key Fields | Notes |
|-------|-----------|-------|
| `User` | id, name, email, password_hash, created_at | |
| `UserProfile` | user_id, preferences (JSON), embedding | GET/PUT via profile_bp |
| `Country` | id, name, code, currency, image | |
| `State` | id, name, image, country_id | FK → Country |
| `Destination` | 40+ fields: name, slug, lat/lng, h3_index_r7, popularity_score, compatible_traveler_types, budget_category, seasonal_score, rating, vibe_tags, image | `state_id` FK (no ORM relationship — manual join in search.py) |
| `Attraction` | name, type, entry_cost_min/max/child, rating, avg_visit_duration_hours, best_visit_time_hour, h3_index_r7/r9, popularity_score, compatible_traveler_types, seasonal_score, osm_id, wikidata_id, **opening_hours, closed_days, requires_advance_booking, accessibility_level, dietary_options, difficulty_level, is_photo_spot, best_photo_hour, queue_time_minutes, dress_code, guide_available, min_age** | New traveler-experience fields added via Supabase migration |
| `HotelPrice` | destination_id, hotel_name, star_rating, category, price_per_night_min/max, booking_url, partner, availability_score | |
| `FlightRoute` | origin_iata, destination_iata, avg_one_way_inr, avg_return_inr, duration_minutes, transport_type | |
| `Trip` | user_id, trip_title, budget, duration, travelers, style, traveler_type, start_date, itinerary_json, total_cost, quality_score, **user_notes (JSON), is_customized** | user_notes stores `_share_token` key for sharing |
| `AsyncJob` | id (UUID), user_id, status (queued\|processing\|completed\|failed), payload, result, error_message | |
| `AttractionSignal` | attraction_id, user_id, event_type, traveler_type, trip_style, budget_tier, session_id | |
| `AnalyticsEvent` | event_type, user_id, payload (JSON) | |
| `EngineSetting` | key, value, description | Runtime-changeable config |
| `DestinationRequest` | name, description, cost, tag, status | |
| `Feedback` | user_id, itinerary_id, poi_id, rating, corrections | |
| `FeatureFlag` | flag_key, is_active, traffic_pct | |
| `DataSourceLog` | source_name, event_type, records_processed, status | |
| `POIClosure` | attraction_id, closure_reason, start_date, end_date | |
| `CurrencyRate` | base_currency, target_currency, rate, snapshot_date | |

### New Models (added via Supabase MCP migration)
| Model | Key Fields | Notes |
|-------|-----------|-------|
| `WeatherAlert` | destination_id, alert_date, alert_type, severity (low/medium/high/extreme), description, rainy_day_alternatives (JSON) | Populated by weather_sync task |
| `TripPermissionRequest` | trip_id, user_id, status, requested_items (JSON), user_response (JSON) | Pre-booking approval screen |
| `Booking` | trip_id, user_id, booking_type, item_name, item_details (JSON), cost_inr, status (pending/approved/rejected/booked/failed/cancelled/self_arranged), user_approved, booking_ref, booking_url, partner_name, notes, executed_at | Full booking lifecycle |
| `DestinationInfo` | destination_id (unique), visa_required, visa_info, travel_advisory_level, vaccinations_recommended, water_safety, altitude_sickness_risk, tipping_guide, hidden_fees, emergency_contacts, local_phrases, connectivity_guide, currency_tips, dress_code_general, best_hospitals, nearest_embassy | Injected as pre_trip_info in itinerary |
| `LocalEvent` | destination_id, name, description, event_type, start_date, end_date, impact (positive/neutral/avoid), tips | Injected as local_events in itinerary |
| `ExpenseEntry` | trip_id, user_id, category, description, amount_inr, trip_day | Tracked vs planned budget |

---

## 7. The Itinerary Generation Pipeline

### Trigger flow
```
POST /generate-itinerary
  → Validate GenerateItinerarySchema
    selected_destinations = [{"name": "Jaipur"}]  ← DestinationChoiceSchema (not plain strings)
    travel_month = "12"                             ← string, not int
  → Check cache (SHA-256 key)
  → Create AsyncJob (status=queued)
  → generate_itinerary_job.delay(job_id)
    DEV_EAGER=true → runs synchronously, returns completed immediately
  → Return {job_id, status} [202]

GET /get-itinerary-status/<job_id>
  → {job_id, status, result?, error?}
```

### 5-Step Deterministic Pipeline
1. **FilterEngine** — Popularity ≥25, traveler compat, seasonal gate (≥40, default 70), budget cap, category max 2, accessibility, children, dietary, senior (no strenuous), min_age
2. **ClusterEngine** — H3 r7 hex grouping (~5km), NULL GPS guard (0.0,0.0 = missing), theme diversity across days, top N hexes for N days
3. **BudgetAllocator** — Tier splits (budget/mid/luxury), auto-demotion (<2000/1000 INR per person per day), real hotel cost from HotelPrice table, group discounts (5-9: 10%, 10+: 15%)
4. **RouteOptimizer** — 15 km/h urban speed, sunrise priority, W→E ordering, queue_time_minutes added to timing, enriched output (difficulty, is_photo_spot, photo_tip, dress_code, guide_available, min_age, queue_wait_minutes)
5. **Assembler** — Day themes (20% overlap threshold), document_checklist (personalised), daily_transport_guide (per-day cab mode + cost)

### Post-Assembly: Gemini Polish
- Model: `gemini-2.0-flash` → fallback `gemini-2.0-flash-lite`, 3 retries, 15s timeout
- Call 1: `polish_itinerary_text()` — rewrites descriptions, why_this_fits, local_secret, how_to_reach (never changes names/costs)
- Call 2: Meta — trip_title, smart_insights (3), packing_tips (3-5)
- Blocked/failed → graceful fallback to unpolished itinerary

### Itinerary JSON output shape
```json
{
  "trip_title", "total_cost", "cost_breakdown",
  "itinerary": [{"day", "location", "theme", "pacing_level", "activities", "accommodation", "day_total"}],
  "smart_insights": [], "packing_tips": [],
  "travel_between_cities": [],
  "document_checklist": [{"item", "category", "required"}],
  "daily_transport_guide": [{"day", "mode", "estimated_cost_inr", "notes"}],
  "pre_trip_info": {"visa_info", "emergency_contacts", "water_safety", ...},
  "local_events": [{"name", "impact", "dates", "tips"}],
  "traveler_profile": {"dietary", "accessibility", "children", "senior"}
}
```

---

## 8. Authentication & Authorization

### Brute-Force Lockout (auth.py)
- Redis key: `login:fail:<email>` — incremented on each failed attempt
- 5 failures → 429 for 15 minutes (`_LOCKOUT_WINDOW = 900`)
- Cleared on successful login
- Degrades silently if Redis unavailable

### JWT Flow
- `POST /auth/register` → `{token, refresh_token, user}` [201]
- `POST /auth/login` → same [200] — checks lockout first
- `POST /auth/refresh` [JWT refresh] → `{token}` [200]
- `GET /auth/me` [JWT] → `{id, name, email}` [200]
- Access: 1hr | Refresh: 30d

### Admin Auth
- `X-Admin-Key` header OR JWT with `role="admin"` claim
- Token issued via `POST /api/admin/verify-key {key}`

### Frontend Token Keys
- Traveler: `ag_token` + `ag_refresh_token` in localStorage
- Admin: `ag_admin_token` in localStorage
- Expired → `ag:unauthorized` CustomEvent dispatched → AuthContext clears state

---

## 9. All API Endpoints

### Auth
| Method | Path | Rate Limit | Description |
|--------|------|-----------|-------------|
| POST | `/auth/register` | 5/min | Register |
| POST | `/auth/login` | 10/min | Login (lockout-protected) |
| POST | `/auth/refresh` | 30/min | New access token |
| GET | `/auth/me` | — | Current user |

### Profile
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/api/user/profile` | JWT | Get profile + preferences |
| PUT | `/api/user/profile` | JWT | Update name + preferences (merged) |
| DELETE | `/api/user/account` | JWT | GDPR anonymise (requires password) |

### Search
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/search?q=&type=all\|destination\|country&limit=` | Full-text search; sorted exact→prefix→contains |

### Trips
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/generate-itinerary` | — | Create async job (schema: `selected_destinations=[{name}]`, `travel_month` as string) |
| GET | `/get-itinerary-status/<job_id>` | — | Poll status |
| POST | `/api/save-trip` | JWT | Save trip |
| GET | `/get-trip/<trip_id>` | JWT | Fetch trip |
| GET | `/api/user/trips` | JWT | Paginated list |
| POST | `/api/trip/<id>/variants` | JWT | relaxed/balanced/intense variants |

### Sharing
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/api/trip/<id>/share` | JWT | Create share token (Redis TTL 30d + Trip.user_notes._share_token) |
| DELETE | `/api/trip/<id>/share` | JWT | Revoke share link |
| GET | `/api/shared/<token>` | — | Public read-only itinerary view |

### Destinations
| Method | Path | Description |
|--------|------|-------------|
| GET | `/countries` | All countries |
| GET | `/destinations` | Paginated + filterable |
| GET | `/destinations/<id>` | Detail + attractions |
| POST | `/api/destination-requests` | User suggestion |
| POST | `/api/budget-calculator` | Estimate budget |

### Discovery
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/discover/recommend` | AI recommendations (scored by budget/season/type/interests) |
| GET | `/api/discover/best-time/<dest_id>` | Month matrix + top 3 months |
| GET | `/api/discover/is-good-time?dest_id&month` | Quick verdict |
| POST | `/api/discover/estimate-budget` | Full breakdown before committing |
| POST | `/api/discover/compare` | Side-by-side comparison with winner |

### Bookings
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/api/trip/<id>/booking-plan` | JWT | Full booking plan |
| POST | `/api/booking/<id>/approve` | JWT | Approve one booking |
| POST | `/api/booking/<id>/reject` | JWT | Reject one booking |
| POST | `/api/trip/<id>/booking-plan/execute-all` | JWT | Execute ALL approved (skips self_arranged) |
| POST | `/api/booking/<id>/cancel` | JWT | Cancel booking |
| GET | `/api/trip/<id>/bookings` | JWT | Dashboard grouped by type |
| PUT | `/api/booking/<id>/customize` | JWT | Edit booking or mark self_arranged |
| POST | `/api/trip/<id>/booking-plan/add-custom` | JWT | Add self-arranged booking |

### Expenses
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/api/trip/<id>/expense` | JWT | Log actual spending |
| GET | `/api/trip/<id>/expenses` | JWT | Planned vs actual per category |
| DELETE | `/api/expense/<id>` | JWT | Delete expense entry |

### Trip Tools
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/api/trip/<id>/readiness` | JWT | 0-100% score + checklist |
| GET | `/api/trip/<id>/daily-briefing/<day>` | JWT | Full day-of briefing |
| POST | `/api/trip/<id>/activity/swap` | JWT | Swap activity + re-optimize |
| GET | `/api/trip/<id>/next-trip-ideas` | JWT | Post-trip destination ideas |

### Trip Editor
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/api/trip/<id>/hotel-options` | JWT | Browse hotels by category/price |
| PUT | `/api/trip/<id>/hotel` | JWT | Swap hotel (DB id or custom_hotel_name) |
| POST | `/api/trip/<id>/day/<n>/activity/add` | JWT | Add activity (DB or custom) |
| DELETE | `/api/trip/<id>/day/<n>/activity/remove` | JWT | Remove + re-optimize |
| PUT | `/api/trip/<id>/day/<n>/activity/edit` | JWT | Edit cost/note/time/description |
| PUT | `/api/trip/<id>/day/<n>/reorder` | JWT | Manual reorder + re-optimize |
| PUT | `/api/trip/<id>/notes` | JWT | Save trip + per-day notes |

### Admin
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/api/admin/verify-key` | — | Get admin JWT |
| GET | `/api/admin/stats` | Admin | Aggregate counts |
| GET/POST | `/api/admin/destinations` | Admin | List / create |
| PUT/DELETE | `/api/admin/destinations/<id>` | Admin | Update / delete |
| GET/POST | `/api/admin/users` | Admin | User management |
| GET/DELETE | `/api/admin/trips` | Admin | Trip management |
| GET | `/api/admin/requests` | Admin | Destination requests |
| POST | `/api/admin/requests/<id>/approve` | Admin | Approve |
| POST | `/api/admin/requests/<id>/reject` | Admin | Reject |

### Ops (Admin)
| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/ops/trigger-job` | Fire Celery job by name |
| GET | `/api/ops/job-status/<task_id>` | Check task |
| POST | `/api/ops/trigger-agent` | Fire AI agent |
| GET/POST | `/api/ops/engine-config` | Read/update EngineSetting (10 whitelisted keys) |
| GET | `/api/ops/summary` | Full dashboard stats |
| GET | `/api/ops/live-metrics` | SSE stream (`?token=<jwt>`) |

### Signals + Health
| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/signal` | Log behavioral signal |
| GET | `/health` | DB + Redis status |

---

## 10. Celery & Background Jobs

### DEV_EAGER mode (local dev)
When `DEV_EAGER=true`: broker = `sqla+sqlite:///:memory:`, `task_always_eager=True` → tasks run synchronously in the HTTP request. No worker process needed. Itinerary generation completes in ~1s.

### Production Beat Schedule
| Task | Schedule | Purpose |
|------|----------|---------|
| `run_osm_ingestion` | Sunday 03:00 | Fetch POIs from Overpass API |
| `run_enrichment` | Monday 04:00 | Wikidata + Wikipedia |
| `run_scoring` | 1st/month 05:00 | Popularity recalculation |
| `run_price_sync` | Daily 06:00 & 18:00 | Hotel/flight pricing |
| `run_score_update` | Daily 02:00 | update_scores() + update_scores_from_quality() |
| `run_destination_validation` | Daily 01:00 | AI destination request validation |
| `run_cache_warm` | Daily 03:30 | Pre-warm Redis |
| `run_affiliate_health` | Every 6h | Partner API health |
| `run_quality_scoring` | Daily 04:30 | Quality scoring of trips |
| `run_weather_sync` | Daily 05:30 | Open-Meteo → WeatherAlert |
| `heartbeat` | Every 5min | Worker availability |

---

## 11. AI Agents

| Agent | Trigger | Purpose |
|-------|---------|---------|
| `destination_validator_agent` | Daily / manual | AI validation of pending destination requests |
| `itinerary_qa_agent` | Post-generation | Reviews itinerary for quality issues |
| `memory_agent` | Per request | UserProfile.preferences + signal history → excluded_types + preferred_types |
| `token_optimizer` | Pre-Gemini | Estimates char reduction |
| `mcp_context_agent` | Per request | Fetches live destination context |
| `web_scraper_agent` | On demand | Scrapes additional attraction data |

Triggered via `POST /api/ops/trigger-agent {agent_key}` (admin only).

---

## 12. Frontend (`dummy-frontend/`)

**Tech:** React 19, Vite 7, Tailwind CSS v4 (via `@tailwindcss/vite`), Framer Motion, Lucide React, React Router v7, Recharts, React Hot Toast

**Dev server:** `npm run dev` → `http://localhost:5173`

**Proxy:** All `/api/*`, `/auth/*`, `/generate-*`, `/get-trip`, `/countries`, `/destinations` → `http://127.0.0.1:5000`

**Code splitting:** vendor-react / vendor-charts / vendor-motion / vendor-icons / vendor-toast

### Auth tokens (localStorage)
- `ag_token` — traveler JWT
- `ag_refresh_token` — traveler refresh
- `ag_admin_token` — admin JWT
- Expired: `ag:unauthorized` CustomEvent → AuthContext auto-logout

### Routes
| Path | Page | Auth |
|------|------|------|
| `/` | Landing | Public |
| `/discover` | Discover | Public |
| `/destination/:id` | DestinationDetail | Public |
| `/login` | Login | Public only |
| `/register` | Register | Public only |
| `/trip/shared/:token` | SharedTrip | Public |
| `/planner/*` | Planner (5-step wizard + generating) | Protected |
| `/trips` | MyTrips | Protected |
| `/trip/:id` | TripDetail (5 tabs) | Protected |
| `/trip/:id/bookings` | Bookings | Protected |
| `/trip/:id/expenses` | Expenses | Protected |
| `/trip/:id/briefing/:day` | DailyBriefing | Protected |
| `/profile` | Profile | Protected |
| `/admin/login` | AdminLogin | Public |
| `/admin` | AdminDashboard | Admin |
| `/admin/data` | AdminData | Admin |
| `/admin/users` | AdminUsers | Admin |
| `/admin/agents` | AdminAgents | Admin |
| `/admin/settings` | AdminSettings | Admin |

### UI System (`src/components/ui/index.jsx`)
Button (primary/secondary/ghost/danger + loading), Card, Input, Select, Textarea, Badge (status colors), Spinner, Modal (portal + framer-motion), ProgressBar, EmptyState, StatCard

### Design Language
- Primary: `#4F46E5` (indigo-600) + violet gradient
- Accent: `#F59E0B` (amber-500 / gold)
- Background: `#F8FAFC` (slate-50)
- Cards: white + `shadow-card`
- Currency: `₹{n.toLocaleString('en-IN')}`
- Dates: `Intl.DateTimeFormat('en-IN', {...})`

---

## 13. Critical Business Logic & Guards

### Key Schema Gotchas
- `selected_destinations` is `List[DestinationChoiceSchema]` → send `[{"name": "Jaipur"}]` not `["Jaipur"]`
- `travel_month` is `String` → send `"12"` not `12`

### Activity Proxy Pattern (trip_tools.py, trip_editor.py)
RouteOptimizer expects SQLAlchemy model objects. When re-optimizing after edits, activities are plain dicts. Wrap with:
```python
type("_Proxy", (), {"attr": value, ...})()
```

### Safe Itinerary Mutation
```python
itinerary = copy.deepcopy(trip.itinerary_json or {})
# ... modify ...
trip.itinerary_json = itinerary
trip.is_customized = 1
db.session.commit()
```

### Trip Sharing (sharing.py)
- Token stored in `trip.user_notes["_share_token"]`
- Redis `share:<token>` → trip_id (30-day TTL) for O(1) lookup
- Falls back to DB scan when Redis cold

### Login Lockout (auth.py)
- Redis `login:fail:<email>` — 5 attempts → 429 for 15 min
- Degrades silently if Redis down

### Booking execute-all
- Filters `status="approved"` only — naturally excludes `self_arranged` bookings

### Budget Auto-Demotion
```python
daily_per_person = total_budget / (num_days × travelers)
if tier == 'luxury' and daily_per_person < 2000: tier = 'mid'
if tier == 'mid'    and daily_per_person < 1000: tier = 'budget'
```

### H3 NULL Guards
- Missing `h3_index_r7` → compute on-the-fly from lat/lng
- `(0.0, 0.0)` → treated as missing GPS

### Seasonal Score Default
- Missing month → defaults to **70**

### Cache Keys
SHA-256 of: origin_city, destination_names (sorted), budget, duration, travelers, style, traveler_type, travel_month, start_date, date_type, use_engine, dietary, accessibility, children, interests

### Connection Pool Note
After a failed SQL query, the connection enters an aborted-transaction state. With `pool_pre_ping=True` + `pool_recycle=300` this self-heals, but if you run migrations while Flask is live, **restart Flask** to flush stale connections.

---

## 14. Marshmallow Schemas

| Schema | Key Fields |
|--------|-----------|
| `GenerateItinerarySchema` | destination_country, start_city (required); selected_destinations (List[DestinationChoiceSchema]); budget (min 500); duration (1–21); travelers (1–20); style, traveler_type, date_type, start_date, travel_month (str), interests, use_engine, **dietary_restrictions, accessibility, children_count, senior_count, children_min_age, special_occasion, fitness_level, from_city_iata** |
| `DestinationChoiceSchema` | id (optional), name (required), estimated_cost_per_day (optional) |
| `SaveTripSchema` | itinerary_json (required), trip_title, budget, duration |
| `RegisterSchema` | name, email, password (min 12 chars) |
| `LoginSchema` | email, password |
| `DestinationRequestSchema` | name, description, cost, tag |
| `CalculateBudgetSchema` | selected_destinations, duration |
| `AttractionSignalSchema` | attraction_id, event_type, session_id, context |

All schemas extend `BaseSchema` with `unknown = EXCLUDE`.

---

## 15. Test Suite

**Run:** `python -m pytest backend/tests/ -q --tb=short`
**Result:** 188 passed, 1 skipped (rate limit test skipped when `RATELIMIT_ENABLED=False`)

**Test config uses:**
- `TESTING=true` → SQLite in-memory DB + SQLite Celery broker + memory:// Redis
- `DEV_EAGER` is NOT set in tests (TESTING alone triggers eager mode)
- `RATELIMIT_ENABLED=False`

---

## 16. Local Dev — How to Start

```bash
# 1. Ensure Redis is running (Docker Desktop or native)
docker compose up -d redis   # OR redis-server

# 2. Start Flask backend (DEV_EAGER=true in .env — no Celery worker needed)
.venv/Scripts/python.exe -m flask --app backend.app:create_app run --port 5000 --reload

# 3. Start Vite frontend
cd dummy-frontend && npm run dev

# Access: http://localhost:5173
# API health: http://127.0.0.1:5000/health
```

**DEV_EAGER=true** in `.env` means: Celery tasks run synchronously inside the Flask process. The `POST /generate-itinerary` endpoint blocks until the itinerary is complete (~1-3s) and returns `status: completed` immediately. No separate worker or beat process needed.

---

## 17. Deployment (Production)

### Docker Compose Services
- `postgresql` — PostgreSQL (if self-hosted; prod uses Supabase)
- `redis` — Celery broker + metrics + share cache
- `app` — Flask via Gunicorn (port 5000), CPU-count workers, 120s timeout
- `worker` — Celery worker (`--pool=solo` on Windows)
- `beat` — Celery Beat (RedBeatScheduler)

### Database
- Production: Supabase PostgreSQL (project `amdtitsokkounoscgova`)
- Migrations: use `mcp__claude_ai_Supabase__apply_migration` with targeted DDL
- Never run `flask db upgrade` in production (breaks on PostGIS tables)

### Frontend
```bash
npm run build   # outputs to dist/ — serve via nginx or CDN
```

---

## 18. Architecture Patterns

1. **Async-first generation** — Celery worker runs pipeline; HTTP returns job_id immediately (or synchronously in DEV_EAGER)
2. **Cache-first** — SHA-256 Redis cache check before pipeline; 7-day TTL
3. **Graceful degradation** — Gemini failure → unpolished itinerary; Redis down → rate limiting disabled (swallow_errors=True)
4. **Dual session** — `db.session` in routes; `SessionLocal()` in Celery workers
5. **Behavioral feedback loop** — AttractionSignal → score_updater → popularity scores
6. **Runtime config** — EngineSetting table, changeable without redeploy
7. **Dual admin auth** — X-Admin-Key header OR admin JWT
8. **Blueprint order** — dashboard_bp before ops_bp wins `/api/ops/summary`
9. **Activity proxy** — `type("_Proxy", (), {...})()` wraps dicts as model-like objects for RouteOptimizer re-optimization after edits
10. **Safe mutation** — `copy.deepcopy(trip.itinerary_json)` before any edit, then reassign entire field
11. **Schema management** — Supabase MCP for DDL (avoids PostGIS autogenerate conflicts)
