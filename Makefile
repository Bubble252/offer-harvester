PYTHON ?= python
HOST ?= 127.0.0.1
PORT ?= 8000
WORKSPACE_DIR ?= workspace

.PHONY: help install run seed-demo run-demo demo verify test lint format docs security openapi public-boundary

help:
	@printf '%s\n' \
		'make install         Install runtime and development dependencies' \
		'make run             Start the local application' \
		'make seed-demo       Rebuild the anonymous demo workspace' \
		'make run-demo        Seed the demo and start it on PORT=8000' \
		'make verify          Run the complete repository release gate'

install:
	$(PYTHON) -m pip install -r app/backend/requirements.txt ruff

run:
	WORKSPACE_DIR=$(abspath $(WORKSPACE_DIR)) $(PYTHON) -m uvicorn --app-dir app/backend main:app --host $(HOST) --port $(PORT)

seed-demo:
	$(PYTHON) tools/seed_demo_workspace.py --workspace workspace.demo --reset

run-demo: seed-demo
	WORKSPACE_DIR=$(abspath workspace.demo) $(PYTHON) -m uvicorn --app-dir app/backend main:app --host $(HOST) --port $(PORT)

demo: run-demo

test:
	$(PYTHON) -m pytest -q

lint:
	$(PYTHON) -m ruff check app tests tools

format:
	$(PYTHON) -m ruff format --check app tests tools

docs:
	$(PYTHON) tools/lint_docs.py

security:
	$(PYTHON) tools/security_guards.py
	$(PYTHON) tools/public_boundary_check.py

openapi:
	$(PYTHON) tools/check_openapi_contract.py

verify: lint format test docs security openapi
	node --check app/frontend/app.js
	$(PYTHON) -m compileall -q app integrations tests
	npm --prefix integrations/deepseek_harness test
	npm --prefix integrations/deepseek_harness run check
	git diff --check
