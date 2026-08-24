# Vision-First: the rules

This document codifies the non-negotiable rules of the AgentDrop
computer-use loop. They are enforced in code (`loop/security.py`,
`loop/computer_use.py`, `vision/prompts.py`), not just documented.

## Why

DOM-based agents break the moment a site changes a class name. They
cannot read CAPTCHAs, see images, or interpret a reflowed layout. A
vision-first agent sees what a human sees — pixels — and adapts.

## The rules

| # | Rule | Enforced by |
|---|------|-------------|
| 1 | **Observe before acting.** Every step starts with a fresh screenshot. | `ComputerUseLoop.run_task` |
| 2 | **Pixel coordinates only.** No CSS selectors, no XPath, no DOM for interaction. | `BrowserLike` interface has no selector method; `fallback_to_dom: false` |
| 3 | **Verify after every action.** Screenshot + pixel diff; no change = not done. | `vision/verify.py` |
| 4 | **Never assume success.** Completion needs a verifier call, not a self-report. | `verify_completion` |
| 5 | **Adapt, don't reuse.** After a no-change, re-read the screen; never repeat stale coordinates blindly. | `loop/recovery.py` + `RECOVERY_HINT` |
| 6 | **Stop on CAPTCHA.** Report `captcha_detected`, halt, save evidence. Never attempt to solve. | `SecurityGate` → `SecurityHalt(captcha)` |
| 7 | **Never interact with wallets.** Wallet/tx/seed-phrase screens → manual approval gate; even if approved, the agent observes and stops — a human takes over. | `SecurityGate` → `SecurityHalt(wallet)` |
| 8 | **Never store private keys.** Config/campaign/log guard rejects key-shaped strings at load time. | `loop/security.scan_for_keys` |
| 9 | **Bounded budgets.** Max steps per campaign (50), per task, and for recovery. Fail loudly when exhausted. | `LoopConfig` |

## Allowed vs. forbidden

**Allowed** (metadata / context — a human glances at these too):
- `location.href`, `document.title` (read-only, for grounding)
- Page load state / settle delays
- Screenshot capture and pixel diffing

**Forbidden** (interaction must be visual):
- `document.querySelector`, `getElementsByClassName`, XPath
- Clicking/typing *via* a DOM node
- Reusing cached coordinates after a no-change
- Attempting to solve CAPTCHAs
- Clicking wallet/tx controls (even with approval — observe & stop)

## What "vision-first" does NOT mean

- It does **not** forbid reading the URL bar for context.
- It does **not** mean the agent is blind to structure — it means the
  *interaction layer* is pixels. The model still *understands* layout
  visually (that is the point).
- It does **not** remove verification — if anything it makes verification
  central, because "did the pixels change?" replaces "did the DOM node
  update?".
