# ── RAG E-Commerce Assistant ──────────────────────────────────────────────────
# Top-level Makefile for building, running, and testing both services.

.PHONY: help build-order build-ai docker-up docker-down test-all \
        test-order test-ai lint-ai run-order run-ai clean

COMPOSE := docker compose
ORDER_DIR := order-service
AI_DIR := ai-assistant

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*##' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'

# ── Build ─────────────────────────────────────────────────────────────────────

build-order: ## Build the Spring Boot order-service JAR
	cd $(ORDER_DIR) && ./mvnw clean package -DskipTests -q

build-ai: ## Install AI assistant Python dependencies
	cd $(AI_DIR) && pip install -r requirements.txt -q

build-all: build-order build-ai ## Build both services

# ── Docker ────────────────────────────────────────────────────────────────────

docker-up: ## Start the full stack with Docker Compose
	$(COMPOSE) up --build -d
	@echo "\n  Order Service  → http://localhost:8080"
	@echo "  AI Assistant   → http://localhost:8000"
	@echo "  Weaviate       → http://localhost:8081\n"

docker-down: ## Stop and remove all containers
	$(COMPOSE) down -v

docker-logs: ## Tail logs from all services
	$(COMPOSE) logs -f --tail=100

# ── Test ──────────────────────────────────────────────────────────────────────

test-order: ## Run order-service unit tests
	cd $(ORDER_DIR) && ./mvnw test -q

test-ai: ## Run AI assistant pytest suite
	cd $(AI_DIR) && python -m pytest tests/ -v --tb=short

test-all: test-order test-ai ## Run all tests

# ── Local Dev ─────────────────────────────────────────────────────────────────

run-order: ## Run order-service locally (requires Postgres + Kafka)
	cd $(ORDER_DIR) && ./mvnw spring-boot:run

run-ai: ## Run AI assistant locally (requires Weaviate + Kafka)
	cd $(AI_DIR) && uvicorn src.main:app --reload --port 8000

# ── Lint / Format ─────────────────────────────────────────────────────────────

lint-ai: ## Lint the Python code with ruff
	cd $(AI_DIR) && python -m ruff check src/ tests/

format-ai: ## Auto-format the Python code with ruff
	cd $(AI_DIR) && python -m ruff format src/ tests/

# ── Clean ─────────────────────────────────────────────────────────────────────

clean: ## Remove build artefacts
	cd $(ORDER_DIR) && ./mvnw clean -q 2>/dev/null || true
	find $(AI_DIR) -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find $(AI_DIR) -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
