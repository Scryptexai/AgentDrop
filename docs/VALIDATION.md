# Validation

How we prove the vision-first fix actually works — the six metrics from
the problem statement, each with its target and measurement.

## The benchmark: Loqua Airdrop (5 tasks)

`agentdrop/campaigns/loqua.yaml` defines five natural-language tasks:
open the flow → register → profile → quests (follow + Discord) → claim.
It is run two ways:

1. **Offline PoC** (CI, this sandbox): the engine + loop run unchanged
   against `fakesites/loqua/site.py`, a Pillow-rendered replica of the
   same 5-step flow. Screenshots are real PNGs, clicks are real pixel
   hit-tests; only the vision model's perception is simulated (a
   ground-truth oracle). This validates the *loop, verification,
   recovery, security, and metrics* deterministically.

2. **Real-browser E2E** (target machine): the same campaign + loop run
   against a real Chromium (CDP) and a real vision model. See
   `tests/e2e/README.md`. This validates *real rendering + a real model*.

## Metrics, targets, and how they're measured

| Metric | Target | Measured by |
|--------|--------|-------------|
| **Click accuracy** | ≥ 90% | First-attempt clicks that produced a verified pixel change / all first-attempt clicks. `Metrics.click_accuracy`. |
| **Task completion (Loqua)** | 100% (5/5) | `Metrics.task_completion` over the campaign. |
| **Recovery from UI change** | Pass | `test_ui_change_mid_run_is_absorbed` (button moves mid-run) and `test_stale_coordinate_recovers_via_reobserve` (stale click → miss → re-observe → hit). Both must finish 5/5 / complete. |
| **Screen understanding** | Pass | `test_screen_understanding`: the agent's `page_state.description` across the run must contain the key texts of each screen (Get Started, email, Display name, Quest board, Claim). |
| **Step count** | < 50 | `Metrics.total_steps` for the whole campaign vs `TARGETS.max_steps`. |
| **Verification honesty** | Pass | `test_premature_done_rejected_by_verifier` (agent claims done early → verifier rejects → agent corrects) and `test_stuck_when_recovery_budget_exhausted` (can't complete → fails loudly, no infinite loop). |
| **Security** | Pass | CAPTCHA halts + saves evidence; wallet halts without approval; even *with* approval the agent never clicks a wallet control; key-shaped strings rejected at config load. |

## Run the validation

```bash
# Offline (no network, no browser): full unit + integration suite
./.venv/bin/python -m pytest tests/ --ignore=tests/e2e -v

# Real browser + real model (target machine)
export AGENTDROP_VISION_MODEL=gpt-5.6-luna
export OPENAI_API_KEY=...
pytest tests/e2e -v

# MCP server protocol
node tests/mcp/server.test.js
```

## Current result (offline PoC, this repo)

```
47 passed, 1 skipped (e2e — needs a real browser + API key)
```

The Loqua benchmark completes **5/5 tasks**, in **~15 steps** (target
<50), with **100% first-attempt click accuracy** (target ≥90%), absorbs a
mid-run UI mutation, rejects a premature "done", and halts on injected
CAPTCHA / wallet screens with evidence saved.

## Model capability check (problem statement, step 1)

The plan asked to confirm `gpt-5.6-luna` has vision. **Confirmed:** per
OpenAI's model documentation, `gpt-5.6-luna` supports **image input
(vision)** and **computer-use** tools, and is the cost-optimized member
of the GPT-5.6 family. It is a valid primary model. Fallbacks (best
grounding → cheapest → self-hosted):

| Model | Why |
|-------|-----|
| Claude Sonnet 4 / Opus 4 | Best-in-class visual grounding; use for hard sites. |
| `gpt-5.6-luna` (default) | Confirmed vision + computer-use; cheap, fast. |
| DeepSeek V4 Pro (vision) | Cheaper alternative with vision. |
| Qwen-2.5-VL-72B (vLLM) | Self-hostable; keeps page content on-host. |

Any provider speaking the OpenAI Chat Completions protocol with image
content works via `AGENTDROP_VISION_BASE_URL` (so an HNCSEC-style proxy
for `cx/gpt-5.6-luna` keeps working if it forwards image blocks).
