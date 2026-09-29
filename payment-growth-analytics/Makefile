# Payment Growth Analytics Platform — Makefile
# All targets are idempotent. `.venv` is created by `make setup`.
# Usage: `make setup && make demo`

PYTHON ?= python3
VENV   := .venv
PY     := $(VENV)/bin/python
PIP    := $(VENV)/bin/pip

.PHONY: setup generate-data load-data run-sql run-pipeline build-hyper test lint run-api run-app validate demo clean

# --- Environment ---
setup:
	@echo ">> Creating venv and installing dependencies"
	$(PYTHON) -m venv $(VENV)
	$(PIP) install --upgrade pip
	$(PIP) install -e ".[dev]"
	@echo ">> Setup complete. Activate with: source $(VENV)/bin/activate"

# --- Data generation ---
generate-data:
	@echo ">> Generating synthetic data (Parquet)"
	$(PY) scripts/generate_data.py

# --- Load into DuckDB ---
load-data:
	@echo ">> Loading raw parquet into DuckDB"
	$(PY) scripts/load_data.py

# --- Run SQL transformation layer ---
run-sql:
	@echo ">> Running SQL staging + marts + analytics"
	$(PY) scripts/run_sql.py

# --- Full pipeline: generate -> load -> sql -> analytics -> opportunities ---
run-pipeline:
	@echo ">> Running full pipeline"
	$(PY) scripts/run_pipeline.py

# --- Build Tableau Hyper extract ---
build-hyper:
	@echo ">> Building Tableau Hyper extract"
	$(PY) scripts/build_hyper.py

# --- Tests ---
test:
	@echo ">> Running tests"
	$(PY) -m pytest -ra -q

# --- Lint (lightweight: py_compile + import check) ---
lint:
	@echo ">> Linting (compile + import)"
	$(PY) -m py_compile $$(git ls-files '*.py' 2>/dev/null || find src app scripts tests -name '*.py')
	$(PY) -c "import src.api.main, src.data_generation.generator, src.analytics.metrics, src.rca.engine, src.opportunities.engine, src.tableau.hyper_builder"

# --- Run API ---
run-api:
	@echo ">> Starting FastAPI"
	$(VENV)/bin/uvicorn src.api.main:app --host 127.0.0.1 --port 8000 --reload

# --- Run Streamlit ---
run-app:
	@echo ">> Starting Streamlit"
	$(VENV)/bin/streamlit run app/streamlit/app.py

# --- Validate artifacts exist + are sane ---
validate:
	@echo ">> Validating project artifacts"
	$(PY) scripts/validate_project.py

# --- One-command demo ---
demo:
	@echo ">> Running end-to-end demo"
	$(PY) scripts/run_pipeline.py --demo
	@echo ""
	@echo "DATA GENERATED"
	@echo "PIPELINE COMPLETE"
	@echo "TABLES CREATED"
	@echo "HYPER CREATED"
	@echo "TESTS PASSED"
	@echo "API READY"
	@echo "STREAMLIT READY"

clean:
	rm -rf $(VENV) .pytest_cache .coverage htmlcov
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
