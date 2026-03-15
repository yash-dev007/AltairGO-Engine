# AltairGO Intelligence — Complete Test Suite Specification
> Send this to your AI builder alongside the pytest files. This document explains every decision, contract, and implementation requirement needed to make all tests pass.

---

## OVERVIEW

### Test File Map

| File | Scope | Test Count | Type |
|---|---|---|---|
| `conftest.py` | Shared fixtures | — | Infrastructure |
| `test_auth.py` | `/auth/*` endpoints | 15 tests | Integration |
| `test_trips.py` | Trip generate/save/retrieve | 16 tests | Integration |
| `test_destinations.py` | Destinations, countries, budget | 14 tests | Integration |
| `test_admin.py` | Admin panel endpoints | 17 tests | Integration |
| `test_engine.py` | 5-phase engine unit tests | 36 tests | Unit |
| `test_pipeline.py` | Data ingestion pipeline | 21 tests | Unit + Mock |
| `test_gemini_and_validation.py` | Gemini service + validator | 27 tests | Unit + Mock |

**Total: ~146 tests**

---

## SETUP

### Install

```bash
pip install -r tests/requirements-test.txt --break-system-packages
```

### Run All Tests

```bash
cd backend
pytest tests/ -v
```

### Run by Category

```bash
pytest tests/test_auth.py -v                    # auth only
pytest tests/test_engine.py -v                  # engine phases only
pytest tests/test_pipeline.py -v                # pipeline only
pytest tests/ -k "not slow" -v                  # skip slow tests
pytest tests/ --cov=backend --cov-report=html   # with coverage report
```

---

## FILE-BY-FILE SPECIFICATION

---

### `conftest.py` — Shared Fixtures

This file must be placed at `backend/tests/conftest.py`. All test files import fixtures from here automatically via pytest's fixture discovery.

#### Fixtures Your Code Must Support

**`app` fixture**
- Creates Flask app via `create_app(config)` factory pattern
- Config injects: `SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"`, `TESTING = True`, `JWT_SECRET_KEY = "test-secret-key-altairgo"`, `ADMIN_ACCESS_KEY = "test-admin-key-2026"`
- **Requirement**: Your `app.py` must expose a `create_app(config=None)` function that accepts a config dict override

**`db` fixture**
- Imports `db` from `backend.database`
- Wraps each test in a transaction + rollback — no test pollutes another
- **Requirement**: `backend/database.py` must expose `db` as the SQLAlchemy instance and `init_db()` to create tables

**`registered_user` fixture**
- POSTs to `/auth/register` — requires this endpoint to return `{"token": "...", "user": {...}}` with HTTP 201

**`admin_headers` fixture**
- Returns `{"X-Admin-Key": "test-admin-key-2026"}`
- **Requirement**: All `/api/admin/*` endpoints must check for this header key

**`mock_gemini` fixture**
- Uses `monkeypatch` to replace `GeminiService.generate_itinerary` with a mock
- Returns `MOCK_ITINERARY_RESPONSE` (defined in conftest) deterministically
- **Requirement**: GeminiService must be importable as `from backend.services.gemini_service import GeminiService`

---

### `test_auth.py` — Auth Endpoint Contracts

#### POST `/auth/register`

| Test | Expected Behavior |
|---|---|
| Valid payload | HTTP 201, body contains `token` and `user` object |
| Duplicate email | HTTP 409, error message contains "already" |
| Missing email | HTTP 400 |
| Missing password | HTTP 400 |
| Invalid email format | HTTP 400 |
| Empty body | HTTP 400 |
| Password not in response | `password` and `password_hash` must NOT appear in any response |

#### POST `/auth/login`

| Test | Expected Behavior |
|---|---|
| Valid credentials | HTTP 200, body contains `token` (length > 20) |
| Wrong password | HTTP 401 |
| Nonexistent user | HTTP 401 |
| Missing fields | HTTP 400 |
| Case-insensitive email | HTTP 200 (email matching must be case-insensitive) |

#### GET `/auth/me`

| Test | Expected Behavior |
|---|---|
| Valid Bearer token | HTTP 200, returns user object without password fields |
| No token | HTTP 401 |
| Invalid token | HTTP 422 |
| Malformed Authorization header | HTTP 401 or 422 |

---

### `test_trips.py` — Trip Endpoint Contracts

#### POST `/generate-itinerary`

**Valid payload structure:**
```json
{
  "destination_country": "India",
  "start_city": "Mumbai",
  "selected_destinations": [{"id": 1, "name": "Jaipur", "estimated_cost_per_day": 3000}],
  "budget": 9000,
  "duration": 3,
  "travelers": 1,
  "style": "standard",
  "date_type": "fixed",
  "start_date": "2026-10-15",
  "traveler_type": "solo_male",
  "interests": ["heritage", "culture"]
}
```

| Test | Expected Behavior |
|---|---|
| Valid payload | HTTP 200, body contains `itinerary`, `total_cost`, `trip_title` |
| `itinerary` is a list with ≥1 item | Required |
| Day fields: `day`, `location`, `theme`, `activities`, `accommodation`, `day_total` | All required |
| Activity fields: `time`, `activity`, `cost`, `description` | All required |
| Missing `budget` | HTTP 400 |
| Missing `selected_destinations` | HTTP 400 |
| `budget: 0` | HTTP 400 |
| `duration: -1` | HTTP 400 |
| No auth token | HTTP 200 (guests can generate) |
| `total_cost` within ±5% of budget | Enforced by validator |
| Logs `AnalyticsEvent` on success | DB count increases by ≥1 |

#### POST `/api/save-trip`

| Test | Expected Behavior |
|---|---|
| Authenticated user saves trip | HTTP 201, returns `trip_id` or `id` |
| No auth token | HTTP 401 |
| Missing `itinerary_json` | HTTP 400 |

#### GET `/get-trip/:tripId`

| Test | Expected Behavior |
|---|---|
| Valid trip ID | HTTP 200, returns correct trip data |
| Nonexistent ID | HTTP 404 |

#### GET `/api/user/trips`

| Test | Expected Behavior |
|---|---|
| Authenticated | HTTP 200, returns list |
| No token | HTTP 401 |
| User isolation | User B cannot see User A's trips (list is empty for User B) |

---

### `test_destinations.py` — Destination Endpoint Contracts

#### GET `/countries`
- Returns HTTP 200 with a list
- Each country has: `id`, `name`, `code`

#### GET `/destinations`
- Returns HTTP 200 with a list
- Each destination has: `id`, `name`, `slug`, `image`, `rating`, `estimated_cost_per_day`
- Supports query filter: `?tag=Heritage` — response only contains matching tag
- Supports query filter: `?max_cost=5000` — response only contains items where `estimated_cost_per_day ≤ 5000`

#### GET `/destinations/:id`
- Returns HTTP 200 with full destination detail
- Response includes `attractions` array with ≥1 item (when seeded)
- Nonexistent ID → HTTP 404

#### POST `/api/destination-request`
- Valid payload: `{name, description, cost, tag}` → HTTP 200 or 201
- Missing `name` → HTTP 400
- Creates a `DestinationRequest` record with `status = "pending"`

#### POST `/calculate-budget`
- Returns estimated budget
- Luxury tier always returns higher estimate than budget tier for same destinations/duration

---

### `test_admin.py` — Admin Endpoint Contracts

#### Admin Key Requirement
All `/api/admin/*` endpoints must check for `X-Admin-Key` header. The value must match `ADMIN_ACCESS_KEY` in app config. Missing or wrong key → HTTP 401.

#### POST `/api/admin/verify-key`
- `{"key": "correct-key"}` → HTTP 200
- `{"key": "wrong"}` → HTTP 401
- `{}` → HTTP 400

#### GET `/api/admin/stats`
- Returns object with at minimum: `total_users`, `total_trips`, `total_destinations`
- All numeric values must be ≥ 0

#### GET/PUT/DELETE `/api/admin/destinations`
- `GET` returns list
- `PUT /:id` with `{"rating": 4.9}` → HTTP 200
- `PUT /999999` → HTTP 404
- `DELETE /:id` → HTTP 200, record removed from DB

#### GET `/api/admin/users`
- Returns list of users
- `password_hash` must NOT appear in response body

#### GET/POST `/api/admin/requests` + approve/reject
- `GET` returns list of DestinationRequest records
- `POST /:id/approve` → HTTP 200, creates new Destination, sets request status to `"approved"`
- `POST /:id/reject` → HTTP 200, sets request status to `"rejected"`
- `POST /999999/approve` → HTTP 404

---

### `test_engine.py` — Engine Phase Contracts

These are **pure unit tests**. Each engine class must be importable without a running Flask app or database. Use dependency injection — pass attraction objects as arguments, never query the DB internally.

#### `FilterEngine` (`backend/engine/filter_engine.py`)

**Class interface:**
```python
class FilterEngine:
    def filter(self, attractions: list, preferences: dict) -> list:
        ...
```

**Filter rules (all AND conditions):**

| Rule | Logic |
|---|---|
| Popularity floor | `popularity_score >= 25` |
| Traveler compatibility | `traveler_type in compatible_traveler_types` OR `compatible_traveler_types == []` |
| Seasonal gate | `seasonal_score[travel_month] >= 40` (default 70 if month not in dict) |
| Budget entry cost | `entry_cost_max <= daily_activity_budget` when `budget_tier == "budget"` |
| Category cap | Max 2 attractions of same `type` per call |

#### `ClusterEngine` (`backend/engine/cluster_engine.py`)

**Class interface:**
```python
class ClusterEngine:
    def cluster(self, attractions: list, num_days: int) -> dict:
        # Returns {"day_1": [ids], "day_2": [ids], ...}
```

**Clustering rules:**

| Rule | Logic |
|---|---|
| Group by H3 r7 hex | Attractions sharing `h3_index_r7` go to same day |
| Score hexes | Sum `popularity_score` of all attractions in hex |
| Day assignment | Top-scored hex → day_1, second → day_2, etc. |
| Activity cap | Max 6 attractions per day |
| No overlap | An attraction ID appears in exactly one day |

#### `BudgetAllocator` (`backend/engine/budget_allocator.py`)

**Class interface:**
```python
class BudgetAllocator:
    def allocate(self, total_budget: int, num_days: int, num_travelers: int,
                 tier: str, clusters: dict) -> dict:
        # Returns {"day_1": {"accommodation":..., "food":..., "day_total":...}, ...}
```

**Budget split constants:**
```python
BUDGET_SPLITS = {
    "budget":  {"accommodation": 0.30, "food": 0.28, "transport": 0.22, "activities": 0.15, "misc": 0.05},
    "mid":     {"accommodation": 0.35, "food": 0.25, "transport": 0.20, "activities": 0.15, "misc": 0.05},
    "luxury":  {"accommodation": 0.45, "food": 0.20, "transport": 0.15, "activities": 0.15, "misc": 0.05},
}
```

**Rules:**
- `total_cost ≤ total_budget * 1.05`
- No negative values in any field
- If costs exceed budget → demote tier (`luxury → mid → budget`), never cut activities
- Per-person cost is `total_budget / num_travelers`

#### `RouteOptimizer` (`backend/engine/route_optimizer.py`)

**Class interface:**
```python
class RouteOptimizer:
    def optimize(self, attractions: list, date_str: str) -> dict:
        # Returns {"activities": [...], "pacing_level": "relaxed|moderate|intense"}
```

**Ordering rules:**
- Attractions with `best_visit_time_hour <= 7` → forced to position 0 (sunrise first)
- Remaining sorted west-to-east by `longitude`
- Lunch break inserted at 13:00–14:00 if day runs past 13:00
- Each activity has: `time`, `end_time`, `duration_minutes`, `cost`, `travel_to_next_minutes`
- `end_time` of item N ≤ `time` of item N+1
- `pacing_level`: `relaxed` if total active hours < 7, `moderate` if < 9, `intense` if ≥ 9

**Travel time formula:**
```
travel_minutes = (haversine_km(lat1,lon1,lat2,lon2) / 25) * 60
```

#### `Assembler` (`backend/engine/assembler.py`)

**Class interface:**
```python
class Assembler:
    def assemble(self, engine_outputs: dict, preferences: dict) -> dict:
        # engine_outputs = {"clusters": {...}, "budget": {...}, "route": {...}}
        # Returns complete itinerary JSON matching your existing frontend schema
```

**Output contract (must match existing frontend schema):**
```
{
  trip_title: str,
  total_cost: int,
  cost_breakdown: {accommodation, food, transport, activities, misc},
  itinerary: [
    {
      day: int,              # sequential from 1
      location: str,
      theme: str,            # detected from attraction types
      pacing_level: str,
      activities: [...],     # from route optimizer
      accommodation: {...},  # from budget allocator
      day_total: int,
    }
  ],
  smart_insights: list,
  packing_tips: list,
  travel_between_cities: list,
}
```

**Theme detection:**
```python
DAY_THEMES = {
    frozenset(["fort", "palace", "historic"]): "Heritage & Forts",
    frozenset(["museum", "gallery", "art"]): "Culture & Arts",
    frozenset(["beach", "natural", "viewpoint"]): "Nature & Scenic",
    frozenset(["temple", "mosque", "church"]): "Spiritual & Sacred",
    frozenset(["market", "restaurant", "cafe"]): "Food & Local Culture",
}
# Default: "Explore & Discover"
```

---

### `test_pipeline.py` — Pipeline Contracts

All external HTTP calls must be mockable via `unittest.mock.patch`. Scripts must be importable as modules.

#### `OSMIngestor` (`backend/scripts/ingest_osm.py`)

```python
class OSMIngestor:
    def fetch_pois(self, city_name, lat, lon, radius_m) -> list[dict]:
        # Each dict: {osm_id, name, latitude, longitude, type, wikidata_id, opening_hours, ...}
    def ingest_city(self, city_name, destination_id, lat, lon) -> int:
        # Returns count of records inserted/updated
        # Must be idempotent — running twice on same city does NOT create duplicates
        # Deduplication key: osm_id
```

**Parse rules:**
- Skip elements with `lat=None` or `lon=None`
- Extract `tags.wikidata` → `wikidata_id`
- On `requests.Timeout` → return `[]`, do not raise
- On HTTP 429 → wait + retry (max 3 attempts)

#### `AttractionEnricher` (`backend/scripts/enrich_attractions.py`)

```python
class AttractionEnricher:
    def fetch_wikipedia(self, name: str) -> dict | None:
        # Returns {description, image_url} or None on failure
    def fetch_wikidata(self, wikidata_id: str) -> dict | None:
        # Returns {description, image_url} or None on failure
    def is_image_acceptable(self, url: str, width: int, height: int) -> bool:
        # Returns True only if width >= 800
```

#### `AttractionScorer` (`backend/scripts/score_attractions.py`)

```python
class AttractionScorer:
    def compute_popularity_score(self, osm_tag_count, wikidata_links, review_count) -> int:
        # Returns 0–100
    def get_duration_hours(self, attraction_type: str) -> float:
        # Uses DURATION_DEFAULTS dict, falls back to 1.0 for unknown types
    def get_best_visit_hour(self, attraction_type: str) -> int:
        # Returns 0–23, uses BEST_TIME_DEFAULTS dict
    def get_seasonal_score(self, attraction_type: str, month: str) -> int:
        # Returns 0–100. Monsoon months (jun, jul, aug) should score < 60 for most types
```

#### `PriceSyncer` (`backend/scripts/sync_prices.py`)

```python
class PriceSyncer:
    def fetch_hotel_prices(self, destination_id, tier) -> list[dict]:
        # Each dict: {name, price_min, price_max, star_rating}
        # price_min must always be <= price_max
    def get_stale_records(self, max_age_hours: int) -> list:
        # Returns HotelPrice records where last_synced < now - max_age_hours
    def get_midpoint(self, price_min, price_max) -> int:
        # Returns (price_min + price_max) // 2
```

---

### `test_gemini_and_validation.py` — Service Contracts

#### `ItineraryValidator` (`backend/validation.py`)

```python
class ItineraryValidator:
    def __init__(self, strict: bool = True):
        ...
    def validate(self, itinerary: dict, user_budget: int) -> dict:
        # Returns:
        # {
        #   "valid": bool,
        #   "errors": list[str],          # hard failures
        #   "warnings": list[str],        # soft warnings
        #   "corrected": dict | None,     # auto-corrected itinerary if strict=True
        # }
```

**Validation rules:**

| Check | Failure Type | Auto-correct? |
|---|---|---|
| Missing `trip_title` | Hard error (`valid=False`) | No |
| Missing `total_cost` | Hard error | No |
| Missing `itinerary` | Hard error | No |
| Empty `itinerary` | Hard error | No |
| `total_cost > budget * 1.05` | Hard error in strict mode | Yes — scale all costs proportionally |
| Day totals don't sum to `total_cost` (±15%) | Warning | No |
| Activity name is generic (see list below) | Warning | No |
| Day has > 5 activities | Warning | No |

**Generic name patterns to detect (regex or exact match):**
```
"local market", "beach", "restaurant", "park", "temple",
"historical site", "museum", "viewpoint", "local attraction",
"famous landmark", "tourist spot", "sightseeing"
```

**Auto-scale logic (when `total_cost > budget * 1.05`):**
```python
scale_factor = user_budget / itinerary["total_cost"]
# Apply scale_factor to:
# - total_cost
# - each value in cost_breakdown
# - each day's day_total
# - each activity's cost
# Proportions must be preserved within 5% tolerance
```

#### `GeminiService` (`backend/services/gemini_service.py`)

**Required methods:**

```python
class GeminiService:
    def __init__(self, api_key: str):
        ...
    def generate_itinerary(self, preferences: dict, destination_data: list) -> dict:
        ...
    def build_prompt(self, preferences: dict, destination_data: list) -> str:
        # Must include budget value in prompt
        # Must include traveler_type in prompt  
        # Must include instruction forbidding Gemini from modifying costs/times/names
    def chat_with_data(self, message: str, context: list) -> dict:
        # Returns {"reply": str}
```

**API call behavior:**
- Uses `gemini-2.0-flash` model (URL must contain "gemini-2.0-flash")
- On HTTP 500 → retry at least once
- On HTTP 429 → fallback to `gemini-2.0-flash-lite`
- Total retries across models: ≥ 2 attempts before giving up

---

## NEW DATABASE MODELS REQUIRED

These models must exist in `backend/models.py` for the tests to pass:

```python
# 1. Add to existing Attraction model:
latitude = Column(Float, nullable=True)
longitude = Column(Float, nullable=True)
h3_index_r7 = Column(String(20), nullable=True)
h3_index_r9 = Column(String(20), nullable=True)
osm_id = Column(BigInteger, nullable=True)
wikidata_id = Column(String(20), nullable=True)
avg_visit_duration_hours = Column(Float, default=1.0)
best_visit_time_hour = Column(SmallInteger, default=10)
crowd_peak_hours = Column(JSON, default=list)
popularity_score = Column(SmallInteger, default=50)
compatible_traveler_types = Column(JSON, default=list)
budget_category = Column(String(20), default="mid-range")
seasonal_score = Column(JSON, default=dict)
skip_rate = Column(Float, default=0.0)
entry_cost_min = Column(Integer, nullable=True)
entry_cost_max = Column(Integer, nullable=True)
entry_cost_child = Column(Integer, nullable=True)
price_last_synced = Column(DateTime, nullable=True)
gallery_images = Column(JSON, default=list)
google_rating = Column(Float, nullable=True)
review_count = Column(Integer, default=0)

# 2. New HotelPrice model (see architecture doc)
# 3. New FlightRoute model (see architecture doc)
# 4. New AttractionSignal model (see architecture doc)
```

---

## NEW DIRECTORY STRUCTURE REQUIRED

```
backend/
├── engine/
│   ├── __init__.py
│   ├── filter_engine.py       ← FilterEngine class
│   ├── cluster_engine.py      ← ClusterEngine class
│   ├── budget_allocator.py    ← BudgetAllocator class
│   ├── route_optimizer.py     ← RouteOptimizer class
│   └── assembler.py           ← Assembler class
├── scripts/
│   ├── __init__.py
│   ├── ingest_osm.py          ← OSMIngestor class
│   ├── enrich_attractions.py  ← AttractionEnricher class
│   ├── score_attractions.py   ← AttractionScorer class
│   └── sync_prices.py         ← PriceSyncer class
└── tests/
    ├── conftest.py
    ├── pytest.ini
    ├── requirements-test.txt
    ├── test_auth.py
    ├── test_trips.py
    ├── test_destinations.py
    ├── test_admin.py
    ├── test_engine.py
    ├── test_pipeline.py
    └── test_gemini_and_validation.py
```

---

## QUICK REFERENCE — What Makes Each Test Pass

| Symptom | Root Cause | Fix |
|---|---|---|
| `ImportError: cannot import name 'create_app'` | `app.py` uses `app = Flask(...)` directly | Wrap in `create_app(config=None)` factory |
| `AttributeError: 'Attraction' has no 'latitude'` | Schema migration not run | Add new columns to Attraction model |
| `ModuleNotFoundError: backend.engine.filter_engine` | `engine/` directory missing | Create `backend/engine/` with `__init__.py` |
| `AssertionError: password_hash in response` | Password hash being serialized | Remove from all serialization schemas |
| `AssertionError: total_cost > budget * 1.05` | Validator not running after Gemini | Call `ItineraryValidator.validate()` before returning response |
| `AssertionError: call_count >= 2` | No retry logic in Gemini service | Add retry with exponential backoff |

---

*AltairGO Intelligence — Test Suite Specification | 2026*
