# Hermes configuration — vision-first AgentDrop (Option B: config-only build)

This directory **is** the `~/.hermes/` tree for the vision-first AgentDrop
deployment: 1 commander + 7 workers, the airdrop-farming skill, the memory
system, and the security policy. It is designed to be copied onto the target
machine as-is:

```bash
./install.sh            # copies everything into ~/.hermes/ (merge-safe)
```

## Layout

```
hermes-config/
├── install.sh                     # copies this tree into ~/.hermes/
├── hermes.yaml                    # global: MCP servers, model registry
├── profiles/
│   ├── commander/config.yaml      # mission intake + worker dispatch
│   └── workers/
│       ├── worker-quests/config.yaml   ← THE vision-first profile (PoC)
│       ├── worker-claim/config.yaml    # same pattern (port 1:1)
│       ├── worker-connect/config.yaml
│       ├── worker-follow/config.yaml
│       ├── worker-points/config.yaml
│       ├── worker-monitor/config.yaml
│       └── worker-recovery/config.yaml
├── skills/
│   └── airdrop-farming/
│       └── agentdrop-quest-specialist/
│           ├── SKILL.md           # skill contract for Hermes
│           ├── skill.yaml         # machine-readable skill config
│           └── run_quest.py       # invokes the agentdrop engine
├── memory/
│   ├── README.md                  # memory system design
│   ├── task_state.json            # multi-day task state machine
│   └── site_memory/loqua.json     # learned VISUAL anchors (not selectors)
└── security/
    └── policy.yaml                # CAPTCHA halt, wallet gate, key guard
```

## The one rule every profile shares

Every worker profile contains the same `computer_use` block:

```yaml
computer_use:
  enabled: true
  vision_first: true      # NEVER use DOM selectors
  fallback_to_dom: false  # force vision-only
  verify_each_step: true
  max_retries_on_error: 3
  screenshot_before_each_action: true
```

And the same hard security block:

```yaml
security:
  never_store_private_keys: true
  stop_on_captcha: true
  require_manual_approval_for_wallet: true
```

`worker-quests/config.yaml` is the fully wired PoC profile; the other six
are the same pattern ready to activate as each campaign is ported (see
"Next steps" in the root README).

## How the config reaches the engine

`agentdrop/config.EngineConfig.from_worker_yaml()` parses exactly these
blocks, so **one YAML file drives both Hermes and the Python
computer-use engine** — no second source of truth, no drift.
