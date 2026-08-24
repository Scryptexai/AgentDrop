# Real-browser E2E benchmark

This directory contains the **real-browser** version of the Loqua
benchmark. It is separate from the offline PoC (`poc/`, `tests/test_loop.py`)
because it needs a real Chromium with a CDP endpoint and a real vision
model API key.

## What runs where

| Layer | Offline PoC (this sandbox, CI) | Real E2E (target machine) |
|---|---|---|
| Screen | `fakesites/loqua/site.py` — Pillow-rendered PNGs | real Chromium viewport via `Page.captureScreenshot` |
| Input | in-memory pixel hit-testing | CDP `Input.dispatchMouseEvent` / `Input.dispatchKeyEvent` |
| Vision model | `ScriptedVisionPlanner` (ground-truth oracle) | `gpt-5.6-luna` (or any vision model) via `OpenAICompatiblePlanner` |
| Site | same 5-step flow, pixel-rendered | `loqua_site/index.html` served over HTTP |

## Run it

```bash
# 1. Start the site
python3 -m http.server 8137 --directory tests/e2e/loqua_site

# 2. Start a real browser with CDP (or use your registry profile)
scripts/start-browser.sh execution     # or: any chromium with --remote-debugging-port=9223

# 3. Point the engine at it and run the benchmark
export AGENTDROP_VISION_MODEL="gpt-5.6-luna"        # confirmed: vision + computer-use capable
export OPENAI_API_KEY="..."                          # or your HNCSEC proxy key
export AGENTDROP_VISION_BASE_URL="https://your-proxy/v1"   # optional (e.g. HNCSEC)
export AGENTDROP_E2E_SITE="http://127.0.0.1:8137/"

pytest tests/e2e -v
```

## How the harness works

1. `browser.pytest fixture` finds a CDP endpoint:
   - `AGENTDROP_E2E_CDP=127.0.0.1:9223` if you set it, else
   - a Playwright-managed Chromium binary if `playwright` is installed, else
   - **skips** (so CI without a browser stays green).
2. The engine's `BrowserSession.connect()` talks raw CDP to that endpoint —
   the same code path production workers use.
3. The campaign is the same `agentdrop/campaigns/loqua.yaml`; `{LIVE_URL}` is
   replaced with the local site URL.
4. The vision model must complete all 5 tasks in < 50 steps with ≥ 90%
   first-attempt click accuracy (the same targets as the offline PoC).

This is the proof that the loop works against a *real* renderer, real
anti-aliasing, and a *real* model — the final validation tier.
