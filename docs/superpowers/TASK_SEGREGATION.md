# AltairGO — Task Segregation by Tool

Pick up a task, run it in the right tool, done. No overlap between tools.

---

## Codex — Track C: Backend Hardening

**Why Codex:** Self-contained, fully-specced Python tasks. No project context needed — patterns provided inline in the plan.

**Plan file:** `docs/superpowers/plans/2026-04-08-track-c-backend-hardening.md`

| Task | What | File(s) |
|---|---|---|
| C1 | Structured JSON logging middleware | `backend/middleware/logging.py` (NEW) |
| C2 | Consistent error envelopes across all 18 routes | `backend/routes/*.py` (18 files) |
| C3 | `/api/metrics` admin endpoint | `backend/metrics.py` (NEW) |
| C4 | `POST /api/trip/:id/reorder-activity` | `backend/routes/trip_tools.py` |
| C5 | Celery retry + Redis error tracking on all 12 tasks | `backend/celery_tasks.py` + `backend/tasks/task_registry.py` (NEW) |

**Start here:**
```
Open: docs/superpowers/plans/2026-04-08-track-c-backend-hardening.md
Run tasks C1 → C2 → C3 → C4 → C5 in order.
Test after each: python -m pytest backend/tests/ -q --tb=short
```

**Do NOT touch:** any frontend files, admin.py beyond error envelopes, or celery_config.py

---

## Claude Code Sonnet — Track B: Admin Ops Console

**Why Claude Code:** Needs deep understanding of existing Flask blueprints, admin auth patterns, and React admin page structure. Multi-file orchestration.

**Plan file:** `docs/superpowers/plans/2026-04-08-track-b-admin-ops-console.md`

**Prerequisite:** Track C Task 5 complete (writes Redis keys this track reads). Without it, admin endpoints still work — just show no last_run data.

| Task | What | Tool step |
|---|---|---|
| B1 | Admin Celery list + trigger endpoints | Claude Code → edit `backend/routes/admin.py` |
| B2 | Admin health + settings + activity feed endpoints | Claude Code → edit `backend/routes/admin.py` |
| B3 | Admin nav update + route registration | Claude Code → edit `AdminDashboard.jsx` + `App.jsx` |
| B4 | CeleryMonitorPage | Claude Code + **21st.dev MCP** |
| B5 | SystemHealthPage | Claude Code + **21st.dev MCP** |
| B6 | SettingsPage | Claude Code + **21st.dev MCP** |
| B7 | ActivityFeedPage | Claude Code + **21st.dev MCP** |
| B8 | Integration smoke test | Claude Code (manual + pytest) |

**Start here:**
```
Open: docs/superpowers/plans/2026-04-08-track-b-admin-ops-console.md
Run tasks B1 → B2 (backend) → B3 → B4 → B5 → B6 → B7 → B8 (frontend)
```

**Do NOT touch:** PlannerPage, DashboardPage, or any non-admin frontend pages (those are Track A)

---

## Gemini CLI — Track A Step 1: Design Audit

**Why Gemini CLI:** 1M token context reads the ENTIRE frontend codebase in one pass. This is impossible in Claude Code without burning context.

**Plan file:** `docs/superpowers/plans/2026-04-08-track-a-frontend-visual-identity.md` → Task 1

| Task | What | Output |
|---|---|---|
| A1 | Full frontend audit: color inventory, component inventory, token spec | `D:/Projects/AltairGO-Platform/docs/design-audit.md` |

**Gemini CLI prompt:** See Task 1 in the plan file — copy the full prompt block.

**Feed Gemini these directories:**
```
D:/Projects/AltairGO-Platform/src/pages/
D:/Projects/AltairGO-Platform/src/components/
D:/Projects/AltairGO-Platform/src/index.css
```

**Output:** A `design-audit.md` that Claude Code reads before building the component library.

---

## Claude Code Sonnet — Track A Step 2: Component Library + Page Redesigns

**Why Claude Code + 21st.dev MCP:** After Gemini's audit, Claude Code executes: build tokens, invoke 21st.dev MCP for each component, wire pages.

**Plan file:** `docs/superpowers/plans/2026-04-08-track-a-frontend-visual-identity.md` → Tasks 2–10

**Prerequisite:** Gemini A1 audit complete and `design-audit.md` exists.

| Task | What | Tool |
|---|---|---|
| A2 | Design token CSS + typography + animations | Claude Code (write files) |
| A3 | 9-component UI library | Claude Code + **21st.dev MCP** (one MCP call per component) |
| A4 | HomePage redesign | Claude Code + **21st.dev MCP** |
| A5 | PlannerPage redesign | Claude Code + **21st.dev MCP** |
| A6 | DashboardPage + TripViewerPage redesign | Claude Code + **21st.dev MCP** |
| A7 | Auth pages redesign | Claude Code + **21st.dev MCP** |
| A8 | BlogsPage + DiscoverPage redesign | Claude Code + **21st.dev MCP** |
| A9 | Activity reorder UI (needs Track C Task 4 first) | Claude Code |
| A10 | Final build verification | Claude Code |

---

## Execution Order (parallel but with one dependency)

```
┌─────────────────────────────────────────────────────┐
│  Parallel — start all three at once                 │
│                                                     │
│  Codex:        C1 → C2 → C3 → C4 → C5             │
│                                                     │
│  Claude Code:  B1 → B2 → B3 → B4 → B5 → B6 → B7  │
│                                                     │
│  Gemini CLI:   A1 (audit)                          │
│  then Claude:  A2 → A3 → A4 → A5 → A6 → A7 → A8  │
│                                                     │
│  Dependency: A9 must wait for C4 to be done        │
└─────────────────────────────────────────────────────┘
```

---

## File Ownership (no conflicts)

| Area | Owner | Files |
|---|---|---|
| `backend/middleware/` | Codex | NEW |
| `backend/metrics.py` | Codex | NEW |
| `backend/celery_tasks.py` | Codex | MODIFY |
| `backend/tasks/task_registry.py` | Codex | NEW |
| `backend/routes/*.py` (error envelopes) | Codex | MODIFY (all 18) |
| `backend/routes/admin.py` (new endpoints) | Claude Code | MODIFY (append only) |
| `src/pages/admin/*` | Claude Code | NEW + MODIFY |
| `src/design-system/` | Claude Code | NEW |
| `src/components/ui/` | Claude Code | NEW |
| `src/pages/` (non-admin) | Claude Code | REDESIGN |

**The one overlap to manage:** Both Codex (error envelopes, C2) and Claude Code (admin endpoints, B1-B2) modify `backend/routes/admin.py`. Run C2 first or do admin.py in one pass.

---

## Quick Reference: Which Plan for What

| "I want to..." | Plan | Section |
|---|---|---|
| Add logging to Flask | Track C | Task 1 |
| Normalize error responses | Track C | Task 2 |
| See /api/metrics working | Track C | Task 3 |
| Let users reorder activities | Track C + Track A | Task 4 + Task 9 |
| Make Celery tasks retry on failure | Track C | Task 5 |
| See Celery status in admin | Track B | Tasks 1 + 4 |
| Monitor Redis/worker health | Track B | Tasks 2 + 5 |
| Edit EngineSetting in UI | Track B | Tasks 2 + 6 |
| See system event log | Track B | Tasks 2 + 7 |
| Audit all frontend design decisions | Track A | Task 1 (Gemini) |
| Build Button/Card/Modal components | Track A | Task 3 |
| Redesign the landing page | Track A | Task 4 |
| Redesign the trip planner | Track A | Task 5 |
| Redesign the dashboard | Track A | Task 6 |
