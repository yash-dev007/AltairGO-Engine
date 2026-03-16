PYTHON ?= .venv/Scripts/python.exe
FRONTEND_DIR ?= dummy-frontend

.PHONY: dev dev-infra dev-backend dev-frontend test lint build-frontend clean

dev:
	$(MAKE) dev-infra
	$(MAKE) dev-backend

dev-infra:
	docker compose up -d postgres redis

dev-backend:
	cd backend && ..\\$(PYTHON) -m flask --app backend.app:create_app run --port 5000 --reload

dev-frontend:
	cd $(FRONTEND_DIR) && npm run dev

dev-worker:
	$(PYTHON) -m celery -A backend.celery_config:celery_app worker --loglevel=info --pool=solo

dev-beat:
	$(PYTHON) -m celery -A backend.celery_config:celery_app beat --loglevel=info

run-all:
	$(MAKE) dev-infra
	powershell -Command "Start-Process make dev-backend; Start-Process make dev-frontend; Start-Process make dev-worker; Start-Process make dev-beat"

test:
	$(PYTHON) -m pytest backend/tests -q

lint:
	cd $(FRONTEND_DIR) && npm run lint

build-frontend:
	cd $(FRONTEND_DIR) && npm run build

clean:
	docker compose down
