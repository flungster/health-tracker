SHELL := /bin/bash
COMPOSE := docker compose

.DEFAULT_GOAL := help

.PHONY: help
help: ## Show available targets
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-12s %s\n", $$1, $$2}'

.PHONY: install
install: ## Install Python and Node dependencies
	uv sync --directory api
	cd web && npm install

.PHONY: migrate
migrate: ## Apply database migrations (dbmate up)
	$(COMPOSE) run --rm migrate

.PHONY: migrate-down
migrate-down: ## Roll back one database migration (dbmate down 1)
	$(COMPOSE) run --rm migrate down 1

.PHONY: api
api: ## Run the FastAPI dev server (requires .env + a reachable Postgres)
	cd api && uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

.PHONY: web
web: ## Run the Vite dev server (proxies /api to localhost:8000)
	cd web && npm run dev

.PHONY: up
up: ## Build and start the full stack (web on :9090)
	$(COMPOSE) up --build -d

.PHONY: down
down: ## Stop the stack (volumes are kept)
	$(COMPOSE) down

.PHONY: logs
logs: ## Tail logs for all services
	$(COMPOSE) logs -f

.PHONY: test
test: ## Run API tests (requires `make up` for the database)
	cd api && uv run pytest

.PHONY: lint
lint: ## Lint and type-check API (ruff, mypy) and web (eslint, tsc)
	cd api && uv run ruff check . && uv run ruff format --check . && uv run mypy app
	cd web && npm run typecheck && npm run lint

.PHONY: seed
seed: ## Seed a demo user and sample activities (requires `make up`)
	cd api && uv run python -m app.seed

.PHONY: backup
backup: ## Back up the database + uploads to ./backups/<timestamp>/
	scripts/backup.sh

.PHONY: restore
restore: ## Restore a backup (requires the BACKUP=... dir from `make backup`)
	@test -n "$(BACKUP)" || { echo "Usage: make restore BACKUP=./backups/<timestamp>"; exit 1; }
	scripts/restore.sh "$(BACKUP)"

.PHONY: smoke
smoke: ## Run the end-to-end smoke script against a running stack
	scripts/e2e-smoke.sh
