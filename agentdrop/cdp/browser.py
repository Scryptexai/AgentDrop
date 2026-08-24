"""Browser session: pixel-level mouse/keyboard/screenshot over CDP.

This is the ONLY allowed surface for browser interaction in AgentDrop.
No CSS selectors, no XPath, no DOM scraping — the agent sees pixels and
acts on pixels, exactly like a human.

The only non-pixel reads permitted are metadata (current URL / page
title / load state). They give the vision model context, never input
targets. Everything actionable comes from the screenshot.
"""
from __future__ import annotations

import base64
import json
import time
from dataclasses import dataclass, field
from typing import List, Optional, Protocol, Tuple, runtime_checkable

import requests

from .client import CDPClient, CDPError

# ---------------------------------------------------------------------------
# Virtual key codes (subset used by the action set)
# ---------------------------------------------------------------------------
_SPECIAL_KEYS = {
    "Enter": ("Enter", 13),
    "Tab": ("Tab", 9),
    "Backspace": ("Backspace", 8),
    "Delete": ("Delete", 46),
    "Space": ("Space", 32),
    "Escape": ("Escape", 27),
    "ArrowLeft": ("ArrowLeft", 37),
    "ArrowUp": ("ArrowUp", 38),
    "ArrowRight": ("ArrowRight", 39),
    "ArrowDown": ("ArrowDown", 40),
    "Home": ("Home", 36),
    "End": ("End", 35),
    "PageUp": ("PageUp", 33),
    "PageDown": ("PageDown", 34),
    "F5": ("F5", 116),
}

_PUNCT_CODES = {
    ".": "Period", ",": "Comma", "?": "Question", "!": "Exclamation",
    "/": "Slash", ":": "Colon", ";": "Semicolon", "'": "Quote",
    '"': "Quote", "(": "BracketLeft", ")": "BracketRight",
    "[": "BracketLeft", "]": "BracketRight", "-": "Minus", "_": "Minus",
    "=": "Equal", "+": "Equal", "*": "Digit8", "#": "Digit3", "%": "Digit5",
    "&": "Digit7", "@": "Digit2",
}

_MODIFIERS = {
    "ctrl": ("ControlLeft", "Control", 17),
    "shift": ("ShiftLeft", "Shift", 16),
    "alt": ("AltLeft", "Alt", 18),
    "meta": ("MetaLeft", "Meta", 91),
    "cmd": ("MetaLeft", "Meta", 91),
}


def _char_key(ch: str) -> Tuple[str, int]:
    """(code, windowsVirtualKeyCode) for a printable character."""
    if ch.isalpha():
        return f"Key{ch.upper()}", ord(ch.upper())
    if ch.isdigit():
        return f"Digit{ch}", ord(ch)
    code = _PUNCT_CODES.get(ch, "")
    return code, ord(ch)


@runtime_checkable
class BrowserLike(Protocol):
    """Interface shared by the real CDP browser and the fake pixel site.

    Every method here is a *pixel or screen* primitive. There is
    deliberately no selector-based method on this protocol.
    """

    screen_size: Tuple[int, int]

    def screenshot(self) -> bytes: ...
    def click(self, x: int, y: int, button: str = "left", click_count: int = 1) -> None: ...
    def double_click(self, x: int, y: int) -> None: ...
    def right_click(self, x: int, y: int) -> None: ...
    def drag(self, x1: int, y1: int, x2: int, y2: int, steps: int = 8) -> None: ...
    def scroll(self, x: int, y: int, dy: int) -> None: ...
    def type_text(self, text: str) -> None: ...
    def press_key(self, key: str) -> None: ...
    def hotkey(self, *keys: str) -> None: ...
    def navigate(self, url: str) -> None: ...
    def go_back(self) -> None: ...
    def go_forward(self) -> None: ...
    def reload(self) -> None: ...
    def wait(self, seconds: float) -> None: ...
    def get_url(self) -> str: ...
    def get_title(self) -> str: ...
    def close(self) -> None: ...


class BrowserSession:
    """Human-like browser control over CDP.

    Actions mirror a real human: the mouse *moves* before it clicks,
    drags travel in interpolated steps, typing dispatches real key
    events with a small inter-key delay, and wheels scroll in chunks.
    """

    def __init__(
        self,
        client: CDPClient,
        screen_w: int = 1280,
        screen_h: int = 800,
        settle_ms: int = 600,
        type_delay_ms: int = 12,
    ):
        self.client = client
        self.screen_size = (int(screen_w), int(screen_h))
        self.settle_ms = settle_ms
        self.type_delay_ms = type_delay_ms

    # ------------------------------------------------------------------ factory
    @classmethod
    def connect(
        cls,
        host: str = "127.0.0.1",
        port: int = 9223,
        viewport: Tuple[int, int] = (1280, 800),
        prefer_url: Optional[str] = None,
    ) -> "BrowserSession":
        """Connect to an already-running Chrome exposed on ``port``."""
        base = f"http://{host}:{port}"
        version = requests.get(f"{base}/json/version", timeout=5).json()
        targets = requests.get(f"{base}/json/list", timeout=5).json()
        pages = [t for t in targets if t.get("type") == "page"]
        target = None
        if prefer_url:
            target = next((t for t in pages if prefer_url in t.get("url", "")), None)
        if target is None:
            target = pages[0] if pages else None
        if target is None or not target.get("webSocketDebuggerUrl"):
            raise CDPError("connect", f"no page target found at {base}/json/list")
        client = CDPClient(target["webSocketDebuggerUrl"]).connect()
        client.enable("Page")
        client.enable("Runtime")
        w, h = viewport
        try:
            client.send(
                "Emulation.setDeviceMetricsOverride",
                {"width": w, "height": h, "deviceScaleFactor": 1, "mobile": False},
            )
        except CDPError:
            pass
        w_real, h_real = w, h
        try:
            metrics = client.send("Page.getLayoutMetrics")
            vv = metrics.get("cssLayoutViewport") or {}
            if vv.get("width") and vv.get("height"):
                w_real, h_real = int(vv["width"]), int(vv["height"])
        except CDPError:
            pass
        return cls(client, w_real, h_real)

    # ------------------------------------------------------------------ metadata
    def _evaluate(self, expr: str) -> Optional[str]:
        try:
            res = self.client.send("Runtime.evaluate", {"expression": expr, "returnByValue": True})
            val = (res.get("result") or {}).get("value")
            return val if isinstance(val, str) else None
        except CDPError:
            return None

    def get_url(self) -> str:
        return self._evaluate("location.href") or ""

    def get_title(self) -> str:
        return self._evaluate("document.title") or ""

    def wait_for_load(self, timeout: float = 30.0) -> None:
        """Wait for the load event (if still in flight) plus a settle delay
        so client-side rendering stabilises before we screenshot."""
        self.client.wait_event("Page.loadEventFired", timeout=timeout)
        self.client.wait_ms(self.settle_ms)

    # ------------------------------------------------------------------ screenshot
    def screenshot(self) -> bytes:
        res = self.client.send("Page.captureScreenshot", {"format": "png", "fromSurface": True})
        return base64.b64decode(res.get("data", ""))

    def screenshot_b64(self) -> str:
        return base64.b64encode(self.screenshot()).decode("ascii")

    # ------------------------------------------------------------------ mouse
    def _mouse(self, etype: str, x: int, y: int, **extra) -> None:
        params = {
            "type": etype,
            "x": int(x),
            "y": int(y),
            "button": extra.pop("button", "none"),
            "clickCount": extra.pop("clickCount", 1),
            **extra,
        }
        self.client.send("Input.dispatchMouseEvent", params)

    def click(self, x: int, y: int, button: str = "left", click_count: int = 1) -> None:
        # Human-like: the pointer travels to the target before pressing.
        self._mouse("mouseMoved", x, y)
        for i in range(1, click_count + 1):
            if i > 1:
                self.client.wait_ms(80)
            self._mouse("mousePressed", x, y, button=button, clickCount=i)
            self.client.wait_ms(40)
            self._mouse("mouseReleased", x, y, button=button, clickCount=i)

    def double_click(self, x: int, y: int) -> None:
        self.click(x, y, click_count=2)

    def right_click(self, x: int, y: int) -> None:
        self.click(x, y, button="right")

    def drag(self, x1: int, y1: int, x2: int, y2: int, steps: int = 8) -> None:
        self._mouse("mouseMoved", x1, y1)
        self._mouse("mousePressed", x1, y1, button="left")
        for i in range(1, steps + 1):
            t = i / steps
            self._mouse("mouseMoved", round(x1 + (x2 - x1) * t), round(y1 + (y2 - y1) * t))
            self.client.wait_ms(16)
        self._mouse("mouseReleased", x2, y2, button="left")

    def scroll(self, x: int, y: int, dy: int) -> None:
        """Wheel-scroll at (x, y). ``dy`` in pixels; positive = scroll down."""
        total = int(dy)
        step = 120
        while total != 0:
            chunk = max(-step, min(step, total))
            self._mouse("mouseWheel", x, y, deltaX=0, deltaY=chunk, button="none")
            total -= chunk
            self.client.wait_ms(30)
        self.client.wait_ms(self.settle_ms)

    # ------------------------------------------------------------------ keyboard
    def _key(self, etype: str, key: str, **extra) -> dict:
        if key in _SPECIAL_KEYS:
            code, vk = _SPECIAL_KEYS[key]
            return {"type": etype, "key": key, "code": code, "windowsVirtualKeyCode": vk, **extra}
        if len(key) == 1:
            code, vk = _char_key(key)
            return {"type": etype, "key": key, "code": code, "windowsVirtualKeyCode": vk, **extra}
        raise ValueError(f"unsupported key: {key!r}")

    def type_text(self, text: str) -> None:
        for ch in text:
            if ch == "\n":
                self._dispatch_key("Enter")
            elif ch == "\t":
                self._dispatch_key("Tab")
            else:
                self._dispatch_key(ch)
            self.client.wait_ms(self.type_delay_ms)

    def _dispatch_key(self, key: str, text: Optional[str] = None) -> None:
        down = self._key("rawKeyDown", key)
        self.client.send("Input.dispatchKeyEvent", down)
        if text:
            self.client.send(
                "Input.dispatchKeyEvent",
                {"type": "char", "text": text, "unmodifiedText": text},
            )
        up = self._key("keyUp", key)
        self.client.send("Input.dispatchKeyEvent", up)

    def press_key(self, key: str) -> None:
        self._dispatch_key(key)

    def hotkey(self, *keys: str) -> None:
        """e.g. hotkey("ctrl", "c"). Last key is pressed while modifiers hold."""
        if len(keys) < 2:
            raise ValueError("hotkey needs at least a modifier and a key")
        mods, main = keys[:-1], keys[-1]
        for m in mods:
            if m not in _MODIFIERS:
                raise ValueError(f"unknown modifier: {m}")
        for code, k, vk in [ _MODIFIERS[m] for m in mods ]:
            self.client.send(
                "Input.dispatchKeyEvent",
                {"type": "rawKeyDown", "key": k, "code": code, "windowsVirtualKeyCode": vk},
            )
        text = main if (len(main) == 1 and main.isprintable() and main not in _SPECIAL_KEYS) else None
        self._dispatch_key(main, text=text)
        for code, k, vk in [ _MODIFIERS[m] for m in reversed(mods) ]:
            self.client.send(
                "Input.dispatchKeyEvent",
                {"type": "keyUp", "key": k, "code": code, "windowsVirtualKeyCode": vk},
            )

    # ------------------------------------------------------------------ navigation
    def navigate(self, url: str) -> None:
        self.client.send("Page.navigate", {"url": url})
        self.wait_for_load()

    def go_back(self) -> None:
        # A human presses Alt+ArrowLeft — so does the agent (no JS shims).
        self.hotkey("alt", "ArrowLeft")
        self.wait_for_load()

    def go_forward(self) -> None:
        self.hotkey("alt", "ArrowRight")
        self.wait_for_load()

    def reload(self) -> None:
        self.client.send("Page.reload")
        self.wait_for_load()

    def wait(self, seconds: float) -> None:
        time.sleep(max(0.0, float(seconds)))

    def close(self) -> None:
        self.client.close()
