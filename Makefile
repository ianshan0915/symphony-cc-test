.PHONY: help up down build test lint clean ps logs

COMPOSE := docker compose
COMPOSE_TEST := docker compose -f docker-compose.test.yml

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'

# ---------------------------------------------------------------------------
# Local development services
# ---------------------------------------------------------------------------

up: ## Start local dev services (Postgres + Redis)
	$(COMPOSE) up -d
	@echo "Waiting for services to be healthy..."
	@$(COMPOSE) exec postgres pg_isready -U symphony -q --timeout=30 || true
	@echo "Services are up. Postgres: localhost:5432  Redis: localhost:6379"

down: ## Stop and remove local dev services
	$(COMPOSE) down

ps: ## Show running service status
	$(COMPOSE) ps

logs: ## Tail service logs (usage: make logs or make logs s=postgres)
	$(COMPOSE) logs -f $(s)

# ---------------------------------------------------------------------------
# Build / Test / Lint (stubs — filled in by later tickets)
# ---------------------------------------------------------------------------

build: ## Build all services
	@echo "build: not yet implemented — see backend/ and frontend/ tickets"

test: ## Run all tests
	@echo "test: not yet implemented — see backend/ and frontend/ tickets"

lint: ## Run linters
	@echo "lint: not yet implemented — see backend/ and frontend/ tickets"

# ---------------------------------------------------------------------------
# CI test services
# ---------------------------------------------------------------------------

test-up: ## Start CI test services (ephemeral)
	$(COMPOSE_TEST) up -d --wait

test-down: ## Stop CI test services
	$(COMPOSE_TEST) down

# ---------------------------------------------------------------------------
# Housekeeping
# ---------------------------------------------------------------------------

clean: ## Remove volumes and all stopped containers
	$(COMPOSE) down -v --remove-orphans
	$(COMPOSE_TEST) down -v --remove-orphans 2>/dev/null || true
