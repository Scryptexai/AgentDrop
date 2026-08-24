# AgentDrop — Vision-First Browser Agents

AgentDrop's browser agents used to read the DOM. That was the bottleneck:
fragile to any UI change, blind to images/CAPTCHAs, and not human-like.

**This repo transforms them into vision-first, computer-using agents:**
they **see the screen** (CDP screenshots), **reason about what they see**
(a vision model), and **act like a human** (mouse/keyboard at absolute
pixel coordinates via CDP) — then **verify every action** with a fresh
screenshot. No CSS selectors anywhere in the interaction path.

```
┌─────────────────────────────────────────────────────────────┐
│                    COMPUTER USE LOOP                        │
│                                                             │
│  1. CAPTURE SCREENSHOT (CDP)                                │
│  2. OBSERVE (vision model analyzes screenshot)              │
│  3. REASON (model decides next action, pixel coordinates)   │
│  4. EXECUTE (CDP: click X,Y, type, scroll)                  │
│  5. VERIFY (screenshot again, confirm state changed)        │
│  6. REPEAT until task complete or error                     │
└─────────────────────────────────────────────────────────────┘
```

## Status: Phase 1 PoC — done and validated

`worker-quests` runs the **Loqua Airdrop** benchmark (5 tasks) as a
vision-first agent. Fully validated in this repo, offline:

```
47 tests passed  ·  5/5 Loqua tasks  ·  ~15 steps (target <50)
100% first-attempt click accuracy (target ≥90%)
absorbs a mid-run UI mutation  ·  rejects premature "done"
halts on CAPTCHA & wallet screens (evidence saved)
```

The real-browser tier (`tests/e2e/`) activates automatically on any
machine that has Chromium + a vision API key.

## Quickstart

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt

# 1. Run the offline Loqua benchmark (the PoC — no network, no browser)
.venv/bin/python -m agentdrop.cli poc

# 2. Run the full test suite
.venv/bin/python -m pytest tests/ --ignore=tests/e2e

# 3. MCP server protocol test
node tests/mcp/server.test.js

# 4. Profile registry health
.venv/bin/python -m agentdrop.cli registry status
```

Live run (target machine with a browser — see `docs/DEPLOYMENT.md`):

```bash
scripts/install-hermes.sh                 # Option A: full install
scripts/start-browser.sh execution        # CDP :9223 persistent profile
.venv/bin/python -m agentdrop.cli run \
  --campaign agentdrop/campaigns/loqua.yaml --profile execution \
  --url https://LIVE_LOQUA_URL --evidence runs/live
```

## Repository map

| Path | What it is |
|------|-----------|
| `agentdrop/` | **The engine.** CDP client + pixel browser session, vision planners (OpenAI-compatible / Anthropic / offline), the computer-use loop, recovery, security, metrics, campaigns, worker entry point. |
| `agentdrop/campaigns/loqua.yaml` | The 5-task Loqua benchmark — natural-language goals, zero selectors. |
| `fakesites/loqua/site.py` | Pixel-rendered Loqua replica (Pillow). Same `BrowserLike` interface as the real CDP browser — this is what makes the offline PoC honest. |
| `hermes-config/` | **Option B: the complete `~/.hermes/` tree** — 1 commander + 7 workers (all vision-first), airdrop-farming skill, memory system, security policy. `install.sh` drops it into `~/.hermes/`. |
| `mcp/server/` | CDP computer-use **MCP server** — 24 tools, zero-dependency Node ≥21, same action vocabulary as the engine. |
| `data/profile_registry.json` | **Profile registry** — single source of truth: profile → path / CDP port / accounts. |
| `scripts/` | `install-hermes.sh`, `start-browser.sh` (registry-driven), `serve-vnc-browser.sh` (manual debugging), etc. |
| `tests/` | Offline unit + integration tests (47) and the real-browser E2E harness. |
| `docs/` | `ARCHITECTURE.md`, `VISION_FIRST.md` (the rules), `VALIDATION.md` (metrics), `DEPLOYMENT.md`. |

## The hard rules (enforced in code)

1. **Never use DOM selectors** for interaction — pixels only.
2. **Observe before acting, verify after acting** — never assume success.
3. **Adapt** — after a no-change, re-read the screen; never reuse stale coordinates.
4. **Stop on CAPTCHA** — report, halt, save evidence; never attempt to solve.
5. **Never interact with wallets** — manual approval gate; even if approved, the agent observes and stops (a human takes over).
6. **Never store private keys** — key-shaped strings are rejected at config load.

See `docs/VISION_FIRST.md` for the full contract.

## Model choice

`gpt-5.6-luna` — **confirmed vision-capable** (image input + computer-use
per OpenAI docs) and the cost-optimized GPT-5.6 — is the default.
Fallbacks: Claude Sonnet/Opus 4 (best grounding), DeepSeek V4 Pro
(cheaper), Qwen-2.5-VL-72B (self-hosted). Any OpenAI-Chat-Completions
endpoint works via `AGENTDROP_VISION_BASE_URL` (HNCSEC-style proxies
included). Details in `docs/VALIDATION.md`.

## Next steps after PoC success

1. ✅ PoC: `worker-quests` vision-first on Loqua (this repo)
2. Port all 7 workers to the same pattern (configs already in `hermes-config/profiles/workers/`)
3. Mission compiler: Telegram → structured tasks (commander skeleton in `hermes-config/profiles/commander/`)
4. Task state machine for multi-day tasks (`hermes-config/memory/task_state.json`)
5. Horizontal scale: multiple agents on multiple machines via the profile registry
