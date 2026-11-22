#!/usr/bin/env bash
# Serves the project notebooks (with their saved outputs) at http://localhost:8888 (local only, no password).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PY="${PY:-/root/venv/bin/python}"
mkdir -p "$ROOT/runtime/logs"
if ! curl -sf http://127.0.0.1:8888/api >/dev/null 2>&1; then
  ( cd "$ROOT"; exec nohup "$PY" -m jupyter lab --no-browser --allow-root --ip=127.0.0.1 --port=8888 \
      --ServerApp.root_dir="$ROOT" --IdentityProvider.token='' --ServerApp.password='' ) > "$ROOT/runtime/logs/jupyter.log" 2>&1 &
  for _ in $(seq 30); do curl -sf http://127.0.0.1:8888/api >/dev/null 2>&1 && break; sleep 1; done
fi
echo "Notebooks: http://localhost:8888/lab/tree/notebooks"
