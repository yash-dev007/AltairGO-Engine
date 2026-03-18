# AltairGO Data Pipeline — Operations Manual

> Complete reference for running the India travel data pipeline end-to-end.
> Keep this document updated whenever you add or change pipeline scripts.

---

## Overview

The pipeline populates the PostgreSQL (Supabase) database with rich India travel data: destinations, attractions (POIs), pricing, and geospatial indices. It runs in five sequential stages.

```
Stage 1  →  Seed Destinations        enrich_destinations.py
Stage 2  →  Ingest OSM POIs          ingest_osm_data.py
Stage 3  →  Enrich Attractions       enrich_attractions.py
Stage 4  →  Score Attractions        score_attractions.py
Stage 5  →  H3 Geospatial Index      h3_indexer.py
Stage 6  →  Sync Prices              sync_prices.py
```

---

## Prerequisites

### Environment Variables (`.env` in project root)

```bash
DATABASE_URL=postgresql://...         # Supabase connection string
REDIS_URL=redis://...
JWT_SECRET_KEY=...
ADMIN_ACCESS_KEY=...
GEMINI_API_KEY=...                    # Used by enrich_destinations + Gemini enrichment
GOOGLE_MAPS_API_KEY=...              # Optional — enables Google ratings/photos
```

### Python Environment

```bash
cd D:\Projects\AltairGO-Engine-main
.venv\Scripts\activate               # Windows
# or: source .venv/bin/activate      # Linux/Mac

pip install -r requirements.txt
```

Key dependencies: `sqlalchemy`, `flask`, `h3`, `requests`, `psycopg2-binary`

### Run all scripts as modules (not as files)

Always run from the repo root so relative imports work:

```bash
# Correct ✓
python -m backend.scripts.enrich_destinations

# Wrong ✗
python backend/scripts/enrich_destinations.py
```

---

## Stage 1 — Seed Destinations

**Script:** `backend/scripts/enrich_destinations.py`
**Function:** `seed_destinations()`

Seeds 120+ India destinations across all states. For each destination it writes:
- Coordinates (lat/lng + PostGIS geography)
- `best_time_months` — JSON array of month numbers (1-12) ← correct column name
- `budget_category` — string: `"budget"` / `"mid-range"` / `"luxury"` ← mapped from int 1/2/3
- `avg_visit_duration_hours`
- `compatible_traveler_types` — JSON array: `solo_male`, `solo_female`, `couple`, `family`, `group`, `elderly`
- `crowd_peak_hours` — JSON array of peak hour integers `[14, 15, 16]` ← correct column name; extracted from crowd dict (hours with value ≥ 7)
- `h3_index_r7` + `h3_index_r9` — H3 geospatial cell IDs

**Note:** `connects_well_with` exists on `attraction` only, not on `destination`. It is not written here.

This is an **upsert** — safe to re-run. Existing destinations are updated, new ones inserted.

```bash
python -m backend.scripts.enrich_destinations
```

**Coverage (as of March 2026):**
Rajasthan, Himachal Pradesh, Uttarakhand, Uttar Pradesh, Maharashtra, Goa, Karnataka,
Kerala, Tamil Nadu, Andhra Pradesh, Telangana, Odisha, West Bengal, Gujarat,
Madhya Pradesh, Bihar, Punjab, Northeast (Assam, Meghalaya, Sikkim, Nagaland, Arunachal),
Andaman & Nicobar, Ladakh, Jammu & Kashmir, Chhattisgarh, Jharkhand.

---

## Stage 2 — Ingest OSM Attractions (POIs)

**Script:** `backend/scripts/ingest_osm_data.py`

Queries the OpenStreetMap **Overpass API** (free, no key needed) for tourism POIs around each destination in the DB. Inserts `attraction` rows with:
- `name`, `lat`, `lng`, `type` (museum/temple/nature/adventure/etc.)
- `osm_id`, `wikidata_id` (used in Stage 3)
- `destination_id` (linked to destination)
- `popularity_score` = 30 (base, updated in Stage 4)

**Run:**
```bash
python -m backend.scripts.ingest_osm_data
```

**Notes:**
- Overpass API rate-limits: script sleeps 1-2s between destination queries
- Re-run is safe — uses `osm_id` as unique key to avoid duplicates
- Targets a 500m–10km radius depending on city size
- Typical yield: 30–200 POIs per destination

**Data source:** [overpass-api.de](https://overpass-api.de) — OpenStreetMap contributors

---

## Stage 3 — Enrich Attractions

**Script:** `backend/scripts/enrich_attractions.py`

Enriches each attraction with descriptions, photos, and ratings via a waterfall:

```
1. Wikidata SPARQL  → official name, description, image, instance_of
2. Wikipedia REST   → 2-3 sentence summary, main image
3. Google Places    → rating, review_count, up to 3 photos
                      (only if GOOGLE_MAPS_API_KEY is set)
```

**Run (default — 200 attractions per run):**
```bash
python -m backend.scripts.enrich_attractions
```

**Run all unenriched at once:**
```bash
python -m backend.scripts.enrich_attractions --all
```

**Custom batch size:**
```bash
python -m backend.scripts.enrich_attractions --batch 500
```

**Notes:**
- Processes only attractions where `google_rating IS NULL` or `gallery_images IS NULL`
- Safe to re-run — only touches unenriched rows
- With 8000+ attractions and `--batch 200`, run ~40 times to cover all
- Recommended: schedule via cron weekly (`python -m backend.scripts.enrich_attractions`)
- Sleeps 0.5–1s between attractions to respect rate limits
- Without Google key: Wikidata + Wikipedia still work (free)

**Rate limits:**
| Source | Limit | Notes |
|--------|-------|-------|
| Wikidata SPARQL | ~1 req/s | Free, respect UA header |
| Wikipedia REST | ~200 req/s | Free |
| Google Places | pay-per-use | $17/1000 requests |

---

## Stage 4 — Score Attractions

**Script:** `backend/scripts/score_attractions.py`

Computes two scores for every attraction:

### Popularity Score (0–100)
```
30  base (OSM ingestion)
+25 if google_rating >= 4.0 (scaled)
+45 if review_count > 0 (log scale, max at ~10k reviews)
+15 if wikidata_id is set
= 100 max
```

### Seasonal Score (per-month dict)
Cross-references `destination.best_months` with `attraction.best_months`:
```
Destination peak + Attraction peak  → 100
Destination peak only               →  80
Attraction peak only                →  60
Neither peak                        →  40
```

**Run:**
```bash
python -m backend.scripts.score_attractions
```

**Notes:**
- Processes all attractions in one pass
- Safe to re-run any time — idempotent
- Run after every `enrich_attractions` run to pick up new ratings

---

## Stage 5 — H3 Geospatial Indexing

**Script:** `backend/scripts/h3_indexer.py`

Backfills H3 hexagonal cell indices for all destinations and attractions that are missing them. Required for proximity-based queries in the FilterEngine.

```bash
python -m backend.scripts.h3_indexer
```

**Indices written:**
- `h3_index_r7` — resolution 7 (~5km cells, used for cluster-level queries)
- `h3_index_r9` — resolution 9 (~0.2km cells, used for precise proximity)

**Notes:**
- Skips rows that already have both indices set (incremental)
- Processes in batches of 500 with mid-run commits
- Per-row try/except — one bad coordinate won't abort the full run
- Compatible with h3-py v3 (`geo_to_h3`) and v4 (`latlng_to_cell`)

---

## Stage 6 — Sync Prices

**Script:** `backend/scripts/sync_prices.py`

Populates `hotel_price` and `flight_route` tables with India-realistic pricing.

### Hotel Prices
Generates 3 tiers (budget/standard/luxury) per destination with city-based multipliers:
- Delhi/Mumbai/Bangalore: 1.4×
- Goa/Kochi/Udaipur: 1.2×
- Pushkar/Hampi/Gokarna: 0.8×

**Upserts** — will not wipe existing data on re-run.

### Flight Routes
Seeds 80+ India domestic routes with:
- **Correct IATA codes** (BOM not MUM, BLR not BAN, COK not KOC, GOI not GOA)
- Distance-based pricing: short (<75 min) ₹2200–4500 | medium ₹3500–7000 | long ₹5000–11000
- Real airline names: IndiGo, Air India, SpiceJet, Vistara, Go First

Coverage: DEL, BOM, BLR, HYD, MAA, CCU, COK, GOI, JAI, AMD, PNQ, SXR, IXL, GAU, IXZ, ATQ, IXC, UDR, JDH, LKO, VNS, and more.

**Run:**
```bash
python -m backend.scripts.sync_prices
```

---

## Full Pipeline Run (First Time)

Run stages in order. Allow each to complete before starting the next.

```bash
# From D:\Projects\AltairGO-Engine-main with .venv active:

# 1. Seed destinations (upsert, ~2 min)
python -m backend.scripts.enrich_destinations

# 2. Ingest OSM POIs (slow — 1-4 hours for 120+ destinations)
python -m backend.scripts.ingest_osm_data

# 3. Enrich attractions (run multiple times, 200/batch)
#    With Google key: ~1 min per 200 attractions
#    Without Google key: ~3 min per 200 attractions (Wikidata/Wikipedia only)
python -m backend.scripts.enrich_attractions --batch 200
# Repeat until log says "Found 0 attractions requiring enrichment"

# 4. Score all attractions (~30s for 8000 attractions)
python -m backend.scripts.score_attractions

# 5. H3 index (~5 min for 8000+ attractions)
python -m backend.scripts.h3_indexer

# 6. Seed prices (~1 min)
python -m backend.scripts.sync_prices
```

---

## Incremental Updates (Ongoing Maintenance)

### Weekly (recommended)
```bash
# Re-enrich any new attractions from OSM re-ingest
python -m backend.scripts.enrich_attractions --batch 500

# Re-score to pick up new ratings
python -m backend.scripts.score_attractions

# Re-index any new POIs
python -m backend.scripts.h3_indexer

# Refresh pricing
python -m backend.scripts.sync_prices
```

### When adding new destinations
```bash
# 1. Add destination data to DESTINATIONS list in enrich_destinations.py
# 2. Run seed:
python -m backend.scripts.enrich_destinations
# 3. Run OSM ingest for new destinations only (script targets missing coords):
python -m backend.scripts.ingest_osm_data
# 4. Continue with stages 3-6 as normal
```

### Running via Admin Panel (built-in)

The admin dashboard at `/admin` has a **Trigger Job** button. These call `POST /api/ops/trigger-job`.
Jobs available: `enrich_destinations`, `ingest_osm`, `enrich_attractions`, `score_attractions`, `h3_index`, `sync_prices`.
These run as Celery tasks in the background — safe to trigger without SSH access.

---

## Troubleshooting

### `ModuleNotFoundError: No module named 'backend'`
Run as a module from the repo root, not as a file:
```bash
# Wrong:
python backend/scripts/h3_indexer.py

# Right:
python -m backend.scripts.h3_indexer
```

### `ImportError: No module named 'h3'`
```bash
pip install h3
```

### Overpass API timeouts (Stage 2)
Overpass public servers occasionally go down. Retry after 10 minutes or use a local Overpass mirror.

### Google Places quota exceeded (Stage 3)
Script gracefully falls back to Wikidata + Wikipedia when Google returns errors. No action needed — the run continues without Google data.

### H3 index fails on specific rows
h3_indexer has per-row error handling. Check the log for `WARNING` lines with the specific `id/lat/lng`. Usually caused by coordinates exactly at 0,0 (null island) — fix the destination's coordinates in the DB.

### `crowd_level_by_hour` column doesn't exist
Run the Alembic migration: `flask db upgrade`. If using Supabase directly, apply the migration SQL from `migrations/versions/`.

---

## Database Tables Populated by Pipeline

| Table | Populated by Stage |
|-------|--------------------|
| `destination` | 1, 5 |
| `attraction` | 2, 3, 4, 5 |
| `hotel_price` | 6 |
| `flight_route` | 6 |
| `destination_info` | (future: Gemini enrichment) |

---

## Data Sources Used

| Source | What for | Free? | Key needed? |
|--------|----------|-------|-------------|
| OpenStreetMap Overpass API | POI ingestion | ✅ Yes | No |
| Wikidata SPARQL | Attraction descriptions, images | ✅ Yes | No |
| Wikipedia REST API | Summaries, thumbnails | ✅ Yes | No |
| Google Places API | Ratings, reviews, photos | ❌ Pay-per-use | Yes |
| Gemini 2.0 Flash | Content enrichment (future) | Free tier | Yes (in .env) |

---

*Last updated: 2026-03-18*
