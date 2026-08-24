#!/usr/bin/env bash
# Option A: full AgentDrop deployment on the target machine.
# Installs Hermes, browser dependencies, the Python engine venv, the
# Hermes config tree, and registers the computer-use MCP server.
#
#   scripts/install-hermes.sh
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."

echo "[1/6] Hermes"
if command -v hermes >/dev/null 2>&1; then
  echo "  hermes already installed: $(hermes --version 2>/dev/null || true)"
else
  curl -fsSL https://hermes-agent.nousresearch.com/install.sh | bash
fi

echo "[2/6] Browser (Chromium for CDP + Playwright as fallback launcher)"
npx playwright install chromium || echo "  (playwright chromium skipped — install Chrome manually)"

echo "[3/6] Python engine venv"
python3 -m venv .venv 2>/dev/null || true
./.venv/bin/pip install --quiet --upgrade pip
./.venv/bin/pip install --quiet -r requirements.txt
echo "  engine deps installed"

echo "[4/6] Hermes config -> ~/.hermes"
HERMES_HOME="${HERMES_HOME:-$HOME/.hermes}" bash hermes-config/install.sh

echo "[5/6] Register computer-use MCP server"
if command -v hermes >/dev/null 2>&1; then
  hermes mcp add computer-use \
    --command node \
    --args "$PWD/mcp/server/server.js" \
    --env "CDP_PORT=9223,CDP_HOST=127.0.0.1" \
    || echo "  (run 'hermes mcp add' manually — see hermes-config/hermes.yaml)"
fi

echo "[6/6] Smoke check"
./.venv/bin/python -m agentdrop.cli registry status || true
echo
echo "Done. Next steps:"
echo "  1. source ~/.hermes/agentdrop.env"
echo "  2. scripts/start-browser.sh execution        # start the PoC browser profile"
echo "  3. ./.venv/bin/python -m agentdrop.cli poc   # offline benchmark (no network)"
echo "  4. export AGENTDROP_VISION_MODEL=gpt-5.6-luna OPENAI_API_KEY=..."
echo "  5. ./.venv/bin/python -m agentdrop.cli run --campaign agentdrop/campaigns/loqua.yaml --profile execution --url https://LIVE_LOQUA_URL"
