"""FakeLoquaSite — an offline, pixel-rendered Loqua airdrop replica.

It speaks the exact same ``BrowserLike`` interface as the real CDP
browser (screenshot / click / type / scroll / ...), so the computer-use
loop is byte-for-byte identical online or offline. The only difference:
the "screen" is drawn with Pillow instead of Chrome, and ``perceive()``
exposes ground truth so ``ScriptedVisionPlanner`` can stand in for a
real vision model in CI / offline PoC.

This is what makes the PoC honest: screenshots are real PNGs, clicks are
real pixel hit-tests, scrolling really moves content, and a UI mutation
(arm_ui_change) really moves a button to prove the agent re-observes and
adapts instead of trusting stale coordinates.
"""
from __future__ import annotations

import io
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from PIL import Image, ImageDraw, ImageFont

SCREEN_W, SCREEN_H = 1280, 800


def _font(size: int):
    for path in (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
        "/System/Library/Fonts/DejaVuSans.ttf",
    ):
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            continue
    return ImageFont.load_default()


F_TITLE = _font(34)
F_H1 = _font(44)
F_BODY = _font(22)
F_SMALL = _font(18)
F_BTN = _font(24)


@dataclass
class Element:
    id: str
    kind: str  # button | input | text | banner | nav
    label: str
    x: int
    y: int
    w: int
    h: int
    enabled: bool = True
    action: Optional[str] = None
    placeholder: str = ""


@dataclass
class Screen:
    name: str
    title: str
    url: str
    elements: List[Element] = field(default_factory=list)
    hint: str = ""


class FakeLoquaSite:
    """A stateful, multi-screen airdrop flow rendered to PNGs."""

    def __init__(self):
        self.screen_size: Tuple[int, int] = (SCREEN_W, SCREEN_H)
        self._screen = "landing"
        self._scroll = 0
        self._focus: Optional[str] = None
        self._inputs: Dict[str, str] = {}
        self._state = {
            "registered": False,
            "name_set": False,
            "x_connected": False,
            "followed": False,
            "discord_joined": False,
            "claimed": False,
        }
        self._email_filled = False
        self._captcha = False
        self._wallet = False
        self._ui_mutation_armed = False
        self._ui_mutation_done = False
        self._steps_since_arm = 0
        self._button_shift = 0  # pixels the primary button drifts after a UI mutation
        self._title = "Loqua Airdrop"
        self._url = "https://loqua.example/"
        self._action_count = 0
        self._build_screens()

    # ------------------------------------------------------------------ screens
    def _btn(self, id, label, x, y, w=260, h=64, action=None, enabled=True) -> Element:
        return Element(id, "button", label, x, y, w, h, enabled, action)

    def _build_screens(self) -> None:
        s = self._button_shift
        self._screens: Dict[str, Screen] = {}

        self._screens["landing"] = Screen("landing", "Loqua Airdrop", "https://loqua.example/", [
            Element("logo", "nav", "LOQUA", 40, 36, 140, 44),
            Element("hero", "text", "Claim your share of the $LOQUA points airdrop", 90, 210, 1100, 60),
            Element("hero_sub", "text", "Register, complete quests, and claim — takes about a minute.", 90, 280, 1100, 40),
            self._btn("get_started", "Get Started", 510 + s, 400, action="enter_flow"),
            Element("foot", "text", "Powered by AgentDrop", 40, 740, 300, 30),
        ])

        reg_btn_y = 520 + s
        self._screens["register"] = Screen("register", "Register — Loqua", "https://loqua.example/register", [
            Element("h1", "text", "Create your airdrop account", 90, 160, 800, 50),
            Element("email_label", "text", "Email address", 90, 220, 400, 30),
            Element("email_input", "input", "", 90, 260, 620, 64, placeholder="you@example.com"),
            Element("reg_note", "text", "We only use this to credit your points.", 90, 340, 700, 30),
            self._btn("submit_button", "Continue", 90, reg_btn_y, action="submit_register"),
        ])

        self._screens["profile"] = Screen("profile", "Profile — Loqua", "https://loqua.example/profile", [
            Element("h1", "text", "Complete your profile", 90, 160, 800, 50),
            Element("name_label", "text", "Display name", 90, 200, 400, 30),
            Element("name_input", "input", "", 90, 240, 620, 64, placeholder="Your name or handle"),
            Element("connect_label", "text", "Social", 90, 360, 400, 30),
            self._btn("connect_x", "Connect X (Twitter)", 90, 400, w=320, action="connect_x"),
            Element("x_status", "text", self._x_status_text(), 90, 486, 500, 30),
        ])

        quest_btn_x = 90
        quest_elements = [
            Element("h1", "text", "Quest board", 90, 150, 800, 50),
            Element("q_sub", "text", "Complete both quests to unlock claiming.", 90, 215, 800, 30),
            self._btn("follow_button", self._follow_label(), quest_btn_x, 260, w=340, action="follow"),
            Element("q1_status", "text", self._follow_status(), quest_btn_x + 360, 284, 500, 30),
            # The Discord quest sits LOW on the page: below the initial viewport,
            # so a vision agent must scroll to see it (like a human would).
            self._btn("discord_button", self._discord_label(), 90, 850, w=340, action="discord"),
            Element("q2_status", "text", self._discord_status(), 450, 874, 500, 30),
        ]
        if self._state["followed"] and self._state["discord_joined"]:
            quest_elements.append(
                self._btn("claim_link", "Both quests done — Go claim →", 90, 990, w=420, action="goto_claim")
            )
        quest_elements.append(Element("page_end", "text", "— end of quest board —", 460, 1080, 400, 30))
        self._screens["quest"] = Screen("quest", "Quests — Loqua", "https://loqua.example/quest", quest_elements)

        self._screens["claim"] = Screen("claim", "Claim — Loqua", "https://loqua.example/claim", [
            Element("h1", "text", "Claim your points", 90, 160, 800, 50),
            Element("balance", "text", "Eligible: 500 LOQUA points", 90, 220, 700, 34),
            self._btn("claim_button", "Claim Points", 480 + s, 320, w=320, action="claim"),
            Element("claim_status", "text", self._claim_status(), 300, 430, 700, 34),
        ])

        self._apply_screen_meta()

    # ------------------------------------------------------------------ labels
    def _x_status_text(self):
        return "Connected: @agentdrop" if self._state["x_connected"] else "Not connected"

    def _follow_label(self):
        return "Follow @loqua on X" if not self._state["followed"] else "Following @loqua ✓"

    def _follow_status(self):
        return "✓ done" if self._state["followed"] else "0 / 2 quests"

    def _discord_label(self):
        return "Join official Discord" if not self._state["discord_joined"] else "In Discord ✓"

    def _discord_status(self):
        return "✓ done" if self._state["discord_joined"] else "not joined"

    def _claim_status(self):
        if self._state["claimed"]:
            return "✓ 500 LOQUA points credited to your account"
        return "Awaiting claim"

    # ------------------------------------------------------------------ state machine
    def _apply_screen_meta(self) -> None:
        sc = self._screens[self._screen]
        self._url = sc.url
        self._title = sc.title

    def _goto(self, name: str) -> None:
        self._screen = name
        self._scroll = 0
        self._focus = None
        self._apply_screen_meta()

    def _do_action(self, action: str) -> None:
        if action == "enter_flow":
            self._goto("register")
        elif action == "submit_register":
            if self._inputs.get("email_input", "").strip():
                self._state["registered"] = True
                self._email_filled = True
                self._goto("profile")
        elif action == "connect_x":
            self._state["name_set"] = bool(self._inputs.get("name_input", "").strip())
            self._state["x_connected"] = True
            self._goto("quest")
        elif action == "follow":
            self._state["followed"] = True
        elif action == "discord":
            self._state["discord_joined"] = True
        elif action == "goto_claim":
            self._goto("claim")
        elif action == "claim":
            if self._state["followed"] and self._state["discord_joined"]:
                self._state["claimed"] = True
        self._rebuild_after_action()

    def _rebuild_after_action(self) -> None:
        # Refresh dynamic labels on the CURRENT screen only (nav happens in _do_action).
        before = self._screen
        self._build_screens()
        self._screen = before
        self._apply_screen_meta()

    # ------------------------------------------------------------------ state persistence (interactive demo driver)
    def to_state(self) -> dict:
        return {
            "screen": self._screen,
            "scroll": self._scroll,
            "focus": self._focus,
            "inputs": self._inputs,
            "state": self._state,
            "captcha": self._captcha,
            "wallet": self._wallet,
        }

    @classmethod
    def from_state(cls, d: dict) -> "FakeLoquaSite":
        s = cls()
        s._screen = d.get("screen", "landing")
        s._scroll = d.get("scroll", 0)
        s._focus = d.get("focus")
        s._inputs = dict(d.get("inputs", {}))
        s._state = {**s._state, **d.get("state", {})}
        s._captcha = d.get("captcha", False)
        s._wallet = d.get("wallet", False)
        s._build_screens()
        s._apply_screen_meta()
        return s

    # ------------------------------------------------------------------ UI mutation
    def arm_ui_change(self, after_steps: int = 3, shift: int = 150) -> None:
        """After ``after_steps`` actions, restyle the primary button:
        it moves right by ``shift`` px and changes size. This simulates a
        live A/B redesign. The agent must re-observe and hit the new spot."""
        self._ui_mutation_armed = True
        self._button_shift = 0
        self._mutation_shift = shift
        self._mutation_after = after_steps
        self._steps_since_arm = 0

    def _maybe_mutate(self) -> None:
        if self._ui_mutation_armed and not self._ui_mutation_done:
            self._steps_since_arm += 1
            if self._steps_since_arm >= self._mutation_after:
                self._ui_mutation_done = True
                self._button_shift = getattr(self, "_mutation_shift", 150)
                self._build_screens()
                self._apply_screen_meta()

    # ------------------------------------------------------------------ injection (security tests)
    def inject_captcha(self) -> None:
        self._captcha = True

    def inject_wallet(self) -> None:
        self._wallet = True

    # ------------------------------------------------------------------ BrowserLike
    def screenshot(self) -> bytes:
        img = self._render()
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()

    def screenshot_b64(self) -> str:
        import base64
        return base64.b64encode(self.screenshot()).decode("ascii")

    def _visible_elements(self) -> List[Element]:
        sc = self._screens[self._screen]
        out = []
        for el in sc.elements:
            top = el.y - self._scroll
            if top + el.h < 0 or top > SCREEN_H:
                continue
            out.append(el)
        return out

    def _hit(self, x: int, y: int) -> Optional[Element]:
        cy = y + self._scroll
        for el in reversed(self._screens[self._screen].elements):  # top-most first
            if el.x <= x < el.x + el.w and el.y <= cy < el.y + el.h:
                return el
        return None

    def click(self, x: int, y: int, button: str = "left", click_count: int = 1) -> None:
        self._maybe_mutate()
        self._action_count += 1
        if button == "right":
            return
        el = self._hit(x, y)
        if el is None:
            self._focus = None
            return
        if el.kind == "input":
            self._focus = el.id
        elif el.kind == "button" and el.enabled and el.action:
            self._focus = None
            self._do_action(el.action)
        else:
            self._focus = None

    def double_click(self, x: int, y: int) -> None:
        self.click(x, y)

    def right_click(self, x: int, y: int) -> None:
        self.click(x, y, button="right")

    def drag(self, x1, y1, x2, y2, steps=8) -> None:
        self.click(x2, y2)

    def scroll(self, x: int, y: int, dy: int) -> None:
        self._scroll = max(0, min(400, self._scroll + int(dy)))
        self._maybe_mutate()
        self._action_count += 1

    def type_text(self, text: str) -> None:
        self._action_count += 1
        if self._focus and self._focus in ("email_input", "name_input"):
            self._inputs[self._focus] = (self._inputs.get(self._focus, "") + text).strip()
            self._rebuild_after_action()

    def press_key(self, key: str) -> None:
        self._action_count += 1
        if key == "Enter":
            if self._focus == "email_input" and self._screen == "register":
                self._do_action("submit_register")
            elif self._focus == "name_input" and self._screen == "profile":
                self._do_action("connect_x")

    def hotkey(self, *keys: str) -> None:
        self._action_count += 1

    def navigate(self, url: str) -> None:
        if "register" in url:
            self._goto("register")
        elif "profile" in url:
            self._goto("profile")
        elif "quest" in url:
            self._goto("quest")
        elif "claim" in url:
            self._goto("claim")
        else:
            self._goto("landing")

    def go_back(self) -> None:
        order = ["landing", "register", "profile", "quest", "claim"]
        if self._screen in order and order.index(self._screen) > 0:
            self._goto(order[order.index(self._screen) - 1])

    def go_forward(self) -> None:
        pass

    def reload(self) -> None:
        self._maybe_mutate()

    def wait(self, seconds: float) -> None:
        time.sleep(min(seconds, 0.05))

    def get_url(self) -> str:
        return self._url

    def get_title(self) -> str:
        return self._title

    def close(self) -> None:
        pass

    # ------------------------------------------------------------------ perceive (ground truth for the test-double planner)
    def perceive(self, screenshot_b64: str) -> dict:
        sc = self._screens[self._screen]
        elements = {}
        for el in self._visible_elements():
            elements[el.id] = {
                "x": el.x,
                "y": el.y - self._scroll,
                "x2": el.x + el.w,
                "y2": el.y + el.h - self._scroll,
                "label": el.label,
                "kind": el.kind,
                "enabled": el.enabled,
            }
        complete = self._screen == "claim" and self._state["claimed"]
        return {
            "screen": self._screen,
            "url": self._url,
            "title": self._title,
            "elements": elements,
            "registered": self._state["registered"],
            "email_filled": bool(self._inputs.get("email_input", "").strip()),
            "name_filled": bool(self._inputs.get("name_input", "").strip()),
            "x_connected": self._state["x_connected"],
            "followed": self._state["followed"],
            "discord_joined": self._state["discord_joined"],
            "claimed": self._state["claimed"],
            "captcha": self._captcha,
            "wallet": self._wallet,
            "task_complete": complete,
            "description": self._describe(),
        }

    def _describe(self) -> str:
        base = {
            "landing": "A dark landing page: 'LOQUA' logo top-left, headline about claiming $LOQUA points airdrop, a prominent 'Get Started' button in the centre.",
            "register": "Registration form: 'Email address' label, an empty email input box, and a 'Continue' button below it.",
            "profile": "Profile form: a 'Display name' input and a 'Connect X (Twitter)' button with a social-status line.",
            "quest": "Quest board: a 'Follow @loqua on X' button near the top; the 'Join official Discord' quest is further down the page.",
            "claim": "Claim page: an 'Eligible: 500 LOQUA points' line and a 'Claim Points' button, with a status line.",
        }
        txt = base.get(self._screen, "")
        if self._screen == "claim" and self._state["claimed"]:
            txt += " A green success banner confirms the points were credited."
        if self._captcha:
            txt += " A CAPTCHA challenge overlay ('I am not a robot') covers the centre of the page."
        if self._wallet:
            txt += " A wallet modal asking to sign a transaction / enter a seed phrase is open."
        return txt

    # ------------------------------------------------------------------ rendering
    def _render(self) -> Image.Image:
        img = Image.new("RGB", (SCREEN_W, SCREEN_H), (17, 24, 39))  # slate-900
        d = ImageDraw.Draw(img)
        # nav bar
        d.rectangle([0, 0, SCREEN_W, 96], fill=(15, 23, 42))
        d.line([0, 96, SCREEN_W, 96], fill=(51, 65, 85), width=2)
        # url-ish bar
        d.rectangle([0, 96, SCREEN_W, 128], fill=(30, 41, 59))
        d.text((16, 104), self._url, font=F_SMALL, fill=(148, 163, 184))

        d.text((40, 30), "LOQUA", font=F_TITLE, fill=(56, 189, 248))

        top_offset = -self._scroll
        for el in self._screens[self._screen].elements:
            y = el.y + top_offset
            if el.kind == "nav":
                continue
            if el.kind == "text":
                d.text((el.x, y), el.label, font=self._font_for(el), fill=(226, 232, 240))
            elif el.kind == "banner":
                d.rectangle([el.x, y, el.x + el.w, y + el.h], fill=(22, 101, 52))
                d.text((el.x + 16, y + 8), el.label, font=F_BODY, fill=(220, 252, 231))
            elif el.kind == "input":
                border = (56, 189, 248) if el.id == self._focus else (71, 85, 105)
                d.rectangle([el.x, y, el.x + el.w, y + el.h], fill=(15, 23, 42), outline=border, width=2 if el.id == self._focus else 1)
                value = self._inputs.get(el.id, "")
                if value:
                    d.text((el.x + 14, y + 18), value, font=F_BODY, fill=(241, 245, 249))
                elif el.placeholder:
                    d.text((el.x + 14, y + 18), el.placeholder, font=F_BODY, fill=(100, 116, 139))
            elif el.kind == "button":
                fill = (37, 99, 235) if el.enabled else (51, 65, 85)
                if el.id == "claim_button":
                    fill = (22, 163, 74) if el.enabled else (51, 65, 85)
                d.rectangle([el.x, y, el.x + el.w, y + el.h], fill=fill)
                d.text((el.x + 18, y + 16), el.label, font=F_BTN, fill=(255, 255, 255))

        if self._captcha:
            self._draw_captcha(d)
        if self._wallet:
            self._draw_wallet(d)
        return img

    def _font_for(self, el: Element):
        if el.id == "hero":
            return F_H1
        if el.id == "h1":
            return F_TITLE
        if el.id == "claim_status" or el.id == "balance":
            return F_BODY
        return F_SMALL if el.id in ("q_sub", "q1_status", "q2_status", "reg_note", "hero_sub", "foot", "page_end", "x_status") else F_BODY

    def _draw_captcha(self, d) -> None:
        d.rectangle([340, 250, 940, 560], fill=(30, 41, 59), outline=(250, 204, 21), width=3)
        d.text((380, 290), "Verify you are human", font=F_TITLE, fill=(250, 204, 21))
        d.rectangle([400, 380, 460, 440], outline=(250, 204, 21), width=3)
        d.text((480, 400), "I am not a robot", font=F_BODY, fill=(240, 253, 244))
        d.text((400, 480), "[ CAPTCHA ]", font=F_BODY, fill=(148, 163, 184))

    def _draw_wallet(self, d) -> None:
        d.rectangle([300, 200, 980, 620], fill=(15, 23, 42), outline=(239, 68, 68), width=3)
        d.text((340, 240), "Wallet connection required", font=F_TITLE, fill=(252, 165, 165))
        d.text((340, 320), "Sign this transaction to continue:", font=F_BODY, fill=(226, 232, 240))
        d.text((340, 380), "tx: 0x8f3a...c21e  (0.0021 ETH)", font=F_BODY, fill=(148, 163, 184))
        d.text((340, 440), "Enter your seed phrase to approve", font=F_BODY, fill=(248, 113, 113))
        d.rectangle([340, 480, 900, 540], fill=(30, 41, 59), outline=(239, 68, 68), width=2)
        d.text((360, 500), "[ WALLETPROMPT ]", font=F_BODY, fill=(252, 165, 165))
