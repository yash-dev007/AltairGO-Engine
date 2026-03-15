# MVP Production Deployment & Operations Guide

This guide details everything required to host the AltairGO MVP, acquire necessary API keys, manage the AI agents, and run the complete system in production without terminal access.

---

## 1. Prerequisites and API Keys

The system requires several external services to function. You must register and obtain API keys for the following:

### Core Configuration
*   **Database (PostgreSQL + PostGIS):** Your architecture requires a spatial database. Sign up for **Supabase**, **Neon**, or use **Railway's Postgres plugin**. (Do not use standard generic Postgres hosts unless they explicitly support `postgis`).
*   **Message Broker & Cache (Redis):** Required for rate-limiting and Celery background agents. Sign up for **Upstash** (Serverless Redis) or use **Railway's Redis plugin**.
*   **JWT Secret:** Generate a long, secure random string for authentication.

### AI Engine APIs
*   **Google Gemini (GEMINI_API_KEY):** Go to [Google AI Studio](https://aistudio.google.com/) to get a free API key. This powers the orchestrator, memory agents, and itinerary validation.
*   **SerpApi (SERPAPI_API_KEY):** Go to [SerpApi](https://serpapi.com/) to get an API key. This powers the real-time context capabilities (weather, news, events).
*   **Pexels (PEXELS_API_KEY):** Go to [Pexels API](https://www.pexels.com/api/) to get an API key. This powers high-quality image retrieval for destinations and itineraries.

---

## 2. Infrastructure Deployment (Backend + Workers)

The easiest, most resilient host for your specific multi-container architecture is **Railway.app** because it natively supports [Dockerfile](file:///a:/lp/AltairGO-Engine-main/Dockerfile) builds and sidecar workers (Celery).

### Step-by-Step Railway Deployment:
1.  **Connect Repo:** Go to Railway, create a new project, and deploy from your GitHub Repo.
2.  **Add Postgres & Redis:** Inside your Railway project space, add the "PostgreSQL" and "Redis" plugins. (Ensure PostGIS is enabled on the Postgres instance using `CREATE EXTENSION postgis;`).
3.  **Deploy Web API:** 
    *   Railway will automatically use your [Dockerfile](file:///a:/lp/AltairGO-Engine-main/Dockerfile) and [railway.toml](file:///a:/lp/AltairGO-Engine-main/railway.toml).
    *   It will run `gunicorn backend.app:create_app()` as your main web server on `$PORT`.
4.  **Deploy Background Workers:** Create two *new* empty services linked to the *same* repo inside the same Railway project space. Override their startup commands:
    *   **Celery Worker:** `celery -A backend.celery_config:celery_app worker --loglevel=info`
    *   **Celery Beat (Scheduler):** `celery -A backend.celery_config:celery_app beat --loglevel=info`
5.  **Environment Variables:** Add all variables to all three services (Web, Worker, Beat):
    ```env
    FLASK_ENV=production
    TESTING=false
    DATABASE_URL=postgresql://user:pass@postgresql.railway.internal:5432/railway
    REDIS_URL=redis://default:pass@redis.railway.internal:6379/
    JWT_SECRET_KEY=put_your_secure_random_string_here
    ADMIN_ACCESS_KEY=put_your_secure_admin_login_pass_here
    GEMINI_API_KEY=your_gemini_key
    SERPAPI_API_KEY=your_serpapi_key
    PEXELS_API_KEY=your_pexels_key
    VALIDATION_STRICT=true
    RATELIMIT_ENABLED=true
    ```

---

## 3. Frontend Deployment (React Dashboard)

The frontend is a static React Single Page Application (SPA). It should be hosted on a CDN.

1.  **Update API URL:** In your local `dummy-frontend/.env` file, set the URL to your live Railway backend (e.g., `VITE_API_URL=https://altairgo-backend.up.railway.app`).
2.  **Build Payload:** Run `npm install` followed by `npm run build` in the frontend directory to produce the `dist/` folder.
3.  **Host on Vercel/Netlify:** Go to [Vercel](https://vercel.com/) or [Netlify](https://www.netlify.com/), create a new static project, and drag-and-drop the `dist/` folder, or link it directly to the frontend subfolder of your GitHub Repo.

---

## 4. Operating the AI Agents (Completely Self-Sustaining)

With the deployment steps above completed, **you never need to use a terminal again.**

The architecture is designed to run totally autonomously through background jobs. Here is exactly how the workflows operate and how you can manage them from the React Dashboard.

### Scheduled Autonomy (Celery Beat)
Because you deployed the `celery_beat` container, your AI pipelines run on an automated schedule without human intervention:

*   **Ingestion (Weekly):** Pulls raw mapping data ([run_osm_ingestion](file:///a:/lp/AltairGO-Engine-main/backend/celery_tasks.py#32-41)).
*   **Enrichment (Weekly):** Fills in data gaps using Wikidata/Wikipedia ([run_enrichment](file:///a:/lp/AltairGO-Engine-main/backend/celery_tasks.py#43-52)).
*   **Scoring (Monthly):** Recalculates intelligence stats like seasonal popularity ([run_scoring](file:///a:/lp/AltairGO-Engine-main/backend/celery_tasks.py#54-63)).
*   **Price Sync (2x Daily):** Scrapes live pricing ([run_price_sync](file:///a:/lp/AltairGO-Engine-main/backend/celery_tasks.py#65-74)).
*   **Cache Warming (Nightly):** Pre-generates common trips so users see instant load times ([run_cache_warm](file:///a:/lp/AltairGO-Engine-main/backend/celery_tasks.py#101-113)).
*   **Quality Scoring (Nightly):** The AI autonomously grades user-saved trips for logical flow ([run_quality_scoring](file:///a:/lp/AltairGO-Engine-main/backend/celery_tasks.py#124-136)).

### Real-time Agent Intervention (Celery Worker)
When a user requests a trip on the frontend:
1.  The Web API receives the payload, saves it as an [AsyncJob](file:///a:/lp/AltairGO-Engine-main/backend/models.py#304-314) (queued), and immediately returns a `202 Accepted` to the UI to keep things fast.
2.  The Celery Worker instantly picks up the job.
3.  The agent pipeline (MemoryAgent -> MCPContextAgent -> TokenOptimizer -> Gemini -> ItineraryQAAgent) spins up, validates the trip logic, and marks the job as `completed` in the database.
4.  The Frontend UI seamlessly polls for completion and displays the generated trip automatically.

### Manual Operations Center Control
If you ever need to manually force the AI to do something without waiting for the automated schedule, log in to your hosted Frontend Dashboard using the `ADMIN_ACCESS_KEY`. 

Navigate to the **AI Agent Hub / Ops Console** tab in the UI. Here you can click buttons to trigger backend jobs instantly via the standard API endpoints we integrated (`POST /ops/trigger-job`):
*   Click **Force OSM Data Ingestion**.
*   Click **Force Cache Warmer Agent**.
*   Click **Force Destination Validation Agent**.

Those buttons dispatch a command directly to Celery, and you can watch the agent history tab populate with the success or failure results in real time.
