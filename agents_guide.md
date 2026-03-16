# AI Agents Automation & Execution Guide

This guide explains how to run, manage, and automate the AI agents in the AltairGO Engine.

## 1. Local Execution (Development)

To run the complete system locally with all background agents active, use the new `run-all` command:

```powershell
make run-all
```

This will automatically:
1.  Start **Redis** (Infrastructure)
2.  Start **Flask Backend**
3.  Start **Vite Frontend**
4.  Start **Celery Worker** (Handles real-time and scheduled jobs)
5.  Start **Celery Beat** (Automated scheduler)

### Individual Commands
If you prefer to start them manually:
*   **Worker**: `make dev-worker`
*   **Scheduler**: `make dev-beat`

---

## 2. Automated Pipelines (Celery Beat)

The agents are configured to run autonomously on the following schedule (configured in `backend/celery_config.py`):

| Agent / Job | Frequency | Purpose |
| :--- | :--- | :--- |
| **OSM Ingestion** | Weekly (Sun 3 AM) | Pulls fresh mapping data. |
| **POI Enrichment** | Weekly (Mon 4 AM) | Fills data gaps via Wikidata/Wikipedia. |
| **Intelligence Scoring** | Monthly (1st, 5 AM) | Recalculates popularity and seasonality. |
| **Price Sync** | 2x Daily (6 AM/PM) | Scrapes live flight/hotel pricing. |
| **Cache Warmer** | Nightly (3:30 AM) | Pre-generates popular itineraries. |
| **Quality Scoring** | Nightly (4:30 AM) | Audits and grades saved trips. |

---

## 3. Manual Intervention (API & CLI)

### Triggering via Ops Dashboard
The easiest way to run an agent manually is through the **Ops Console** in the Frontend Dashboard.
1.  Login as Admin.
2.  Navigate to **AI Agent Hub**.
3.  Click the "Force" buttons for specific agents.

### Triggering via CLI (Scripts)
You can run the background scripts directly if you have terminal access:

```powershell
# Ingest OSM data for a specific city
.venv\Scripts\python.exe backend\scripts\ingest_osm_data.py --city Jaipur

# Run POI Enrichment
.venv\Scripts\python.exe backend\scripts\enrich_attractions.py

# Recalculate Scoring
.venv\Scripts\python.exe backend\scripts\score_attractions.py
```

### Triggering via REST API
You can also trigger jobs using a `POST` request to the backend:

**Endpoint**: `POST /api/ops/trigger-job`
**Payload**:
```json
{
  "job_name": "osm_ingestion"
}
```
*Valid job names: `osm_ingestion`, `enrichment`, `scoring`, `price_sync`, `destination_validation`, `cache_warm`, `quality_scoring`.*

---

## 4. Monitoring & Logs

*   **Celery Logs**: Watch the `dev-worker` terminal for real-time agent activity.
*   **Agent History**: View the history of all background jobs in the Dashboard Ops Console.
*   **Redis Check**: The agents require Redis. Ensure it's running via `docker ps` or `make dev-infra`.
