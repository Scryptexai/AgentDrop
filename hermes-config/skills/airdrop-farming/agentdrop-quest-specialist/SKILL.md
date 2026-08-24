# Skill: agentdrop-quest-specialist (vision-first)

**Domain:** airdrop-farming
**Workers:** worker-quests (PoC) → all 7 workers (port pattern)
**Mode:** vision-first computer use. This skill NEVER uses DOM selectors,
XPath, or HTML structure. The agent screenshots, a vision model reasons
over the pixels, and the agent acts with mouse/keyboard at absolute
pixel coordinates.

## When to use

Run this skill when a mission requires a worker to complete a
multi-step web flow (register → profile → quests → claim) on an
airdrop/campaign site.

## Contract

Input (from the commander's mission compiler):

```yaml
campaign: loqua            # campaign id -> agentdrop/campaigns/<id>.yaml
profile: execution         # profile registry name (data/profile_registry.json)
live_url: https://...      # optional base URL for {LIVE_URL} substitution
```

Output: a structured run report

```yaml
status: completed | incomplete | halted
tasks: [{id, completed, steps, recoveries, error}]
click_accuracy: 0.95
total_steps: 15
evidence_dir: runs/<ts>    # screenshots + steps.jsonl + report.json
```

## Execution

```bash
# from the repo root (AGENTDROP_WORKER_CONFIG points at the Hermes
# profile yaml so one file configures both Hermes and the engine)
python3 -m agentdrop.worker.quest_worker \
  --campaign agentdrop/campaigns/loqua.yaml \
  --profile execution \
  --url https://live-campaign.example \
  --evidence runs/$(date +%Y%m%d-%H%M%S)
```

The engine loop for every task step:

1. **CAPTURE** — `Page.captureScreenshot` (CDP)
2. **OBSERVE/REASON** — vision model sees the screenshot + task goal +
   step history, returns one action as strict JSON (pixel coordinates)
3. **SECURITY** — CAPTCHA → halt; wallet/tx screen → manual approval gate
4. **EXECUTE** — CDP `Input.dispatchMouseEvent` / `Input.dispatchKeyEvent`
5. **VERIFY** — new screenshot, pixel diff; no change → retry the exact
   action once, then re-observe & adapt (recovery budget 3)
6. **REPEAT** — until the verifier confirms the done-criteria or the
   budget is exhausted

## Hard rules (enforced in code, not just prose)

- NO DOM selectors for interaction — vision only (`fallback_to_dom: false`)
- Verify after EVERY visual action; never assume success
- Stop on CAPTCHA (do not attempt to solve); save evidence screenshot
- Never interact with wallet/tx screens without explicit human approval
- Never store private keys / seed phrases (config + log guard rejects them)
- Campaign step budget: 50 (fail loudly when exhausted)

## Model requirements

The vision model must support image input and reliable coordinate
output. Confirmed: `gpt-5.6-luna` (vision + computer-use per OpenAI
docs). Alternatives: Claude Sonnet/Opus (best grounding), DeepSeek V4
Pro (cheaper), Qwen-2.5-VL-72B (self-hosted).
