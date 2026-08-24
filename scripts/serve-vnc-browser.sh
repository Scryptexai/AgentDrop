#!/usr/bin/env bash
# Start a VNC-accessible browser for MANUAL debugging of agent runs.
# Uses the `alhena` Docker image (password: alhena) exposing VNC :5900
# and noVNC :6080. Watch the agent act in a real window while it runs.
#
#   scripts/serve-vnc-browser.sh
set -euo pipefail

PORT_VNC="${PORT_VNC:-5900}"
PORT_NOVNC="${PORT_NOVNC:-6080}"

if ! command -v docker >/dev/null 2>&1; then
  echo "docker is not available in this environment." >&2
  echo "Run this on a machine with Docker; e.g. the target host." >&2
  exit 1
fi

echo "Starting noVNC browser (VNC password: alhena)"
echo "  VNC:    localhost:${PORT_VNC}"
echo "  noVNC:  http://localhost:${PORT_NOVNC}/vnc.html?password=alhena"

docker run -d --rm \
  -p "${PORT_VNC}:5900" \
  -p "${PORT_NOVNC}:6080" \
  --name agentdrop-vnc \
  alhena

echo "Container 'agentdrop-vnc' started. Stop with: docker stop agentdrop-vnc"
