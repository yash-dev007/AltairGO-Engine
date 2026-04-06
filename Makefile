PYTHON ?= .venv/Scripts/python.exe
FRONTEND_DIR ?= dummy-frontend

.PHONY: dev dev-infra dev-backend dev-frontend dev-worker dev-beat run-all \
        prod-up prod-down prod-restart prod-logs prod-status \
        test lint build-frontend seed migrate clean

# ── Local Development ─────────────────────────────────────────────────────────

dev: dev-infra dev-backend

dev-infra:
	docker compose up -d postgres redis

dev-backend:
	$(PYTHON) -m flask --app backend.app:create_app run --port 5000 --reload

dev-frontend:
	cd $(FRONTEND_DIR) && npm run dev

dev-worker:
	$(PYTHON) -m celery -A backend.celery_config:celery_app worker --loglevel=info --pool=solo

dev-beat:
	$(PYTHON) -m celery -A backend.celery_config:celery_app beat --loglevel=info

run-all: dev-infra
	powershell -Command "Start-Process make dev-backend; Start-Process make dev-frontend; Start-Process make dev-worker; Start-Process make dev-beat"

# ── Testing ───────────────────────────────────────────────────────────────────

test:
	$(PYTHON) -m pytest backend/tests -q --tb=short

test-verbose:
	$(PYTHON) -m pytest backend/tests -v

# ── Production ────────────────────────────────────────────────────────────────

prod-up:
	docker compose up -d --build
	@echo "AltairGO Engine starting. Check health: make prod-status"

prod-down:
	docker compose down

prod-restart:
	docker compose restart web celery_worker celery_beat

prod-logs:
	docker compose logs -f --tail=100

prod-logs-web:
	docker compose logs -f web --tail=100

prod-logs-worker:
	docker compose logs -f celery_worker --tail=100

prod-status:
	docker compose ps
	@echo ""
	@echo "Health check:"
	@curl -sf http://localhost:5000/health | python -m json.tool || echo "  API not responding"

prod-build:
	docker compose build --no-cache

# ── Database & Seeds ──────────────────────────────────────────────────────────

seed-blogs:
	$(PYTHON) -m backend.scripts.seed_blogs

seed-all:
	$(PYTHON) -m backend.scripts.seed_data
	$(PYTHON) -m backend.scripts.seed_blogs

score:
	$(PYTHON) -m backend.scripts.score_attractions

embeddings:
	$(PYTHON) -m backend.scripts.generate_embeddings

# ── Frontend ─────────────────────────────────────────────────────────────────

lint:
	cd $(FRONTEND_DIR) && npm run lint

build-frontend:
	cd $(FRONTEND_DIR) && npm run build

# ── Cleanup ───────────────────────────────────────────────────────────────────

clean:
	docker compose down -v
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete 2>/dev/null || true
