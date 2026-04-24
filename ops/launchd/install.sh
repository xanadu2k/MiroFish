#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PLIST_SRC="${ROOT_DIR}/ops/launchd/com.mirofish.dev.plist"
LAUNCH_AGENTS_DIR="${HOME}/Library/LaunchAgents"
PLIST_DST="${LAUNCH_AGENTS_DIR}/com.mirofish.dev.plist"

mkdir -p "${LAUNCH_AGENTS_DIR}"
cp "${PLIST_SRC}" "${PLIST_DST}"

# (Re)load
launchctl bootout "gui/$(id -u)/com.mirofish.dev" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "${PLIST_DST}"
launchctl enable "gui/$(id -u)/com.mirofish.dev" || true
launchctl kickstart -k "gui/$(id -u)/com.mirofish.dev"

echo "Installed & started: com.mirofish.dev"
echo "Logs:"
echo "  /tmp/mirofish-launchd.out.log"
echo "  /tmp/mirofish-launchd.err.log"

