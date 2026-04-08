# Track B — Admin Ops Console Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a full ops console in the admin panel: Celery task monitoring with manual triggers, live system health stats, EngineSetting editor, feature flag toggles, and an activity feed.

**Architecture:** Backend adds new endpoints to `admin.py` reading Redis keys written by Track C's Celery retry hardening. Frontend adds 4 new admin sub-pages wired into an extended sidebar nav. No schema migrations needed — all state lives in Redis + existing DB tables (`EngineSetting`, `FeatureFlag`).

**Tech Stack:** Python Flask (`@require_admin` auth), Redis, SQLAlchemy, React 19, Tailwind v4, 21st.dev MCP for UI components

**Executor tool:** Claude Code Sonnet — requires understanding of existing Flask blueprint patterns and React admin page structure.

**Prerequisite:** Track C Task 5 must be complete (Celery retry hardening writes Redis keys this plan reads). If Track C isn't done, admin endpoints gracefully return empty last_run / no errors.

---

## Codebase Patterns

**Admin backend:**
```python
# backend/routes/admin.py
from flask import Blueprint, request, jsonify
from backend.utils.auth import require_admin
from backend.database import db

admin_bp = Blueprint("admin", __name__)

@admin_bp.get("/api/admin/something")
@require_admin
def handler():
    return jsonify({"success": True, "data": {...}})
```

**Admin frontend pages live at:** `D:/Projects/AltairGO-Platform/src/pages/admin/`

**Existing admin nav is in:** `D:/Projects/AltairGO-Platform/src/pages/admin/AdminDashboard.jsx`

**Admin auth in frontend:**
```js
// Admin token stored as ag_admin_token in localStorage
// All admin API calls use: headers: { 'X-Admin-Key': adminKey }
// adminKey = localStorage.getItem('ag_admin_token')
```

**API call pattern (frontend):**
```js
const adminKey = localStorage.getItem('ag_admin_token');
const resp = await fetch('/api/admin/something', {
  headers: { 'X-Admin-Key': adminKey, 'Content-Type': 'application/json' }
});
const body = await resp.json();
// body.success === true → use body.data
// body.success === false → show body.error
```

**Redis access (backend):**
```python
from backend.services.cache_service import get_redis_client
import json

r = get_redis_client()
if r:
    raw = r.get("celery:task:run_score_update:last")
    data = json.loads(raw) if raw else None
```

**EngineSetting model:**
```python
# backend/models.py
class EngineSetting(db.Model):
    __tablename__ = "engine_settings"
    key = db.Column(db.String(64), primary_key=True)
    value = db.Column(db.Text, nullable=False)
    description = db.Column(db.Text)
```

**FeatureFlag model:**
```python
class FeatureFlag(db.Model):
    __tablename__ = "feature_flags"
    id = db.Column(db.Integer, primary_key=True)
    flag_key = db.Column(db.String(64), unique=True)
    is_active = db.Column(db.Boolean, default=False)
    traffic_pct = db.Column(db.Integer, default=100)
```

**Test setup:**
```python
# ADMIN_ACCESS_KEY = "test-admin-key-2026"
# admin_headers fixture: {"X-Admin-Key": "test-admin-key-2026"}
# Run: python -m pytest backend/tests/test_admin.py -q --tb=short
```

---

## File Map

**Backend:**
| File | Action | Responsibility |
|---|---|---|
| `backend/routes/admin.py` | MODIFY | Add 5 new endpoints: celery tasks, trigger, health, settings CRUD, activity feed |
| `backend/tasks/task_registry.py` | READ | Used by celery endpoints (created in Track C Task 5) |

**Frontend (`D:/Projects/AltairGO-Platform/src/`):**
| File | Action | Responsibility |
|---|---|---|
| `pages/admin/AdminDashboard.jsx` | MODIFY | Add sidebar nav links to new pages |
| `pages/admin/CeleryMonitorPage.jsx` | CREATE | Task grid with status, manual trigger |
| `pages/admin/SystemHealthPage.jsx` | CREATE | Live stats cards, auto-refresh |
| `pages/admin/SettingsPage.jsx` | CREATE | EngineSetting inline editor + feature flag toggles |
| `pages/admin/ActivityFeedPage.jsx` | CREATE | Scrolling event log |
| `App.jsx` | MODIFY | Add routes for new admin pages |

---

## Task 1: Backend — Celery Monitor Endpoints

**Files:**
- Modify: `backend/routes/admin.py`

- [ ] **Step 1.1: Write failing tests**

Add to `backend/tests/test_admin.py`:

```python
def test_celery_tasks_list(client, admin_headers):
    resp = client.get("/api/admin/celery/tasks", headers=admin_headers)
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["success"] is True
    tasks = body["data"]
    assert isinstance(tasks, list)
    assert len(tasks) == 12
    first = tasks[0]
    assert "name" in first
    assert "label" in first
    assert "schedule" in first
    assert "last_run" in first        # None or dict
    assert "recent_errors" in first   # list

def test_celery_trigger_unknown_task(client, admin_headers):
    resp = client.post("/api/admin/celery/trigger/nonexistent_task", headers=admin_headers)
    assert resp.status_code == 404
    assert resp.get_json()["code"] == "ERR_NOT_FOUND"

def test_celery_trigger_known_task(client, admin_headers):
    resp = client.post("/api/admin/celery/trigger/run_score_update", headers=admin_headers)
    # In test env (TESTING=true, task_always_eager=True), task runs synchronously
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["success"] is True
    assert "job_id" in body["data"]
```

- [ ] **Step 1.2: Run — expect FAIL**

```bash
python -m pytest backend/tests/test_admin.py::test_celery_tasks_list -v
```

- [ ] **Step 1.3: Add celery monitor endpoints to admin.py**

Open `backend/routes/admin.py`. Add at the end of the file:

```python
@admin_bp.get("/api/admin/celery/tasks")
@require_admin
def celery_tasks_list():
    """List all scheduled tasks with last-run metadata from Redis."""
    from backend.tasks.task_registry import TASK_REGISTRY
    from backend.services.cache_service import get_redis_client
    import json

    r = get_redis_client()
    tasks = []
    for name, meta in TASK_REGISTRY.items():
        last_run = None
        recent_errors = []
        if r:
            raw = r.get(f"celery:task:{name}:last")
            if raw:
                try:
                    last_run = json.loads(raw)
                except Exception:
                    pass
            raw_errors = r.lrange(f"celery:errors:{name}", 0, 2)
            recent_errors = [json.loads(e) for e in raw_errors if e]
        tasks.append({
            "name": name,
            "label": meta["label"],
            "schedule": meta["schedule"],
            "last_run": last_run,
            "recent_errors": recent_errors,
        })
    return jsonify({"success": True, "data": tasks})


@admin_bp.post("/api/admin/celery/trigger/<task_name>")
@require_admin
def celery_trigger(task_name: str):
    """Manually fire a scheduled task. Returns job_id."""
    from backend.tasks.task_registry import TASK_REGISTRY
    if task_name not in TASK_REGISTRY:
        return jsonify({
            "success": False,
            "error": f"Unknown task: {task_name}",
            "code": "ERR_NOT_FOUND",
        }), 404
    try:
        import backend.celery_tasks as ct
        task_fn = getattr(ct, task_name, None)
        if task_fn is None:
            return jsonify({
                "success": False,
                "error": "Task function not found",
                "code": "ERR_SERVER",
            }), 500
        job = task_fn.delay()
        return jsonify({"success": True, "data": {"job_id": str(job.id)}})
    except Exception as exc:
        return jsonify({
            "success": False,
            "error": str(exc),
            "code": "ERR_SERVER",
        }), 500
```

- [ ] **Step 1.4: Run tests**

```bash
python -m pytest backend/tests/test_admin.py::test_celery_tasks_list backend/tests/test_admin.py::test_celery_trigger_unknown_task backend/tests/test_admin.py::test_celery_trigger_known_task -v
```

Expected: PASS.

- [ ] **Step 1.5: Commit**

```bash
git add backend/routes/admin.py backend/tests/test_admin.py
git commit -m "feat: add admin Celery task list and manual trigger endpoints"
```

---

## Task 2: Backend — Health, Settings, Activity Feed Endpoints

**Files:**
- Modify: `backend/routes/admin.py`

- [ ] **Step 2.1: Write failing tests**

Add to `backend/tests/test_admin.py`:

```python
def test_admin_health(client, admin_headers):
    resp = client.get("/api/admin/health", headers=admin_headers)
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["success"] is True
    data = body["data"]
    for field in ["redis_ok", "worker_alive", "embedding_coverage_pct", "gemini_429_count_24h"]:
        assert field in data, f"Missing field: {field}"

def test_admin_settings_list(client, admin_headers):
    resp = client.get("/api/admin/settings", headers=admin_headers)
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["success"] is True
    assert isinstance(body["data"], list)

def test_admin_settings_update(client, admin_headers):
    # First get a setting key
    resp = client.get("/api/admin/settings", headers=admin_headers)
    settings = resp.get_json()["data"]
    if not settings:
        pytest.skip("No EngineSetting rows in test DB")
    key = settings[0]["key"]
    original_value = settings[0]["value"]

    resp = client.patch(
        f"/api/admin/settings/{key}",
        json={"value": "test_value_99"},
        headers=admin_headers,
    )
    assert resp.status_code == 200
    assert resp.get_json()["success"] is True

    # Restore
    client.patch(f"/api/admin/settings/{key}", json={"value": original_value}, headers=admin_headers)

def test_admin_activity_feed(client, admin_headers):
    resp = client.get("/api/admin/activity-feed", headers=admin_headers)
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["success"] is True
    assert isinstance(body["data"], list)
```

- [ ] **Step 2.2: Run — expect FAIL**

```bash
python -m pytest backend/tests/test_admin.py::test_admin_health -v
```

- [ ] **Step 2.3: Add health, settings, activity feed endpoints to admin.py**

Append to `backend/routes/admin.py`:

```python
@admin_bp.get("/api/admin/health")
@require_admin
def admin_health():
    """Live system health: Redis, worker, embeddings, Gemini quota."""
    from backend.services.cache_service import get_redis_client, REDIS_OK
    from backend.models import Destination
    from datetime import datetime, timezone
    import json

    r = get_redis_client()
    worker_alive = False
    gemini_429 = 0
    embedding_pct = 0.0

    if r:
        heartbeat = r.get("celery:heartbeat")
        if heartbeat:
            try:
                ts = datetime.fromisoformat(heartbeat)
                worker_alive = (datetime.now(timezone.utc) - ts).total_seconds() < 600
            except Exception:
                pass
        gemini_429 = int(r.get("metrics:gemini_429_24h") or 0)

    try:
        total = Destination.query.count()
        with_emb = Destination.query.filter(Destination.embedding.isnot(None)).count()
        embedding_pct = round(with_emb / total, 3) if total > 0 else 0.0
    except Exception:
        pass

    return jsonify({
        "success": True,
        "data": {
            "redis_ok": REDIS_OK,
            "worker_alive": worker_alive,
            "embedding_coverage_pct": embedding_pct,
            "gemini_429_count_24h": gemini_429,
        }
    })


@admin_bp.get("/api/admin/settings")
@require_admin
def settings_list():
    """List all EngineSetting key-value pairs."""
    from backend.models import EngineSetting
    rows = EngineSetting.query.order_by(EngineSetting.key).all()
    return jsonify({
        "success": True,
        "data": [{"key": r.key, "value": r.value, "description": r.description} for r in rows]
    })


@admin_bp.patch("/api/admin/settings/<key>")
@require_admin
def settings_update(key: str):
    """Update a single EngineSetting value."""
    from backend.models import EngineSetting
    row = EngineSetting.query.get(key)
    if not row:
        return jsonify({"success": False, "error": "Setting not found", "code": "ERR_NOT_FOUND"}), 404
    data = request.get_json() or {}
    if "value" not in data:
        return jsonify({"success": False, "error": "value is required", "code": "ERR_VALIDATION"}), 400
    row.value = str(data["value"])
    db.session.commit()
    return jsonify({"success": True, "data": {"key": key, "value": row.value}})


@admin_bp.get("/api/admin/activity-feed")
@require_admin
def activity_feed():
    """Last 50 system events from Redis stream."""
    from backend.services.cache_service import get_redis_client
    import json

    r = get_redis_client()
    events = []
    if r:
        raw_events = r.lrange("admin:activity_feed", 0, 49)
        for raw in raw_events:
            try:
                events.append(json.loads(raw))
            except Exception:
                pass
    return jsonify({"success": True, "data": events})
```

- [ ] **Step 2.4: Run tests**

```bash
python -m pytest backend/tests/test_admin.py -k "health or settings or activity" -v
```

- [ ] **Step 2.5: Commit**

```bash
git add backend/routes/admin.py backend/tests/test_admin.py
git commit -m "feat: add admin health, settings, and activity feed endpoints"
```

---

## Task 3: Frontend — Admin Navigation Update

**Files:**
- Modify: `D:/Projects/AltairGO-Platform/src/pages/admin/AdminDashboard.jsx`
- Modify: `D:/Projects/AltairGO-Platform/src/App.jsx`

- [ ] **Step 3.1: Read current AdminDashboard.jsx to understand nav structure**

Read `D:/Projects/AltairGO-Platform/src/pages/admin/AdminDashboard.jsx` and identify where the nav links are rendered.

- [ ] **Step 3.2: Add nav links for new pages**

In `AdminDashboard.jsx`, add the following nav items alongside existing ones (preserve existing items, add new ones):

```jsx
// Add to nav items array / sidebar
{ label: 'Celery Tasks', path: '/admin/celery', icon: '⚙️' },
{ label: 'System Health', path: '/admin/health', icon: '🩺' },
{ label: 'Settings', path: '/admin/settings', icon: '🔧' },
{ label: 'Activity Feed', path: '/admin/activity', icon: '📋' },
```

If nav is rendered as `<Link>` elements, add:
```jsx
<Link to="/admin/celery" className="...existing-nav-class...">⚙️ Celery Tasks</Link>
<Link to="/admin/health" className="...existing-nav-class...">🩺 System Health</Link>
<Link to="/admin/settings" className="...existing-nav-class...">🔧 Settings</Link>
<Link to="/admin/activity" className="...existing-nav-class...">📋 Activity Feed</Link>
```

- [ ] **Step 3.3: Register routes in App.jsx**

Open `D:/Projects/AltairGO-Platform/src/App.jsx`. Find where admin routes are registered (look for `AdminRoute` or `/admin` paths). Add:

```jsx
import CeleryMonitorPage from './pages/admin/CeleryMonitorPage';
import SystemHealthPage from './pages/admin/SystemHealthPage';
import SettingsPage from './pages/admin/SettingsPage';
import ActivityFeedPage from './pages/admin/ActivityFeedPage';

// Inside <Routes> alongside existing admin routes:
<Route path="/admin/celery" element={<AdminRoute><CeleryMonitorPage /></AdminRoute>} />
<Route path="/admin/health" element={<AdminRoute><SystemHealthPage /></AdminRoute>} />
<Route path="/admin/settings" element={<AdminRoute><SettingsPage /></AdminRoute>} />
<Route path="/admin/activity" element={<AdminRoute><ActivityFeedPage /></AdminRoute>} />
```

- [ ] **Step 3.4: Commit (placeholder pages created next)**

```bash
cd "D:/Projects/AltairGO-Platform"
git add src/pages/admin/AdminDashboard.jsx src/App.jsx
git commit -m "feat: add admin nav links and routes for ops console pages"
```

---

## Task 4: Frontend — CeleryMonitorPage

**Files:**
- Create: `D:/Projects/AltairGO-Platform/src/pages/admin/CeleryMonitorPage.jsx`

- [ ] **Step 4.1: Build component using 21st.dev MCP**

Use `mcp__magic__21st_magic_component_builder` with this prompt:

```
Build a React component called CeleryMonitorPage for an admin panel.

Layout: Full-width page with a header "Celery Task Monitor" and a responsive table/grid below.

Each row shows one task with these columns:
- Task name (human label, bold)
- Schedule (small gray text, e.g. "Daily 02:00")
- Status badge: green "Success" / red "Failed" / gray "Never Run" based on last_run.status
- Last run (relative time, e.g. "2 hours ago") — null shows "Never"
- Actions: a "Trigger" button (indigo, small)

On "Trigger" click: show a loading spinner on that row, POST to the API, then show a success toast or error message.

Loading state: show skeleton rows while fetching.
Empty state: "No tasks registered" message.

Data comes from GET /api/admin/celery/tasks → response.data (array of {name, label, schedule, last_run: {ts, status} | null, recent_errors})
Trigger via POST /api/admin/celery/trigger/:name

Admin API calls use header: X-Admin-Key from localStorage.getItem('ag_admin_token')

Style: Tailwind CSS v4, indigo primary color, clean table with hover states, consistent with existing admin panel.
```

- [ ] **Step 4.2: Save the output to the file**

Save the generated component to `D:/Projects/AltairGO-Platform/src/pages/admin/CeleryMonitorPage.jsx`.

Verify it includes:
- `useState` + `useEffect` for data fetching
- Loading state with skeleton or spinner
- Trigger button with per-row loading state
- Toast/alert on trigger success/error
- Proper `X-Admin-Key` header on all fetches

- [ ] **Step 4.3: Commit**

```bash
cd "D:/Projects/AltairGO-Platform"
git add src/pages/admin/CeleryMonitorPage.jsx
git commit -m "feat: add CeleryMonitorPage with task status and manual trigger"
```

---

## Task 5: Frontend — SystemHealthPage

**Files:**
- Create: `D:/Projects/AltairGO-Platform/src/pages/admin/SystemHealthPage.jsx`

- [ ] **Step 5.1: Build component using 21st.dev MCP**

Use `mcp__magic__21st_magic_component_builder` with this prompt:

```
Build a React component called SystemHealthPage for an admin panel.

Layout: Page header "System Health", then a 2×2 grid of stat cards, then a "Last refreshed: X seconds ago" line with a Refresh button.

Stat cards:
1. Redis Status — green "Online" / red "Offline" based on redis_ok boolean
2. Worker Status — green "Alive" / red "Dead" based on worker_alive boolean. Show "Last heartbeat > 10min ago" when dead.
3. Embedding Coverage — show as percentage (e.g. "34%") with a horizontal progress bar
4. Gemini 429s (24h) — show count, amber warning badge if > 10

Auto-refreshes every 30 seconds. Shows a subtle "Refreshing..." indicator.

Data from GET /api/admin/health → response.data:
{ redis_ok: bool, worker_alive: bool, embedding_coverage_pct: number, gemini_429_count_24h: number }

Admin API calls use header: X-Admin-Key from localStorage.getItem('ag_admin_token')

Style: Tailwind CSS v4, clean stat cards with colored status indicators, indigo primary.
```

- [ ] **Step 5.2: Save and verify**

Save to `D:/Projects/AltairGO-Platform/src/pages/admin/SystemHealthPage.jsx`.

Check it has: auto-refresh `setInterval`, cleanup in `useEffect` return, loading skeleton on first load.

- [ ] **Step 5.3: Commit**

```bash
cd "D:/Projects/AltairGO-Platform"
git add src/pages/admin/SystemHealthPage.jsx
git commit -m "feat: add SystemHealthPage with live stats and auto-refresh"
```

---

## Task 6: Frontend — SettingsPage

**Files:**
- Create: `D:/Projects/AltairGO-Platform/src/pages/admin/SettingsPage.jsx`

- [ ] **Step 6.1: Build component using 21st.dev MCP**

Use `mcp__magic__21st_magic_component_builder` with this prompt:

```
Build a React component called SettingsPage for an admin panel.

Two sections on the page:

Section 1 — "Engine Settings":
Table with columns: Key, Value (editable inline), Description, Save button.
Each row: key (monospace bold), value in an <input> (editable), description (gray small text), Save button (appears when value changes).
On Save: PATCH /api/admin/settings/:key with body {value: newValue}. Show inline success (green checkmark) or error.

Section 2 — "Feature Flags":
Table with columns: Flag Key, Enabled (toggle switch), Traffic % (number input 0-100), Save.
Toggle maps to is_active. Traffic % maps to traffic_pct.
On toggle change: immediately call PATCH /api/admin/feature-flags/:id with {is_active: bool, traffic_pct: number}.
Show loading spinner on the row while saving.

Data for section 1: GET /api/admin/settings → response.data (array of {key, value, description})
Data for section 2: GET /api/admin/feature-flags → response.data (array of {id, flag_key, is_active, traffic_pct})

Admin API calls use header: X-Admin-Key from localStorage.getItem('ag_admin_token')

Style: Tailwind CSS v4, clean tables, indigo toggles, monospace font for keys.
```

- [ ] **Step 6.2: Save and verify**

Save to `D:/Projects/AltairGO-Platform/src/pages/admin/SettingsPage.jsx`.

Check: inline editing doesn't submit on every keystroke (use local state, only PATCH on save button click or blur).

- [ ] **Step 6.3: Commit**

```bash
cd "D:/Projects/AltairGO-Platform"
git add src/pages/admin/SettingsPage.jsx
git commit -m "feat: add SettingsPage with inline EngineSetting editor and feature flag toggles"
```

---

## Task 7: Frontend — ActivityFeedPage

**Files:**
- Create: `D:/Projects/AltairGO-Platform/src/pages/admin/ActivityFeedPage.jsx`

- [ ] **Step 7.1: Build component using 21st.dev MCP**

Use `mcp__magic__21st_magic_component_builder` with this prompt:

```
Build a React component called ActivityFeedPage for an admin panel.

Layout: Header "Activity Feed", then a scrollable list of event rows, then a "Load more" button at bottom.

Each event row shows:
- Severity badge (green INFO / amber WARN / red ERROR) based on event.severity
- Event type in bold (e.g. "trip_generated", "booking_failed", "weather_sync_complete")
- Description text (truncated to 80 chars, expandable on click)
- Relative timestamp (e.g. "5 minutes ago")

Rows are color-tinted: green tint for INFO, amber for WARN, red tint for ERROR.

Polls GET /api/admin/activity-feed every 10 seconds. New events slide in at the top with a brief highlight animation.

Empty state: "No activity recorded yet" with a subtle icon.
Loading state: 5 skeleton rows.

Data format: array of { ts: ISO string, type: string, severity: "INFO"|"WARN"|"ERROR", description: string }

Admin API calls use header: X-Admin-Key from localStorage.getItem('ag_admin_token')

Style: Tailwind CSS v4, dense list layout, subtle alternating row backgrounds.
```

- [ ] **Step 7.2: Save and verify**

Save to `D:/Projects/AltairGO-Platform/src/pages/admin/ActivityFeedPage.jsx`.

Check: polling clears on unmount (cleanup in useEffect), no infinite re-render loops.

- [ ] **Step 7.3: Commit**

```bash
cd "D:/Projects/AltairGO-Platform"
git add src/pages/admin/ActivityFeedPage.jsx
git commit -m "feat: add ActivityFeedPage with live event polling"
```

---

## Task 8: Integration Smoke Test

- [ ] **Step 8.1: Start backend + frontend**

```bash
# Terminal 1 — Backend
cd "D:/Projects/AltairGO Engine"
docker compose up -d redis
.venv/Scripts/python.exe -m flask --app backend.app:create_app run --port 5000 --reload

# Terminal 2 — Frontend
cd "D:/Projects/AltairGO-Platform"
npm run dev
```

- [ ] **Step 8.2: Manual smoke test checklist**

Navigate to `http://localhost:5173/admin`:
- [ ] Login with admin key
- [ ] Click "Celery Tasks" → see 12 task rows, trigger one, see toast
- [ ] Click "System Health" → see 4 stat cards, auto-refreshes every 30s
- [ ] Click "Settings" → see EngineSetting rows, edit one value, save
- [ ] Click "Activity Feed" → see event list (may be empty if no events yet)

- [ ] **Step 8.3: Run backend tests**

```bash
cd "D:/Projects/AltairGO Engine"
python -m pytest backend/tests/ -q --tb=short
```

Expected: all tests pass.

- [ ] **Step 8.4: Final commit**

```bash
cd "D:/Projects/AltairGO-Platform"
git add .
git commit -m "feat: complete admin ops console - Celery monitor, health, settings, activity feed"
```

---

## Self-Review Checklist

- [x] Spec coverage: Celery list ✓, manual trigger ✓, health stats ✓, settings editor ✓, feature flags ✓, activity feed ✓
- [x] No placeholders — all API contracts specified, all MCP prompts complete
- [x] Backend endpoints tested with pytest before frontend built
- [x] Frontend pages specify exact API endpoints, auth headers, and response shapes
- [x] `get_redis_client()` from Track C Task 3 used throughout — not the private `_r`
- [x] Task registry from Track C Task 5 used by celery endpoints
