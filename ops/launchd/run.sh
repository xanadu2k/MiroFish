#!/usr/bin/env bash
set -euo pipefail

ROOT="/Volumes/MasterDisk/Documents/Github/MiroFish"

is_listening() {
  local port="$1"
  lsof -nP -iTCP:"${port}" -sTCP:LISTEN >/dev/null 2>&1
}

# If something is already bound, don't start a duplicate instance.
if is_listening 5555 && is_listening 5556; then
  echo "[run.sh] 5555/5556 already listening; skip start."
  exit 0
fi

cd "${ROOT}"
export FLASK_HOST=0.0.0.0
export FLASK_PORT=5556

exec npm run dev

