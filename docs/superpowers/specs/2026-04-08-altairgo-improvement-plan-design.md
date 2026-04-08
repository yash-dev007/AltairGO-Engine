# AltairGO — Full Quality & Architecture Improvement Plan

**Date:** 2026-04-08  
**Status:** Approved  
**Approach:** 3 parallel tracks, task-segregated by tool capability (not time)

---

## Context

All P1–P6 test phases complete (188 passed). Production-ready as of 2026-04-06.
The system has solid bones — this plan adds quality, visual identity, and operational visibility.

**Goals (all three, equally):**
1. Demo/investor-ready — premium visual identity, compelling UX
2. Production-hardened — reliability, monitoring, no silent failures
3. Developer velocity — clean architecture for the next 3 months of features

---

## Track Structure

Three tracks share **zero overlapping files**:

```
Track A — Frontend Visual Identity        → Gemini CLI + Claude Code + 21st.dev MCP
  D:/Projects/AltairGO-Platform/src/
    design-system/        ← NEW
    components/ui/        ← NEW
    pages/                ← REDESIGN (existing files)

Track B — Admin Ops Console               → Claude Code Sonnet
  backend/routes/admin.py                 ← EXTEND
  backend/tasks/task_registry.py          ← NEW
  D:/Projects/AltairGO-Platform/src/
    pages/admin/          ← EXTEND (new sub-pages)

Track C — Backend Hardening               → Codex
  backend/middleware/logging.py           ← NEW
  backend/routes/ (all 18 files)          ← AUDIT
  backend/routes/trip_tools.py            ← EXTEND
  backend/metrics.py                      ← NEW
  backend/tasks/ (all 9 files)            ← HARDEN
```

---

## Track A — Frontend Visual Identity

### Why this tool assignment
Gemini CLI has a 1M-token context window — it can read every existing component in one pass and produce a coherent design spec. Claude Code + 21st.dev MCP then executes that spec: the `magic_component_builder` produces polished, production-grade components from a clear prompt. No tool here is guessing at the design — Gemini sets the contract, 21st.dev builds to spec.

### A1 — Design System Foundation
**Tool:** Gemini CLI  
**Output:** `src/design-system/tokens.css`, `typography.css`, `animations.css`

Gemini reads all existing pages and components, then produces:
- CSS custom properties for every design decision currently hardcoded
- Color palette: `#4F46E5` indigo primary, deep navy backgrounds, warm amber accents, full dark-mode token set
- Spacing scale: 4px base grid, named steps (xs/sm/md/lg/xl/2xl)
- Typography: display / heading / body / caption scale with line heights
- Shared Framer Motion variants: `fadeIn`, `slideUp`, `staggerChildren`

### A2 — Component Library
**Tool:** Claude Code + 21st.dev MCP (`magic_component_builder`)  
**Output:** `src/components/ui/` — 12 components

Components to build (each via `mcp__magic__21st_magic_component_builder`):
`Button`, `Card`, `Badge`, `Input`, `Select`, `Modal`, `Tabs`, `Skeleton`, `EmptyState`, `Toast`, `Avatar`, `ProgressBar`

Each component: uses design tokens from A1, has loading/disabled/error states, is accessible (ARIA labels, keyboard nav), exports TypeScript-friendly props.

### A3 — Page Redesigns
**Tool:** Claude Code (integrates A1+A2) + Gemini CLI (page architecture)  
**Priority order (best output first, not by time):**

| Page | Key Change |
|---|---|
| `HomePage` | Hero with animated gradient, feature cards, trust signals, CTA flow |
| `PlannerPage` | Multi-step wizard: origin → destinations → preferences → generate |
| `TripViewerPage` | Premium itinerary cards, visual day timeline, cover imagery |
| `DashboardPage` | Trip grid with cover images, stats strip already in place |
| `BlogsPage` | Editorial grid layout, category filters |
| `DiscoverPage` | Destination cards with rich imagery |
| `Auth pages` | Clean split-panel login/register |

### A4 — Activity Reordering UI
**Tool:** Claude Code  
**Depends on:** Track C Task 4 (reorder endpoint)  
Drag-and-drop within `ItineraryTab` using existing Framer Motion dep. No new libraries.

---

## Track B — Admin Ops Console

### Why this tool assignment
Claude Code Sonnet has deep context of the existing Flask app structure, blueprint registration order, auth patterns, and admin routes. Adding new endpoints + new React admin pages requires understanding the existing system — not a contained spec task.

### B1 — Task Registry Infrastructure
**Tool:** Claude Code  
**File:** `backend/tasks/task_registry.py` (NEW)

Central registry: maps task function name → human label → cron schedule → Redis key for last-run metadata.  
On each task execution, writes `{ran_at, status, duration_s, error}` to `celery:task:{name}:last`.  
This powers the Celery monitor without Flower.

```python
TASK_REGISTRY = {
    "run_weather_sync": {"label": "Weather Sync", "schedule": "Daily 05:30"},
    "run_score_update": {"label": "Score Update", "schedule": "Daily 02:00"},
    # ... all 9 tasks
}
```

### B2 — Admin Backend Endpoints
**Tool:** Claude Code  
**File:** `backend/routes/admin.py` (EXTEND)

| Endpoint | Auth | Purpose |
|---|---|---|
| `GET /api/admin/celery/tasks` | admin | List all tasks: name, schedule, last_run, last_status, last_error |
| `POST /api/admin/celery/trigger/<task>` | admin | Manually fire task → return job_id |
| `GET /api/admin/health` | admin | Redis ping+memory, worker heartbeat age, Gemini 429 count, embedding coverage % |
| `GET /api/admin/settings` | admin | List all EngineSetting rows |
| `PATCH /api/admin/settings/<key>` | admin | Update EngineSetting value |
| `GET /api/admin/activity-feed` | admin | Last 50 events from Redis stream |

### B3 — Admin UI: Celery Monitor
**Tool:** Claude Code + 21st.dev MCP  
**File:** `src/pages/admin/CeleryMonitorPage.jsx` (NEW)

Task grid: each row shows task name, human schedule, status badge (success/failed/never-run), last-run timestamp, last error (expandable), manual trigger button. Trigger fires `POST /api/admin/celery/trigger/:task` and shows a toast.

### B4 — Admin UI: System Health
**Tool:** Claude Code + 21st.dev MCP  
**File:** `src/pages/admin/SystemHealthPage.jsx` (NEW)

Stat cards: Redis memory %, worker heartbeat (green < 10min, red > 10min), Gemini 429 count (last 24h), embedding coverage % (destinations with non-null embedding / total). Auto-refreshes every 30s.

### B5 — Admin UI: Settings & Feature Flags
**Tool:** Claude Code  
**File:** `src/pages/admin/SettingsPage.jsx` (NEW)

Two sections:
- `EngineSetting` table: inline-editable key→value rows, save on blur
- Feature flags: toggle switches with `traffic_pct` slider, mapped to existing `PATCH /api/admin/feature-flags/:id`

### B6 — Admin UI: Activity Feed
**Tool:** Claude Code  
**File:** `src/pages/admin/ActivityFeedPage.jsx` (NEW)

Live scrolling log: event type badge, timestamp, description. Color-coded: green=success, amber=warning, red=error. Polls `GET /api/admin/activity-feed` every 10s.

### B7 — Admin Navigation
**Tool:** Claude Code  
**File:** `src/pages/admin/AdminDashboard.jsx` (EXTEND)

Add sidebar nav items: Overview (existing), Celery Tasks, System Health, Settings, Activity Feed.

---

## Track C — Backend Hardening

### Why this tool assignment
These are all well-scoped, specifiable tasks with clear inputs and outputs. Codex excels at "given this pattern, apply it consistently across N files." No deep system understanding required — just reliable execution of a defined transformation.

### C1 — Structured Logging Middleware
**Tool:** Codex  
**File:** `backend/middleware/logging.py` (NEW)

Flask `after_request` hook emitting JSON log lines:
```json
{"ts": "...", "method": "GET", "path": "/api/trips", "status": 200, 
 "duration_ms": 45, "user_id": "abc", "ip": "1.2.3.4"}
```
Register in `app.py`. Replaces all `print()` debugging calls across routes.

### C2 — Consistent Error Envelope
**Tool:** Codex  
**Files:** All 18 `backend/routes/*.py` files

Every error response normalized to:
```json
{"success": false, "error": "Human-readable message", "code": "ERR_NOT_FOUND"}
```
Success responses gain `"success": true` wrapper where missing.  
Error codes: `ERR_NOT_FOUND`, `ERR_UNAUTHORIZED`, `ERR_VALIDATION`, `ERR_SERVER`, `ERR_RATE_LIMIT`.

### C3 — Metrics Endpoint
**Tool:** Codex  
**File:** `backend/metrics.py` (NEW)  
**Route:** `GET /api/metrics` (admin-only)

```json
{
  "trips_generated_24h": 12,
  "active_jobs": 3,
  "cache_hit_rate": 0.74,
  "embedding_coverage_pct": 0.0,
  "gemini_429_count_24h": 5,
  "worker_alive": true,
  "redis_memory_mb": 48.2,
  "db_pool_size": 10
}
```
Reads from Redis counters (increment on each trip gen/cache hit), worker heartbeat key, Supabase pool stats.

### C4 — Activity Reorder Endpoint
**Tool:** Codex  
**File:** `backend/routes/trip_tools.py` (EXTEND)  
**Route:** `POST /api/trip/<trip_id>/reorder-activity`

```json
{"day_index": 1, "from_index": 2, "to_index": 0}
```
Uses existing safe-mutation pattern: `deepcopy(trip.itinerary_json)` → swap activities[day][from] ↔ activities[day][to] → reassign → commit. Returns updated day activities.

### C5 — Celery Task Retry Hardening
**Tool:** Codex  
**Files:** All 9 `backend/tasks/*.py` files

Add to every task:
- `max_retries=3, default_retry_delay=60`
- `try/except` wrapping execution body
- On failure: write `{task, error, traceback, ts}` to `celery:errors:{task_name}` Redis list (max 10 entries, used by B4 health panel)
- On success: write `{ts, duration_s}` to `celery:task:{name}:last`

---

## Cross-Track Dependency

Only one dependency exists:
- **A4** (activity reorder UI) requires **C4** (reorder endpoint) to exist first
- Everything else in all three tracks is fully independent

---

## Definition of Done

| Track | Done When |
|---|---|
| A | All pages use design system tokens, component library in use site-wide, no hardcoded colors/spacing |
| B | Admin panel shows live Celery status, health stats, editable settings, activity feed — all backed by real data |
| C | All routes return consistent envelopes, structured logs flowing, /api/metrics returns real values, activity reorder works |

---

## What This Plan Does NOT Include

- Database schema changes (no new migrations needed)
- Engine pipeline changes (orchestrator, filter_engine, etc. untouched)
- New user-facing features beyond what's listed (YAGNI)
- Time estimates
