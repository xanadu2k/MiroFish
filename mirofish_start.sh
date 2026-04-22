#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
API_BASE="${MIROFISH_API_BASE:-http://127.0.0.1:5556}"
FRONTEND_URL="${MIROFISH_FRONTEND_URL:-http://localhost:5555}"

is_backend_ready() {
  local code
  code="$(curl -s -o /dev/null -w "%{http_code}" "${API_BASE}/api/simulation/history?limit=1" || true)"
  [[ "${code}" == "200" ]]
}

is_frontend_ready() {
  local code
  code="$(curl -s -o /dev/null -w "%{http_code}" "${FRONTEND_URL}" || true)"
  [[ "${code}" == "200" ]]
}

echo "MiroFish starter"
echo

if is_backend_ready && is_frontend_ready; then
  echo "Services are already running."
  echo "- Frontend: ${FRONTEND_URL}"
  echo "- Backend : ${API_BASE}"
  exit 0
fi

echo "Starting MiroFish with npm run dev ..."
(cd "${SCRIPT_DIR}" && npm run dev > /tmp/mirofish-dev.log 2>&1 &)

echo "Waiting for backend/frontend to become ready..."
for _ in {1..40}; do
  if is_backend_ready && is_frontend_ready; then
    echo "MiroFish is ready."
    echo "- Frontend: ${FRONTEND_URL}"
    echo "- Backend : ${API_BASE}"
    echo "- Logs    : /tmp/mirofish-dev.log"
    exit 0
  fi
  sleep 1
done

echo "Startup timed out. Check logs: /tmp/mirofish-dev.log"
exit 1

