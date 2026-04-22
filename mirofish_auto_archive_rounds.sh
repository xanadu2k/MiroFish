#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
API_BASE="${MIROFISH_API_BASE:-http://127.0.0.1:5556}"

echo "Auto-archive simulation rounds"
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
    echo "Error: backend is required for auto-archive."
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

# 1) Ask interval first (default 5)
DEFAULT_INTERVAL="${ARCHIVE_INTERVAL_SECONDS:-5}"
read -r -p "ARCHIVE_INTERVAL_SECONDS (default ${DEFAULT_INTERVAL}): " INTERVAL_INPUT
INTERVAL="${INTERVAL_INPUT:-$DEFAULT_INTERVAL}"

if ! [[ "${INTERVAL}" =~ ^[0-9]+([.][0-9]+)?$ ]]; then
  echo "Error: interval must be a number (seconds). Got: ${INTERVAL}"
  exit 1
fi

# 2) Detect currently running simulation_id (best-effort)
DEFAULT_SIM_ID="$(
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
for item in items:
    if item.get("runner_status") == "running":
        sid = item.get("simulation_id") or ""
        if sid:
            print(sid)
            sys.exit(0)
sys.exit(0)
PY
)"

if [[ -n "${DEFAULT_SIM_ID}" ]]; then
  read -r -p "Enter simulation_id (default ${DEFAULT_SIM_ID}): " SIM_ID_INPUT
  SIM_ID="${SIM_ID_INPUT:-$DEFAULT_SIM_ID}"
else
  read -r -p "Enter simulation_id (e.g. sim_e4a5691edbd3): " SIM_ID
fi

if [[ -z "${SIM_ID}" ]]; then
  echo "Error: simulation_id cannot be empty (no running simulation detected)."
  exit 1
fi

echo
echo "Starting archiver for: ${SIM_ID}"
echo "Interval: ${INTERVAL}s"
echo "Archives will be written to: backend/uploads/archives/${SIM_ID}/"
echo

cd "${SCRIPT_DIR}"

python3 -u "backend/scripts/auto_archive_rounds.py" \
  --simulation-id "${SIM_ID}" \
  --interval "${INTERVAL}"

