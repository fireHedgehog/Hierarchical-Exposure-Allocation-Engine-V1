PYTHON := .venv/bin/python
PIP := .venv/bin/pip

.PHONY: setup seed-demo build serve dev-api dev-ui test verify

setup:
	python3 -m venv .venv
	$(PIP) install -r backend/requirements.txt
	npm --prefix frontend ci

seed-demo:
	$(PYTHON) -m backend.seed

build:
	npm --prefix frontend run build

serve: build
	$(PYTHON) -m uvicorn backend.main:app --host 127.0.0.1 --port 8000

dev-api:
	$(PYTHON) -m uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000

dev-ui:
	npm --prefix frontend run dev -- --host 127.0.0.1

test:
	$(PYTHON) -m pytest -q
	npm --prefix frontend test

verify: test build
