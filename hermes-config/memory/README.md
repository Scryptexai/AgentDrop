# AgentDrop memory system

Three memory layers, all plain JSON under `~/.hermes/memory/`, all
readable by humans. Nothing here may contain credentials.

## 1. Task state (`task_state.json`) — the multi-day state machine

Campaigns span days (daily quests, claim windows, cooldowns). The
commander owns this file; workers update `in_progress`/`done` for the
tasks they execute.

```json
{
  "campaign": "loqua",
  "updated": "2026-08-24T09:00:00Z",
  "tasks": {
    "t1_open":    {"state": "done",   "done_at": "...", "worker": "worker-quests"},
    "t2_register":{"state": "done",   "done_at": "...", "worker": "worker-quests"},
    "t3_profile": {"state": "done",   "done_at": "...", "worker": "worker-quests"},
    "t4_quest":   {"state": "in_progress", "worker": "worker-quests"},
    "t5_claim":   {"state": "blocked", "reason": "claim window opens 2026-08-25T00:00Z"}
  }
}
```

States: `pending → scheduled → in_progress → {waiting_manual | blocked | done | failed}`
`waiting_manual` is set when the wallet gate needs a human; `blocked`
when a CAPTCHA halt or schedule constraint stops progress.

## 2. Site memory (`site_memory/<campaign>.json`) — learned VISUAL anchors

The ONLY "memory of the page" AgentDrop keeps. These are **descriptions
a vision model can re-match on a fresh screenshot** — never selectors,
never coordinates from a stale layout. When a site changes, the anchors
guide re-identification; the agent still finds everything by looking.

```json
{
  "site": "loqua",
  "learned": "2026-08-24",
  "anchors": {
    "get_started": "blue 'Get Started' button, centred below the airdrop headline",
    "email_field": "single email input under an 'Email address' label on the registration form",
    "discord_quest": "'Join official Discord' button, second quest card, near the bottom of the quest board (scroll required)",
    "claim_button": "green 'Claim Points' button on the claim page"
  },
  "known_variants": {
    "get_started": ["Get Started", "Enter", "Start"]
  }
}
```

## 3. Run evidence (`runs/<ts>/`) — the audit trail

Every step: before/after screenshots, action JSON, model reasoning,
page description, change verdict. `steps.jsonl` + `report.json` are the
machine-readable summary; screenshots are the proof.

Retention: keep 30 days by default; evidence for any `halted` run is
kept until the halt is resolved (it is the incident report).
