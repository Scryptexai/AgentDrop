# Interactive Vision Demo — a human IS the vision model

This directory contains a real end-to-end run of the AgentDrop
computer-use flow where **a human (not a script) played the vision
model**. The driver (`vision_demo.py`) gives the operator *exactly* what
a real vision planner receives — and nothing more:

- a numbered PNG screenshot (the only view of the page)
- URL + title (metadata, like a human glancing at the URL bar)
- the previous action + CHANGED/UNCHANGED verdict (real pixel diff)

It is given **no ground truth**: no element positions, no screen names,
no hints. Every coordinate below was chosen by *looking at the pixels*
in `evidence/NNN.png`.

## Replay the run

```bash
cd poc/interactive
rm -f .state.json && rm -rf evidence
PYTHON=/home/user/AgentDrop/.venv/bin/python
$PYTHON vision_demo.py init
$PYTHON vision_demo.py shot                # view evidence/001.png, decide action...
$PYTHON vision_demo.py click 640 432       # ...execute, verify
# ...repeat per the transcript below
```

## Transcript — Loqua Airdrop, start to claim

| # | Screenshot seen | What I saw | Action | Verdict |
|---|----------------|-----------|--------|---------|
| 1 | 001.png | Landing: "Claim your share of the $LOQUA points airdrop", blue **Get Started** button centred ~(510–770, 400–465) | `click(640, 432)` | CHANGED → `/register` |
| 2 | 003.png | Register form: empty email field ~(90–710, 260–325), **Continue** below | `type(400, 292, "agent@drop.test")` | CHANGED |
| 3 | 005.png | Email field now shows `agent@drop.test` (verified, not assumed) | `click(220, 552)` on Continue | CHANGED → `/profile` |
| 4 | 007.png | Profile: empty **Display name** field, **Connect X (Twitter)** button, "Not connected" | `type(400, 272, "AgentDrop")` | CHANGED |
| 5 | 009.png | Name field shows "AgentDrop" (verified) | `click(250, 432)` on Connect X | CHANGED → `/quest` |
| 6 | 011.png | Quest board: **Follow @loqua on X** ~(90–430, 260–324), "0 / 2 quests"; second quest not visible | `click(260, 292)` | CHANGED |
| 7 | 013.png | "Following @loqua ✓ / ✓ done" — but board still says *both* quests; the other is below the fold | `scroll(down ×3)` | CHANGED |
| 8 | 015.png | Second quest revealed: **Join official Discord** ~(90–430, 490–554), "not joined", "— end of quest board —" | `click(260, 522)` | CHANGED |
| 9 | 017.png | "In Discord ✓ / ✓ done" + new button **Both quests done — Go claim →** ~(90–510, 630–694) | `click(300, 662)` | CHANGED → `/claim` |
| 10 | 019.png | Claim page: "Eligible: 500 LOQUA points", green **Claim Points** button; status "Awaiting claim". Security check: points claim, not a wallet/tx screen | `click(640, 352)` | CHANGED |
| 11 | 021.png | **"✓ 500 LOQUA points credited to your account"** — success visually confirmed | `done` | task complete |

## Result

- **10 actions, all on the first attempt — 100% click accuracy**
- Every action verified with a real pixel diff (CHANGED), and every
  "did it work?" question answered by *looking*, never by assuming
- The below-the-fold quest required a **scroll**, exactly like a human
- No DOM, no selectors, no ground truth — screenshots in, pixels out

This is the same interface (`BrowserLike`) and the same verification
code (`agentdrop.vision.verify`) the CDP worker uses in production; only
the renderer and the model differ (see `docs/ARCHITECTURE.md`).
