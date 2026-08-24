"""Vision planners — the "eyes + brain" of the computer-use loop.

A planner takes (task, recent history, the screenshot bytes) and
returns a Plan: a validated Action plus a description of what it
perceives (page_state). The loop never inspects the page itself; it
only forwards pixels and records what the planner claims to see.

Implementations
---------------
OpenAICompatiblePlanner  — any OpenAI Chat Completions-compatible API
                           (OpenAI, HNCSEC-style proxies, DeepSeek,
                           local vLLM/Ollama servers). Works with
                           gpt-5.6-luna, which supports image input.
AnthropicPlanner         — Anthropic Messages API (Claude Sonnet/Opus,
                           best-in-class visual grounding).
ScriptedVisionPlanner    — offline test double. It receives the same
                           screenshot bytes and asks a `perceive`
                           oracle (wired to the fake pixel site in
                           tests) for ground truth, then applies simple
                           rules. Simulates a *perfect* vision model
                           without any network access.
"""
from __future__ import annotations

import base64
import json
import os
import re
from dataclasses import dataclass, field
from typing import Callable, List, Optional, Protocol

from . import prompts
from ..loop.actions import Action, ActionError, parse_action


@dataclass
class PageState:
    description: str = ""
    captcha_detected: bool = False
    wallet_prompt_detected: bool = False


@dataclass
class Plan:
    action: Action
    page_state: PageState
    reasoning: str = ""
    confidence: float = 1.0
    raw: dict = field(default_factory=dict)


class PlannerError(Exception):
    pass


class VisionPlanner(Protocol):
    name: str

    def plan(self, task_goal: str, screenshot_b64: str, screen: tuple, history: List[dict],
             extra_hint: str = "") -> Plan: ...

    def verify(self, task_goal: str, done_criteria: str, screenshot_b64: str, screen: tuple) -> tuple:
        """-> (complete: bool, evidence: str)."""
        ...


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def _extract_json(text: str) -> dict:
    """Pull the first JSON object out of a model response (fence-tolerant)."""
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    start = text.find("{")
    if start == -1:
        raise PlannerError(f"no JSON object in model response: {text[:200]!r}")
    depth = 0
    for i in range(start, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                candidate = text[start : i + 1]
                try:
                    return json.loads(candidate)
                except json.JSONDecodeError as e:
                    raise PlannerError(f"model returned malformed JSON: {e}; head={candidate[:200]!r}")
    raise PlannerError(f"unbalanced JSON in model response: {text[:200]!r}")


def _plan_from_data(data: dict, screen: tuple) -> Plan:
    action = parse_action(data.get("action", data), screen[0], screen[1])
    ps = data.get("page_state") or {}
    page_state = PageState(
        description=str(ps.get("description", "")),
        captcha_detected=bool(ps.get("captcha_detected", False)),
        wallet_prompt_detected=bool(ps.get("wallet_prompt_detected", False)),
    )
    return Plan(
        action=action,
        page_state=page_state,
        reasoning=str(data.get("reasoning", "")),
        confidence=float(data.get("confidence", 1.0) or 1.0),
        raw=data,
    )


def _user_message(task_goal: str, screen: tuple, history: List[dict], extra_hint: str = "") -> str:
    w, h = screen
    parts = [
        f"Screen size: {w}x{h} pixels (top-left origin).",
        f"Current task: {task_goal}",
    ]
    if history:
        parts.append("Recent steps (oldest first):")
        for hstep in history[-6:]:
            parts.append(
                f"  step {hstep.get('step')}: {hstep.get('action')} "
                f"-> screen {'CHANGED' if hstep.get('changed') else 'UNCHANGED'}"
                + (f" ({hstep.get('note')})" if hstep.get("note") else "")
            )
    if extra_hint:
        parts.append(extra_hint)
    parts.append("What should I do next? Respond with the JSON object only.")
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# OpenAI-compatible (OpenAI / HNCSEC proxy / DeepSeek / local servers)
# ---------------------------------------------------------------------------
class OpenAICompatiblePlanner:
    def __init__(
        self,
        model: str,
        base_url: Optional[str] = None,
        api_key_env: str = "OPENAI_API_KEY",
        api_key: Optional[str] = None,
        max_tokens: int = 1024,
        temperature: float = 0.0,
        timeout: float = 120.0,
        session=None,
    ):
        import requests

        self.name = f"openai-compat:{model}"
        self.model = model
        self.base_url = (base_url or os.environ.get("AGENTDROP_VISION_BASE_URL", "https://api.openai.com/v1")).rstrip("/")
        self.api_key = api_key or os.environ.get(api_key_env, "")
        if not self.api_key:
            raise PlannerError(f"no API key: set {api_key_env} or pass api_key")
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.timeout = timeout
        self._requests = session or requests

    def _chat(self, system: str, user_text: str, screenshot_b64: str) -> str:
        payload = {
            "model": self.model,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "messages": [
                {"role": "system", "content": system},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": user_text},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{screenshot_b64}",
                                "detail": "high",
                            },
                        },
                    ],
                },
            ],
        }
        resp = self._requests.post(
            f"{self.base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=self.timeout,
        )
        if resp.status_code != 200:
            raise PlannerError(f"vision API {resp.status_code}: {resp.text[:300]}")
        data = resp.json()
        try:
            return data["choices"][0]["message"]["content"]
        except (KeyError, IndexError) as e:
            raise PlannerError(f"unexpected vision API response: {str(data)[:300]}") from e

    def plan(self, task_goal, screenshot_b64, screen, history, extra_hint="") -> Plan:
        out = self._chat(prompts.SYSTEM_PROMPT, _user_message(task_goal, screen, history, extra_hint), screenshot_b64)
        return _plan_from_data(_extract_json(out), screen)

    def verify(self, task_goal, done_criteria, screenshot_b64, screen) -> tuple:
        sys = prompts.VERIFIER_PROMPT.format(task=task_goal, criteria=done_criteria)
        out = self._chat(sys, "Is the task complete? JSON only.", screenshot_b64)
        data = _extract_json(out)
        return bool(data.get("complete", False)), str(data.get("evidence", ""))


# ---------------------------------------------------------------------------
# Anthropic
# ---------------------------------------------------------------------------
class AnthropicPlanner:
    def __init__(
        self,
        model: str = "claude-sonnet-4-20250514",
        api_key_env: str = "ANTHROPIC_API_KEY",
        api_key: Optional[str] = None,
        max_tokens: int = 1024,
        timeout: float = 120.0,
        session=None,
    ):
        import requests

        self.name = f"anthropic:{model}"
        self.model = model
        self.api_key = api_key or os.environ.get(api_key_env, "")
        if not self.api_key:
            raise PlannerError(f"no API key: set {api_key_env}")
        self.max_tokens = max_tokens
        self.timeout = timeout
        self._requests = session or requests

    def _chat(self, system: str, user_text: str, screenshot_b64: str) -> str:
        resp = self._requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": self.model,
                "max_tokens": self.max_tokens,
                "system": system,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": user_text},
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": "image/png",
                                    "data": screenshot_b64,
                                },
                            },
                        ],
                    }
                ],
            },
            timeout=self.timeout,
        )
        if resp.status_code != 200:
            raise PlannerError(f"anthropic API {resp.status_code}: {resp.text[:300]}")
        data = resp.json()
        blocks = data.get("content", [])
        text = "".join(b.get("text", "") for b in blocks if b.get("type") == "text")
        if not text:
            raise PlannerError(f"empty anthropic response: {str(data)[:300]}")
        return text

    def plan(self, task_goal, screenshot_b64, screen, history, extra_hint="") -> Plan:
        out = self._chat(prompts.SYSTEM_PROMPT, _user_message(task_goal, screen, history, extra_hint), screenshot_b64)
        return _plan_from_data(_extract_json(out), screen)

    def verify(self, task_goal, done_criteria, screenshot_b64, screen) -> tuple:
        sys = prompts.VERIFIER_PROMPT.format(task=task_goal, criteria=done_criteria)
        out = self._chat(sys, "Is the task complete? JSON only.", screenshot_b64)
        data = _extract_json(out)
        return bool(data.get("complete", False)), str(data.get("evidence", ""))


# ---------------------------------------------------------------------------
# Offline test double
# ---------------------------------------------------------------------------
class ScriptedVisionPlanner:
    """Offline stand-in for a vision model.

    It receives exactly what a real model would receive — screenshot
    bytes — and asks a `perceive(screenshot_b64) -> dict` oracle for
    ground truth about that exact render (in tests the oracle is wired
    to the fake pixel site). It then picks actions with simple rules,
    including *re-reading* the screen after every change, which is what
    lets it absorb UI mutations mid-run.
    """

    def __init__(self, perceive: Callable[[str], dict]):
        self._perceive = perceive
        self.name = "scripted-vision-test-double"
        self.observations: List[dict] = []

    def _see(self, screenshot_b64: str) -> dict:
        truth = self._perceive(screenshot_b64)
        self.observations.append(truth)
        return truth

    def plan(self, task_goal, screenshot_b64, screen, history, extra_hint="") -> Plan:
        w, h = screen
        truth = self._see(screenshot_b64)
        elements: dict = truth.get("elements", {})
        screen_name = truth.get("screen", "")
        desc = truth.get("description", "")
        ps = PageState(
            description=desc,
            captcha_detected=truth.get("captcha", False),
            wallet_prompt_detected=truth.get("wallet", False),
        )
        if truth.get("captcha"):
            return Plan(Action(type="error", value="CAPTCHA detected — stopping per security policy"), ps,
                        "A CAPTCHA challenge is visible; policy says do not attempt it.")
        if truth.get("wallet"):
            return Plan(Action(type="error", value="Wallet prompt detected — stopping per security policy"), ps,
                        "A wallet/transaction prompt is visible; policy says do not interact.")

        def center(el_id: str):
            el = elements.get(el_id)
            if not el:
                raise PlannerError(f"planner cannot find element {el_id!r} on screen {screen_name!r}")
            x = (el["x"] + el["x2"]) // 2
            y = (el["y"] + el["y2"]) // 2
            return x, y

        last_action = history[-1].get("action", "") if history else ""
        last_unchanged = bool(history) and not history[-1].get("changed")

        # ---- task policy: what does THIS task's goal ask for?
        goal = task_goal.lower()
        if "claim" in goal:
            policy = "claim"
        elif "register" in goal or "email" in goal:
            policy = "register"
        elif "display name" in goal or "profile" in goal:
            policy = "profile"
        elif "quest" in goal or "discord" in goal or "follow" in goal:
            policy = "quest"
        else:
            policy = "enter"

        def completed(policy_: str) -> bool:
            if policy_ == "enter":
                return screen_name != "landing"
            if policy_ == "register":
                return bool(truth.get("registered"))
            if policy_ == "profile":
                return bool(truth.get("x_connected"))
            if policy_ == "quest":
                return bool(truth.get("followed")) and bool(truth.get("discord_joined"))
            return bool(truth.get("claimed"))

        # If this task is already satisfied (we are past its stage), stop.
        # A real vision model recognises "the goal state is already on
        # screen" from the screenshot alone.
        if completed(policy):
            return Plan(Action(type="done"), ps, "Task goal state is already satisfied on screen.")

        # ---- per-screen work (prerequisites are completed in order,
        #     which is also what a real agent does when it arrives early)
        if screen_name == "landing":
            x, y = center("get_started")
            return Plan(Action(type="click", x=x, y=y), ps,
                        "Landing page with a 'Get Started' button; click it to enter the flow.")
        if screen_name == "register":
            if not truth.get("email_filled", False):
                x, y = center("email_input")
                return Plan(Action(type="type", x=x, y=y, value="agent@drop.test"), ps,
                            "Registration form visible; type the email into the email field.")
            x, y = center("submit_button")
            return Plan(Action(type="click", x=x, y=y), ps,
                        "Email already entered; submit the form.")
        if screen_name == "profile":
            if not truth.get("name_filled", False):
                x, y = center("name_input")
                return Plan(Action(type="type", x=x, y=y, value="AgentDrop"), ps,
                            "Profile form visible; type the display name into the name field.")
            if not truth.get("x_connected", False):
                x, y = center("connect_x")
                return Plan(Action(type="click", x=x, y=y), ps, "Connect the X (Twitter) account.")
        if screen_name == "quest":
            if not truth.get("followed", False):
                x, y = center("follow_button")
                return Plan(Action(type="click", x=x, y=y), ps, "Follow quest not done; click 'Follow @loqua'.")
            if not truth.get("discord_joined", False):
                if "discord_button" in elements:
                    x, y = center("discord_button")
                    return Plan(Action(type="click", x=x, y=y), ps, "Discord button visible; click it.")
                # Below the fold: a human scrolls to bring it into view.
                if last_action.startswith("scroll") and last_unchanged:
                    return Plan(Action(type="error", value="scrolled but Discord button never appeared"), ps,
                                "Discord button still not visible after scrolling.")
                return Plan(Action(type="scroll", direction="down", amount=3, x=w // 2, y=h // 2), ps,
                            "Discord button not visible; scroll down to bring it into view.")
            # Both quests complete.
            if policy == "claim":
                if "claim_link" in elements:
                    x, y = center("claim_link")
                    return Plan(Action(type="click", x=x, y=y), ps,
                                "Both quests done; the claim link is now visible, click it.")
                # claim link is below the fold — scroll to find it
                return Plan(Action(type="scroll", direction="down", amount=3, x=w // 2, y=h // 2), ps,
                            "Both quests done but the claim link is not visible; scroll down.")
        if screen_name == "claim":
            if not truth.get("claimed", False):
                x, y = center("claim_button")
                return Plan(Action(type="click", x=x, y=y), ps, "Claim button visible; click it.")
        raise PlannerError(f"scripted planner: no progress possible on screen {screen_name!r}")

    def verify(self, task_goal, done_criteria, screenshot_b64, screen) -> tuple:
        """Per-task completion check (the loop rejects premature 'done')."""
        t = self._see(screenshot_b64)
        g = task_goal.lower()
        if "claim" in g:
            complete = bool(t.get("claimed"))
        elif "register" in g or "email" in g:
            complete = bool(t.get("registered"))
        elif "display name" in g or "profile" in g or "connect your x" in g:
            complete = bool(t.get("x_connected"))
        elif "quest" in g or "discord" in g or "follow" in g:
            complete = bool(t.get("followed")) and bool(t.get("discord_joined"))
        else:  # landing / enter the flow
            complete = t.get("screen", "landing") != "landing"
        return complete, t.get("description", "no description")
