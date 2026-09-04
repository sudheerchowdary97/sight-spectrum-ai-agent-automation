# Agentic Invoice-to-Payment Automation — developer workflow.
# Usage: `make <target>`. Docker (Python 3.12) is the canonical runtime.

.DEFAULT_GOAL := help
# Use the Compose v2 plugin if present, else fall back to the v1 standalone.
COMPOSE := $(shell if docker compose version >/dev/null 2>&1; then echo "docker compose"; \
	elif command -v docker-compose >/dev/null 2>&1; then echo "docker-compose"; \
	else echo "docker compose"; fi)

.PHONY: help
help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'

# ─── Local dev (host Python) ────────────────────────────────────────────────
.PHONY: install
install: ## Install package + dev/data extras into the active venv
	pip install -e ".[dev,data]"

.PHONY: lint
lint: ## Run ruff lint
	ruff check src tests

.PHONY: format
format: ## Auto-format with ruff
	ruff format src tests && ruff check --fix src tests

.PHONY: typecheck
typecheck: ## Run mypy
	mypy src

.PHONY: test
test: ## Run the test suite
	pytest

# ─── Docker Compose stack ───────────────────────────────────────────────────
.PHONY: up
up: ## Build & start the full stack (detached)
	$(COMPOSE) up -d --build

.PHONY: down
down: ## Stop the stack
	$(COMPOSE) down

.PHONY: logs
logs: ## Tail logs from all services
	$(COMPOSE) logs -f

.PHONY: ps
ps: ## Show running services
	$(COMPOSE) ps

.PHONY: ollama-pull
ollama-pull: ## Pull the required Ollama models into the running container
	$(COMPOSE) exec ollama ollama pull llama3.1:8b
	$(COMPOSE) exec ollama ollama pull nomic-embed-text

# ─── Data (Task 1) ──────────────────────────────────────────────────────────
.PHONY: data
data: ## Generate synthetic invoices, PO/GR master data, and ground truth
	python scripts/generate_synthetic_data.py

# ─── Pipeline CLIs (run inside the api container) ───────────────────────────
.PHONY: agent
agent: ## Run the agent over inbox invoices (extract→match→post/escalate→audit)
	$(COMPOSE) exec api python scripts/run_agent.py --limit 5

.PHONY: ar
ar: ## Apply AR remittances against open AR items
	$(COMPOSE) exec api python scripts/run_ar.py

.PHONY: eval
eval: ## Evaluate the pipeline vs ground truth → data/evaluation_report.{json,md}
	$(COMPOSE) exec api python scripts/run_eval.py --limit 20

.PHONY: rag-check
rag-check: ## Index POs and test fuzzy-vendor retrieval (hit@1)
	$(COMPOSE) exec api python scripts/rag_index_retrieve.py --sample 10

.PHONY: seed
seed: ## Generate data (in api container) and re-seed the mock ERP
	$(COMPOSE) exec api python scripts/generate_synthetic_data.py --out data
	$(COMPOSE) restart mock-erp

.PHONY: clean
clean: ## Remove caches and generated data
	rm -rf .pytest_cache .mypy_cache .ruff_cache htmlcov .coverage
	rm -rf data/inbox data/master data/generated data/ground_truth.json
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
