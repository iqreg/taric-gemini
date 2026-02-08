# ===== CodeSandbox Makefile (no venv, PEP-668 safe) =====

PYTHON := python3
PIP := $(PYTHON) -m pip

APP := backend:app
HOST := 0.0.0.0
PORT := 8000

.PHONY: help deps run run-reload check clean

help:
	@echo "Available targets:"
	@echo "  make deps        -> install Python dependencies (CodeSandbox)"
	@echo "  make run         -> start uvicorn"
	@echo "  make run-reload  -> start uvicorn with --reload"
	@echo "  make check       -> show python & pip status"
	@echo "  make clean       -> no-op (no venv used)"

deps:
	$(PIP) install -U pip wheel --break-system-packages
	$(PIP) install -r requirements.txt --break-system-packages

run:
	$(PYTHON) -m uvicorn $(APP) --host $(HOST) --port $(PORT)

run-reload:
	$(PYTHON) -m uvicorn $(APP) --host $(HOST) --port $(PORT) --reload

check:
	$(PYTHON) --version
	$(PIP) --version
	$(PIP) list | head -20

clean:
	@echo "Nothing to clean (no virtualenv in use)."
