.PHONY: setup run mcp test eval-dev eval-milestone ui samples schemas
PY=.venv/bin/python

setup:
	python3 -m venv .venv && .venv/bin/pip install -q -e ".[dev]"
run:
	./run.sh
mcp:
	$(PY) -m pharos.mcp_server
test:
	$(PY) -m pytest -q
eval-dev:
	$(PY) -m pharos.evaluate --set dev
eval-milestone:
	$(PY) -m pharos.evaluate --set milestone
ui:
	cd ui && npm install --no-audit --no-fund && npm run build
schemas:
	$(PY) scripts/export_schemas.py
samples:
	$(PY) scripts/make_samples.py && $(PY) scripts/make_samples_milestone.py
