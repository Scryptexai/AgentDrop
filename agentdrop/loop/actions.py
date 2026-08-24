"""The action vocabulary of the computer-use loop.

The vision model emits ONE of these per step as strict JSON. All
interaction is expressed in absolute pixel coordinates (or keys) —
never selectors.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from typing import Optional, Tuple

ACTION_TYPES = (
    "click",
    "double_click",
    "right_click",
    "drag",
    "scroll",
    "type",
    "hotkey",
    "press",
    "wait",
    "navigate",
    "back",
    "forward",
    "reload",
    "done",
    "error",
)

# Actions that must produce a visible screen change to count as progress.
VISUAL_ACTIONS = {
    "click", "double_click", "right_click", "drag", "scroll",
    "navigate", "back", "forward", "reload",
}
# Actions where a change is expected but not guaranteed (typing may be
# hidden behind a closed panel, etc.) — still verified, softer handling.
SOFT_VISUAL_ACTIONS = {"type", "hotkey", "press"}
NON_VISUAL_ACTIONS = {"wait", "done", "error"}

# How many pixels of slop are acceptable when a click is "aimed" at a
# point the planner already targeted (used by metrics, not for gating).
DEFAULT_TIMEOUT_STEPS = 50


class ActionError(ValueError):
    pass


@dataclass
class Action:
    type: str
    x: Optional[int] = None
    y: Optional[int] = None
    x2: Optional[int] = None
    y2: Optional[int] = None
    value: Optional[str] = None
    key: Optional[str] = None
    keys: list = field(default_factory=list)
    direction: Optional[str] = None  # "up" | "down" | "left" | "right"
    amount: int = 1
    seconds: float = 1.0
    url: Optional[str] = None

    @property
    def point(self) -> Optional[Tuple[int, int]]:
        return (self.x, self.y) if self.x is not None and self.y is not None else None

    @property
    def is_visual(self) -> bool:
        return self.type in VISUAL_ACTIONS

    @property
    def is_soft_visual(self) -> bool:
        return self.type in SOFT_VISUAL_ACTIONS

    @property
    def needs_change(self) -> bool:
        return self.is_visual

    def summary(self) -> str:
        t = self.type
        if t in ("click", "double_click", "right_click") and self.point:
            return f"{t} @ {self.x},{self.y}"
        if t == "drag" and self.x is not None:
            return f"drag {self.x},{self.y} -> {self.x2},{self.y2}"
        if t == "scroll":
            return f"scroll {self.direction or 'down'} x{self.amount}"
        if t == "type" and self.value is not None:
            shown = self.value if len(self.value) <= 24 else self.value[:21] + "..."
            return f"type {shown!r}"
        if t == "hotkey" and self.keys:
            return "hotkey " + "+".join(self.keys)
        if t == "press" and self.key:
            return f"press {self.key}"
        if t == "wait":
            return f"wait {self.seconds}s"
        if t == "navigate" and self.url:
            return f"navigate {self.url}"
        if t == "done":
            return "done"
        if t == "error":
            return f"error: {self.value or 'unspecified'}"
        return t

    def to_dict(self) -> dict:
        d = asdict(self)
        return {k: v for k, v in d.items() if v not in (None, [], "")}


def _int(value, name, screen_max: int, screen_label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ActionError(f"{name} must be a number, got {value!r}")
    v = int(round(float(value)))
    if not (0 <= v <= screen_max):
        raise ActionError(
            f"{name}={v} outside screen bounds 0..{screen_max} ({screen_label})"
        )
    return v


def parse_action(data, screen_w: int, screen_h: int) -> Action:
    """Validate the model's action JSON against the screen bounds.

    Raises ActionError with a human-readable reason on any violation —
    the loop feeds that reason back to the model for a corrected step.
    """
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except json.JSONDecodeError as e:
            raise ActionError(f"action is not valid JSON: {e}") from e
    if not isinstance(data, dict):
        raise ActionError(f"action must be an object, got {type(data).__name__}")
    t = data.get("type") or data.get("action_type")
    if t not in ACTION_TYPES:
        raise ActionError(f"unknown action type {t!r}; expected one of {list(ACTION_TYPES)}")

    a = Action(type=t)
    sw, sh = screen_w, screen_h

    if data.get("x") is not None:
        a.x = _int(data["x"], "x", sw, f"screen {sw}x{sh}")
    if data.get("y") is not None:
        a.y = _int(data["y"], "y", sh, f"screen {sw}x{sh}")
    if data.get("x2") is not None:
        a.x2 = _int(data["x2"], "x2", sw, f"screen {sw}x{sh}")
    if data.get("y2") is not None:
        a.y2 = _int(data["y2"], "y2", sh, f"screen {sw}x{sh}")
    if "value" in data and data["value"] is not None:
        a.value = str(data["value"])
    if "key" in data and data["key"]:
        a.key = str(data["key"])
    if "keys" in data and data["keys"]:
        if isinstance(data["keys"], str):
            a.keys = [k.strip() for k in data["keys"].split("+") if k.strip()]
        elif isinstance(data["keys"], list):
            a.keys = [str(k) for k in data["keys"]]
        else:
            raise ActionError("keys must be a string or list")
    if "direction" in data and data["direction"]:
        if data["direction"] not in ("up", "down", "left", "right"):
            raise ActionError(f"direction must be up/down/left/right, got {data['direction']!r}")
        a.direction = data["direction"]
    if "amount" in data and data["amount"] is not None:
        a.amount = max(1, int(data["amount"]))
    if "seconds" in data and data["seconds"] is not None:
        a.seconds = min(30.0, max(0.0, float(data["seconds"])))
    if "url" in data and data["url"]:
        a.url = str(data["url"])

    # per-type required fields
    if t in ("click", "double_click", "right_click", "type"):
        if a.x is None or a.y is None:
            raise ActionError(f"{t} requires x and y pixel coordinates")
    if t == "drag":
        if a.x is None or a.y is None or a.x2 is None or a.y2 is None:
            raise ActionError("drag requires x, y, x2, y2")
    if t == "type" and a.value is None:
        raise ActionError("type requires value (the text to type)")
    if t == "press" and a.key is None:
        raise ActionError("press requires key")
    if t == "hotkey":
        if not a.keys or len(a.keys) < 2:
            raise ActionError("hotkey requires keys with a modifier + key, e.g. ['ctrl','c']")
    if t == "scroll":
        if a.direction is None:
            a.direction = "down"
        if a.x is None or a.y is None:
            a.x, a.y = sw // 2, sh // 2  # scroll at screen centre
    if t == "navigate":
        if a.url is None or not a.url.startswith(("http://", "https://", "about:")):
            raise ActionError("navigate requires a url starting with http(s):// or about:")
    return a


def execute_action(browser, action: Action) -> None:
    """Map a validated Action onto the pixel primitives of ``browser``.

    This is the single place where actions become CDP (or fake-site)
    input events. Nothing else in the codebase touches the browser.
    """
    t = action.type
    if t in ("click", "double_click", "right_click"):
        x, y = action.point
        if t == "click":
            browser.click(x, y)
        elif t == "double_click":
            browser.double_click(x, y)
        else:
            browser.right_click(x, y)
    elif t == "drag":
        browser.drag(action.x, action.y, action.x2, action.y2)
    elif t == "scroll":
        x, y = action.point or (browser.screen_size[0] // 2, browser.screen_size[1] // 2)
        per = 120  # one wheel step
        if action.direction == "up":
            browser.scroll(x, y, -per * action.amount)
        elif action.direction == "down":
            browser.scroll(x, y, per * action.amount)
        else:
            # Browsers scroll vertically with the wheel; left/right are
            # accepted by the schema but are no-ops on a standard page.
            pass
    elif t == "type":
        x, y = action.point
        browser.click(x, y)  # focus the field first, like a human
        browser.type_text(action.value)
    elif t == "press":
        browser.press_key(action.key)
    elif t == "hotkey":
        browser.hotkey(*action.keys)
    elif t == "wait":
        browser.wait(action.seconds)
    elif t == "navigate":
        browser.navigate(action.url)
    elif t == "back":
        browser.go_back()
    elif t == "forward":
        browser.go_forward()
    elif t == "reload":
        browser.reload()
    elif t in ("done", "error"):
        pass
    else:  # pragma: no cover - parse_action guards this
        raise ActionError(f"cannot execute unknown action {t!r}")
