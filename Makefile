# MediSimplify developer commands. Run `make help` for a list.
# Requires Python 3.11 and Node.js >= 20.9 on PATH (override with PYTHON=... if needed).

PYTHON ?= python3.11
VENV := backend/.venv
PY := $(VENV)/bin/python

.PHONY: help setup check-node backend frontend test test-backend test-frontend e2e eval eval-offline \
        ingest fetch-sources samples fixtures

help:
	@echo "make setup          Create the Python venv, install all dependencies, build the index, write samples"
	@echo "make backend        Start the API on http://localhost:8000"
	@echo "make frontend       Start the web app on http://localhost:3000"
	@echo "make test           Backend tests + frontend lint, typecheck and production build"
	@echo "make e2e            Browser end-to-end tests (starts the servers if they are not running)"
	@echo "make eval-offline   Evaluation stages that need no API key"
	@echo "make eval           Full evaluation including the LLM comparison (needs GEMINI_API_KEY)"
	@echo "make ingest         Rebuild the knowledge-base index"
	@echo "make fetch-sources  Re-download approved MedlinePlus pages (review the diff afterwards)"
	@echo "make samples        Write synthetic sample PDFs to samples/"

check-node:
	@node -e 'const [a,b]=process.versions.node.split(".").map(Number); if (a<20||(a===20&&b<9)) { console.error("Node.js >= 20.9 is required (found " + process.versions.node + "). On Homebrew: export PATH=\"/opt/homebrew/opt/node/bin:$$PATH\""); process.exit(1) }'

$(PY):
	$(PYTHON) -m venv $(VENV)
	$(PY) -m pip install --upgrade pip

setup: $(PY) check-node
	$(PY) -m pip install -r backend/requirements-dev.txt
	cd frontend && npm install
	@test -f .env || (cp .env.example .env && echo "Created .env from .env.example")
	$(MAKE) ingest samples

backend:
	cd backend && .venv/bin/uvicorn app.main:app --reload --port 8000

frontend: check-node
	cd frontend && npm run dev

test: test-backend test-frontend

test-backend:
	cd backend && .venv/bin/pytest

test-frontend: check-node
	cd frontend && npm run lint && npm run typecheck && npm run build

e2e: check-node
	cd frontend && npx playwright install chromium && npm run e2e

eval:
	$(PY) evaluation/scripts/run_evaluation.py --delay 6

eval-offline:
	$(PY) evaluation/scripts/run_evaluation.py --stages extraction retrieval validator

ingest:
	cd backend && .venv/bin/python -m scripts.ingest_knowledge_base

fetch-sources:
	cd backend && .venv/bin/python -m scripts.fetch_sources

samples:
	cd backend && .venv/bin/python -m scripts.generate_sample_pdfs

fixtures:
	cd backend && .venv/bin/python -m scripts.generate_e2e_fixtures
