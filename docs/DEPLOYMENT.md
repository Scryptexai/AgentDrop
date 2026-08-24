# Deployment

Two deployment options, matching the problem statement. This repo is the
foundation for both.

## Option A — Full install (target machine with browser + Hermes)

```bash
# 1. Clone + full install
git clone <repo> agentdrop && cd agentdrop
scripts/install-hermes.sh
source ~/.hermes/agentdrop.env

# 2. Start the execution profile's browser (CDP :9223)
scripts/start-browser.sh execution          # add --headless if no display

# 3. Optional: watch the agent act in a real window (VNC/noVNC)
scripts/serve-vnc-browser.sh                # needs Docker (VNC pw: alhena)

# 4. Offline benchmark first (proves the engine, no network needed)
.venv/bin/python -m agentdrop.cli poc

# 5. Live benchmark on the real Loqua site
export AGENTDROP_VISION_MODEL=gpt-5.6-luna
export OPENAI_API_KEY=...                    # or HNCSEC proxy key
export AGENTDROP_VISION_BASE_URL=https://your-proxy/v1   # optional
.venv/bin/python -m agentdrop.cli run \
  --campaign agentdrop/campaigns/loqua.yaml \
  --profile execution \
  --url https://LIVE_LOQUA_URL \
  --evidence runs/live-$(date +%s)
```

Hermes MCP integration (already registered by the installer):
`hermes mcp add computer-use --command node --args <repo>/mcp/server/server.js --env CDP_PORT=9223`.

## Option B — Config-only build (this repo, push to GitHub)

If a machine can't run full browser automation, the repo **is** the
deliverable:

- `hermes-config/` — the complete `~/.hermes/` tree: 1 commander + 7
  workers (all vision-first), the airdrop-farming skill, the memory
  system, and the security policy. `hermes-config/install.sh` drops it
  into `~/.hermes/` when you are ready.
- `agentdrop/` + `fakesites/` — the full browser-automation layer (CDP
  connection + vision loop) implemented as testable code, proven by the
  offline PoC in this very sandbox.
- `data/profile_registry.json` — the profile single-source-of-truth.
- `mcp/server/` — the CDP computer-use MCP server.

Push this to GitHub; any machine then does Option A in one script.

## Profile registry (the consistency fix)

`data/profile_registry.json` is the single source of truth for
profile → (path, CDP port, accounts). Workers resolve through
`ProfileRegistry`; nothing hardcodes a path or port.

```bash
.venv/bin/python -m agentdrop.cli registry status
# [OFFLINE] discord    cdp=127.0.0.1:9224  accounts=google,email,discord,x
# [OFFLINE] execution  cdp=127.0.0.1:9223  accounts=google,email,telegram,discord,phantom,okx
# [OFFLINE] hana       cdp=127.0.0.1:9222  accounts=google,email,x,kucoin,gleam
```

`scripts/start-browser.sh <profile>` starts the matching Chrome; the
registry reports ONLINE/OFFLINE so drift is visible, not silent.

## Sandbox note

This Arena sandbox has **no browser binary and no root** (the Playwright
CDN is blocked), so the live browser tiers can't run *here*. That is
exactly the case Option B is designed for: the engine is fully built and
validated offline against the pixel-rendered replica, and the real-browser
E2E (`tests/e2e/`) activates automatically wherever a Chromium + API key
exist.

## Security posture (default, non-negotiable)

- `stop_on_captcha: true` — halt + evidence screenshot, never solve.
- `require_manual_approval_for_wallet: true` — headless runs can never
  sign; even with approval the agent observes and stops.
- `never_store_private_keys: true` — key-shaped strings rejected at load.
- Evidence retained for any halted run until the halt is resolved.
