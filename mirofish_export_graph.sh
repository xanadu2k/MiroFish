#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
API_BASE="${MIROFISH_API_BASE:-http://127.0.0.1:5556}"

echo "Export Zep Standalone Graph snapshot"
echo

backend_ready() {
  local code
  code="$(curl -s -o /dev/null -w "%{http_code}" "${API_BASE}/api/simulation/history?limit=1" || true)"
  [[ "${code}" == "200" ]]
}

ensure_backend() {
  if backend_ready; then
    return 0
  fi

  echo "Backend not reachable at ${API_BASE}."
  read -r -p "Start backend now with 'npm run dev'? [Y/n]: " START_INPUT
  local start_ans="${START_INPUT:-Y}"
  if [[ ! "${start_ans}" =~ ^[Yy]$ ]]; then
    echo "Error: backend is required for graph export."
    exit 1
  fi

  echo "Starting backend/frontend in background..."
  (cd "${SCRIPT_DIR}" && npm run dev > /tmp/mirofish-dev.log 2>&1 &)

  echo "Waiting for backend to become ready..."
  local i
  for i in {1..30}; do
    if backend_ready; then
      echo "Backend is ready."
      return 0
    fi
    sleep 1
  done

  echo "Error: backend did not become ready in time."
  echo "Check logs: /tmp/mirofish-dev.log"
  exit 1
}

ensure_backend

# Detect default graph_id from backend history (best-effort):
# - prefer runner_status==running
# - else newest completed
DEFAULT_GRAPH_ID="$(
  MIROFISH_API_BASE="${API_BASE}" python3 - <<'PY' 2>/dev/null || true
import json
import os
import sys
from urllib.request import urlopen

base = os.environ.get("MIROFISH_API_BASE", "http://127.0.0.1:5556").rstrip("/")
URL = f"{base}/api/simulation/history?limit=20"
try:
    with urlopen(URL, timeout=1.5) as resp:
        data = json.loads(resp.read().decode("utf-8"))
except Exception:
    sys.exit(0)

items = data.get("data") or []
running = [i for i in items if i.get("runner_status") == "running" and i.get("graph_id")]
if running:
    print(running[0]["graph_id"])
    sys.exit(0)

completed = [i for i in items if i.get("runner_status") == "completed" and i.get("graph_id")]
completed.sort(key=lambda x: x.get("created_at") or "", reverse=True)
if completed:
    print(completed[0]["graph_id"])
PY
)"

if [[ -n "${DEFAULT_GRAPH_ID}" ]]; then
  read -r -p "Enter graph_id (default ${DEFAULT_GRAPH_ID}): " GRAPH_ID_INPUT
  GRAPH_ID="${GRAPH_ID_INPUT:-$DEFAULT_GRAPH_ID}"
else
  read -r -p "Enter graph_id (e.g. mirofish_a9640b9b61e944ba): " GRAPH_ID
fi

if [[ -z "${GRAPH_ID}" ]]; then
  echo "Error: graph_id cannot be empty."
  exit 1
fi

echo
echo "Exporting graph: ${GRAPH_ID}"
echo "Backend API: ${API_BASE}"
echo "Output dir: backend/uploads/graphs/${GRAPH_ID}/"
echo

cd "${SCRIPT_DIR}"

python3 -u "backend/scripts/export_graph_snapshot.py" \
  --graph-id "${GRAPH_ID}" \
  --api-base "${API_BASE}" \
  --include-history

