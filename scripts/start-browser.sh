#!/usr/bin/env bash
# Start (or verify) a persistent-profile Chrome with a CDP endpoint,
# using the profile registry as the single source of truth.
#
#   scripts/start-browser.sh execution [--headless]
#
# If the CDP port is already alive, nothing is started (profiles must
# persist across sessions — that is the whole point).
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/.."
PROFILE="${1:-execution}"
HEADLESS=0
[[ "${2:-}" == "--headless" ]] && HEADLESS=1

REGISTRY="$(python3 - "$PROFILE" <<'EOF'
import sys
sys.path.insert(0, ".")
from agentdrop.registry.registry import ProfileRegistry
p = ProfileRegistry.load().resolve(sys.argv[1])
print(f"{p.path} {p.cdp_port}")
EOF
)"
PROFILE_PATH="$(echo "$REGISTRY" | awk '{print $1}')"
CDP_PORT="$(echo "$REGISTRY" | awk '{print $2}')"

if curl -sf --max-time 2 "http://127.0.0.1:${CDP_PORT}/json/version" >/dev/null; then
  echo "[start-browser] profile '$PROFILE' already online on CDP :${CDP_PORT}"
  exit 0
fi

# Find a Chrome binary
CHROME=""
for c in google-chrome google-chrome-stable chromium chromium-browser; do
  if command -v "$c" >/dev/null 2>&1; then CHROME="$(command -v "$c")"; break; fi
done
if [[ -z "$CHROME" && -d "$HOME/.cache/ms-playwright" ]]; then
  CHROME="$(find "$HOME/.cache/ms-playwright" -name chrome -type f 2>/dev/null | sort | tail -1 || true)"
fi
if [[ -z "$CHROME" ]]; then
  echo "[start-browser] ERROR: no Chrome/Chromium binary found. Install one or run: npx playwright install chromium" >&2
  exit 1
fi

mkdir -p "$PROFILE_PATH"
FLAGS=(--remote-debugging-port="$CDP_PORT" --user-data-dir="$PROFILE_PATH"
  --no-first-run --no-default-browser-check --disable-background-networking
  --window-size=1280,800)
if [[ "$HEADLESS" == "1" ]]; then
  FLAGS+=(--headless=new)
fi

echo "[start-browser] starting '$PROFILE' (CDP :${CDP_PORT}, profile: $PROFILE_PATH)"
"$CHROME" "${FLAGS[@]}" "about:blank" >/dev/null 2>&1 &
BROWSER_PID=$!

for i in $(seq 1 30); do
  if curl -sf --max-time 2 "http://127.0.0.1:${CDP_PORT}/json/version" >/dev/null; then
    echo "[start-browser] online (pid $BROWSER_PID). Health: python3 -m agentdrop.cli registry status"
    exit 0
  fi
  sleep 0.5
done
echo "[start-browser] ERROR: CDP :${CDP_PORT} did not come up" >&2
exit 1
