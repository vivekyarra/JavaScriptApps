#!/usr/bin/env bash
# One command: create the environment, install, and start the Pharos workbench (UI + API) on http://127.0.0.1:${PORT:-8000}
set -euo pipefail
cd "$(dirname "$0")"
PY="${PYTHON:-python3}"
[ -d .venv ] || "$PY" -m venv .venv
# shellcheck disable=SC1091
. .venv/bin/activate
pip install -q --upgrade pip >/dev/null 2>&1 || true
pip install -q -e ".[dev]"
if [ ! -f ui/dist/index.html ] && command -v npm >/dev/null 2>&1; then
  (cd ui && npm install --no-audit --no-fund && npm run build)
fi
echo "Pharos workbench: http://127.0.0.1:${PORT:-8000}   (MCP server: python -m pharos.mcp_server)"
exec python -m pharos.api --host "${HOST:-127.0.0.1}" --port "${PORT:-8000}"
