# Architecture: Vision-First Computer-Use Browser Agent

## The core loop

```
┌────────────────────────────────────────────────────────────────┐
│                       COMPUTER-USE LOOP                        │
│                                                                │
│  1. CAPTURE      Page.captureScreenshot (CDP)  ──► PNG bytes   │
│         │                                                              │
│  2. OBSERVE      vision model sees the screenshot (+ task goal,   │
│         │                  step history)                            │
│  3. REASON       model returns ONE action as strict JSON         │
│         │                  (pixel coordinates, never selectors)    │
│  4. SECURITY     CAPTCHA -> halt · wallet -> human approval gate  │
│         │                                                              │
│  5. EXECUTE      CDP Input.dispatchMouseEvent / dispatchKeyEvent   │
│         │                  (mouse moves before click, real keys)    │
│  6. VERIFY       new screenshot, pixel diff vs pre-action shot     │
│         │        no change -> retry x1 -> re-observe & adapt       │
│  7. REPEAT       until verifier confirms done-criteria or budget   │
│                                                                │
└────────────────────────────────────────────────────────────────┘
```

The agent uses **pixel coordinates, not CSS selectors** — the way a human
interacts with a UI. When the site changes, there is nothing cached to
break: the agent simply looks again.

## Components

```
agentdrop/                     the engine (Python)
├── cdp/client.py              raw CDP JSON-RPC over WebSocket (events + commands)
├── cdp/browser.py             BrowserSession: screenshot / mouse / keyboard / nav
│                              (the ONLY interaction surface; no selectors)
├── registry/registry.py       ProfileRegistry — single source of truth for
│                              profile path + CDP port + liveness
├── vision/planner.py          VisionPlanner: OpenAI-compatible, Anthropic,
│                              ScriptedVisionPlanner (offline test double)
├── vision/prompts.py          vision-first system prompt (the hard rules)
├── vision/verify.py           "did the screen change?" (mean + local pixel diff,
│                              perceptual dHash)
├── loop/actions.py            the 15-action vocabulary (pixel/keys), validation
├── loop/computer_use.py       ComputerUseLoop — the 7-step loop above
├── loop/recovery.py           episode -> re-observe -> stuck (bounded)
├── loop/security.py           CAPTCHA halt, wallet gate, key guard
├── loop/metrics.py            step log + validation metrics
├── campaigns/base.py          Campaign/TaskSpec — natural-language goals
├── campaigns/loqua.yaml       the 5-task benchmark
├── config.py                  parses the worker YAML (shared with Hermes)
└── worker/quest_worker.py     worker-quests entry point

fakesites/loqua/site.py        pixel-rendered Loqua replica (offline PoC env)
hermes-config/                 the ~/.hermes tree (Option B)
mcp/server/server.js           CDP computer-use MCP server (24 tools, Node, 0 deps)
tests/                         offline unit+integration tests, real-browser E2E
```

## Data flow

```
worker config YAML ──► EngineConfig ──► ProfileRegistry ──► BrowserSession (CDP)
                 │                                        │
                 └──► SecurityGate                         │
                   (CAPTCHA/wallet/keys)                   ▼
                                              ComputerUseLoop.run_task
                                                   │  ▲
              ┌────────────────────────────────────┘  │ verify (pixel diff)
              ▼                                       │
        VisionPlanner.plan(goal, screenshot_b64,      │
                           screen, history) ──► Action
              │  ▲                                    │
              └──── SecurityGate.check_plan ─────────┘
```

## Key design decisions

**1. One interaction surface.** All browser contact goes through
`BrowserSession` (or the fake site's identical interface). Nothing else
imports CDP. This makes "no selectors" enforceable, not just aspirational.

**2. Metadata is allowed; interaction is not.** Reading `location.href` /
`document.title` for context is fine (a human glances at the URL bar too).
Clicking/typing/scrolling is pixels-only.

**3. Verification is the honesty mechanism.** A click that misses, a form
that rejects input, a spinner that never resolves — all show up as
"no change" and trigger recovery instead of being assumed as success.
Completion is confirmed by a separate verifier call, not by the agent's
self-report.

**4. Recovery is bounded and escalating.** One inline retry (slip / not
ready), then re-observe-and-adapt (the level that absorbs real UI change),
then fail loudly with evidence. No infinite loops.

**5. One config drives everything.** The worker YAML block
(`computer_use`, `security`, `browser`) is parsed by both Hermes and the
Python engine (`config.EngineConfig`). No second source of truth.

**6. The MCP server mirrors the engine.** `mcp/server/server.js` exposes
the same 24-tool computer-use vocabulary over CDP, so a Hermes MCP session
and the worker engine behave identically.

## Why not desktop computer-use (OS-level mouse/keyboard)?

The plan referenced `@opencode/computer-use`; no such npm package exists,
and the closest real package (`open-computer-use`) drives the **OS**
mouse/keyboard — which cannot reach a headless browser. Browser agents
need CDP. So we ship a CDP-based MCP server with the same tool names.
