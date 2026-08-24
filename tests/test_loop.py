"""End-to-end tests of the computer-use loop against the pixel-rendered
Loqua replica, plus targeted tests for recovery, verification, and the
security gate.

These run fully offline: screenshots are real PNGs, clicks are real
pixel hit-tests, and the only simulated component is the vision model's
perception (a ground-truth oracle wired to the fake site).
"""
import io
import os

import pytest
from PIL import Image, ImageDraw

from agentdrop.campaigns.base import Campaign, TaskSpec
from agentdrop.loop.actions import Action, ActionError
from agentdrop.loop.computer_use import ComputerUseLoop, LoopConfig
from agentdrop.loop.metrics import Metrics, TARGETS
from agentdrop.loop.security import SecurityGate, SecurityPolicy
from agentdrop.vision.planner import PageState, Plan, ScriptedVisionPlanner
from fakesites.loqua.site import FakeLoquaSite

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOQUA_CAMPAIGN = os.path.join(REPO, "agentdrop", "campaigns", "loqua.yaml")


def _run_campaign(site, planner, tmp_path, **loop_kwargs):
    cfg = LoopConfig(evidence_dir=str(tmp_path / "evidence"), **loop_kwargs)
    metrics = Metrics(max_steps=cfg.max_steps)
    loop = ComputerUseLoop(
        browser=site,
        planner=planner,
        metrics=metrics,
        security=SecurityGate(SecurityPolicy()),
        config=cfg,
    )
    campaign = Campaign.load(LOQUA_CAMPAIGN)
    result = loop.run_campaign(campaign, run_dir=str(tmp_path / "evidence"))
    return result, metrics


# ---------------------------------------------------------------------------
# 1. The benchmark: all 5 Loqua tasks, offline
# ---------------------------------------------------------------------------
def test_full_campaign_benchmark(tmp_path):
    site = FakeLoquaSite()
    planner = ScriptedVisionPlanner(perceive=site.perceive)
    result, metrics = _run_campaign(site, planner, tmp_path)

    assert result.all_completed, [t.error for t in result.tasks]
    assert metrics.tasks_completed == 5
    # --- validation targets from docs/VALIDATION.md ---
    assert metrics.task_completion >= TARGETS["task_completion_min"]
    assert metrics.total_steps < TARGETS["max_steps"], f"{metrics.total_steps} steps"
    assert metrics.click_accuracy is not None
    assert metrics.click_accuracy >= TARGETS["click_accuracy_min"]
    # happy path needs no recovery
    assert metrics.recovery_events == 0


def test_ui_change_mid_run_is_absorbed(tmp_path):
    """A live redesign moves the primary button mid-campaign; the agent
    must re-observe and still finish 5/5."""
    site = FakeLoquaSite()
    site.arm_ui_change(after_steps=2, shift=170)
    planner = ScriptedVisionPlanner(perceive=site.perceive)
    result, metrics = _run_campaign(site, planner, tmp_path)

    assert site._button_shift == 170  # the mutation actually happened
    assert result.all_completed, [t.error for t in result.tasks]
    assert metrics.task_completion == 1.0
    assert metrics.click_accuracy >= TARGETS["click_accuracy_min"]


def test_screen_understanding(tmp_path):
    """The agent must be able to describe what's on screen (benchmark
    metric 'Screen understanding')."""
    site = FakeLoquaSite()
    planner = ScriptedVisionPlanner(perceive=site.perceive)
    _, metrics = _run_campaign(site, planner, tmp_path)
    descs = metrics.descriptions()
    joined = " | ".join(descs)
    assert "Get Started" in joined
    assert "email" in joined.lower()
    assert "Display name" in joined
    assert "Quest board" in joined
    assert "Claim" in joined


# ---------------------------------------------------------------------------
# 2. Recovery from a stale coordinate (the core 'UI changed' scenario)
# ---------------------------------------------------------------------------
class MovingButtonPage:
    """One screen, one button that sits at a KNOWN position. Clicking it
    paints a 'Clicked!' banner (a real pixel change)."""

    screen_size = (800, 400)

    def __init__(self, button_x):
        self.button_x = button_x
        self.clicked = False

    def screenshot(self):
        img = Image.new("RGB", (800, 400), (17, 24, 39))
        d = ImageDraw.Draw(img)
        d.rectangle([self.button_x, 150, self.button_x + 160, 210], fill=(37, 99, 235))
        d.text((self.button_x + 55, 168), "GO", fill=(255, 255, 255))
        if self.clicked:
            d.text((330, 260), "Clicked!", fill=(74, 222, 128))
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()

    def click(self, x, y, button="left", click_count=1):
        if self.button_x <= x < self.button_x + 160 and 150 <= y < 210:
            self.clicked = True

    def double_click(self, x, y): self.click(x, y)
    def right_click(self, x, y): pass
    def drag(self, x1, y1, x2, y2, steps=8): pass
    def scroll(self, x, y, dy): pass
    def type_text(self, text): pass
    def press_key(self, key): pass
    def hotkey(self, *keys): pass
    def navigate(self, url): pass
    def go_back(self): pass
    def go_forward(self): pass
    def reload(self): pass
    def wait(self, seconds): pass
    def get_url(self): return "https://example.test/"
    def get_title(self): return "Moving button"
    def close(self): pass

    def perceive(self, b64):
        return {
            "screen": "page",
            "elements": {"go": {"x": self.button_x, "y": 150, "x2": self.button_x + 160, "y2": 210}},
            "clicked": self.clicked,
            "description": f"A GO button around x={self.button_x}."
            + (" A 'Clicked!' banner is shown." if self.clicked else ""),
        }


class StaleFirstPlanner:
    """Simulates a vision model that first acts from STALE memory
    (clicks where the button used to be), then re-reads the screen after
    the loop's re-observe hint and hits the real position."""

    def __init__(self, page, stale_point):
        self.page = page
        self.stale_point = stale_point
        self._calls = 0
        self.name = "stale-first-test-double"

    def plan(self, goal, b64, screen, history, extra_hint=""):
        self._calls += 1
        truth = self.page.perceive(b64)
        ps = PageState(description=truth["description"])
        if truth["clicked"]:
            return Plan(Action(type="done"), ps, "Clicked! banner visible; task done.")
        if self._calls == 1:
            x, y = self.stale_point
            return Plan(Action(type="click", x=x, y=y), ps, "Clicking the GO button where I last saw it.")
        el = truth["elements"]["go"]
        x, y = (el["x"] + el["x2"]) // 2, (el["y"] + el["y2"]) // 2
        return Plan(Action(type="click", x=x, y=y), ps, "Re-reading the screenshot: GO is at its current position.")

    def verify(self, goal, criteria, b64, screen):
        truth = self.page.perceive(b64)
        return truth["clicked"], truth["description"]


def test_stale_coordinate_recovers_via_reobserve(tmp_path):
    page = MovingButtonPage(button_x=500)      # button lives at x=500
    planner = StaleFirstPlanner(page, stale_point=(100, 180))  # but model clicks x=100 first

    metrics = Metrics(max_steps=50)
    loop = ComputerUseLoop(
        browser=page,
        planner=planner,
        metrics=metrics,
        security=SecurityGate(SecurityPolicy()),
        config=LoopConfig(evidence_dir=str(tmp_path / "evidence")),
    )
    task = TaskSpec(id="click_go", goal="Click the GO button.", done_criteria="A 'Clicked!' banner is visible.")
    run = loop.run_task(task, run_dir=str(tmp_path / "evidence"))
    loop.metrics.record_task(task.id, run.completed, run.steps, run.recoveries, run.error)

    assert run.completed, run.error
    assert run.recoveries == 1                       # exactly one re-observe was needed
    assert metrics.recovery_events == 1
    # the stale click counts as a missed first attempt; the adapted one succeeds
    assert metrics.click_accuracy == pytest.approx(0.5)
    no_change_steps = [s for s in metrics.steps if s.outcome == "no-change"]
    assert len(no_change_steps) == 1
    assert "2 attempts" in no_change_steps[0].action  # episode included the inline retry


def test_stuck_when_recovery_budget_exhausted():
    """A button that can never be clicked: after the recovery budget is
    spent the task must FAIL (not loop forever)."""
    class DeadPage(MovingButtonPage):
        def click(self, x, y, button="left", click_count=1):  # nothing ever works
            pass

    page = DeadPage(button_x=500)

    class AlwaysStalePlanner(StaleFirstPlanner):
        def plan(self, goal, b64, screen, history, extra_hint=""):
            # always clicks the wrong spot, even after re-observing
            truth = self.page.perceive(b64)
            return Plan(Action(type="click", x=5, y=5), PageState(description=truth["description"]), "still unsure")

    planner = AlwaysStalePlanner(page, stale_point=(100, 180))
    metrics = Metrics(max_steps=50)
    loop = ComputerUseLoop(
        browser=page, planner=planner, metrics=metrics,
        security=SecurityGate(SecurityPolicy()),
        config=LoopConfig(max_recoveries=2, max_steps_per_task=20),
    )
    task = TaskSpec(id="click_go", goal="Click the GO button.", done_criteria="banner")
    run = loop.run_task(task)
    assert not run.completed
    assert "stuck" in run.error
    assert run.recoveries == 2  # budget fully used, then stopped


# ---------------------------------------------------------------------------
# 3. Verifier: never assume success
# ---------------------------------------------------------------------------
class PrematureDonePlanner:
    """Claims 'done' before anything happened; only complies after the
    verifier rejects it with evidence."""

    def __init__(self, site):
        self.site = site
        self._calls = 0
        self.name = "premature-done-test-double"

    def plan(self, goal, b64, screen, history, extra_hint=""):
        self._calls += 1
        truth = self.site.perceive(b64)
        ps = PageState(description=truth["description"])
        if self._calls == 1:
            return Plan(Action(type="done"), ps, "Looks done to me.")
        if truth["screen"] == "landing":
            el = truth["elements"]["get_started"]
            return Plan(
                Action(type="click", x=(el["x"] + el["x2"]) // 2, y=(el["y"] + el["y2"]) // 2),
                ps, "Verifier says not done — click Get Started.",
            )
        return Plan(Action(type="done"), ps, "Now it is actually done.")

    def verify(self, goal, criteria, b64, screen):
        truth = self.site.perceive(b64)
        return truth["screen"] != "landing", truth["description"]


def test_premature_done_rejected_by_verifier(tmp_path):
    site = FakeLoquaSite()
    planner = PrematureDonePlanner(site)
    metrics = Metrics(max_steps=50)
    loop = ComputerUseLoop(
        browser=site, planner=planner, metrics=metrics,
        security=SecurityGate(SecurityPolicy()),
        config=LoopConfig(evidence_dir=str(tmp_path / "evidence")),
    )
    task = TaskSpec(id="t1", goal="Enter the airdrop flow: click Get Started.",
                    done_criteria="The landing hero is gone.")
    run = loop.run_task(task, run_dir=str(tmp_path / "evidence"))

    assert run.completed, run.error
    assert run.steps == 3  # rejected done -> real click -> verified done
    assert planner._calls >= 3
    rejected = [s for s in metrics.steps if s.action == "done" and not s.outcome.endswith("done")]
    assert any("done" in s.action for s in metrics.steps)


# ---------------------------------------------------------------------------
# 4. Invalid model output is fed back, not fatal
# ---------------------------------------------------------------------------
class ErrOnceThenScripted:
    def __init__(self, site):
        self.inner = ScriptedVisionPlanner(perceive=site.perceive)
        self._n = 0
        self.name = "err-once-test-double"

    def plan(self, goal, b64, screen, history, extra_hint=""):
        self._n += 1
        if self._n == 1:
            raise ActionError("x=99999 outside screen bounds 0..1280 (screen 1280x800)")
        return self.inner.plan(goal, b64, screen, history, extra_hint)

    def verify(self, goal, criteria, b64, screen):
        return self.inner.verify(goal, criteria, b64, screen)


def test_invalid_coordinates_rejected_and_recovered(tmp_path):
    site = FakeLoquaSite()
    planner = ErrOnceThenScripted(site)
    metrics = Metrics(max_steps=50)
    loop = ComputerUseLoop(
        browser=site, planner=planner, metrics=metrics,
        security=SecurityGate(SecurityPolicy()),
        config=LoopConfig(evidence_dir=str(tmp_path / "evidence")),
    )
    task = TaskSpec(id="t1", goal="Enter the airdrop flow: click Get Started.",
                    done_criteria="The landing hero is gone.")
    run = loop.run_task(task, run_dir=str(tmp_path / "evidence"))

    assert run.completed, run.error
    err_steps = [s for s in metrics.steps if s.outcome == "planner-error"]
    assert len(err_steps) == 1
    assert run.steps >= 3


# ---------------------------------------------------------------------------
# 5. Security: CAPTCHA and wallet halt the worker
# ---------------------------------------------------------------------------
def test_captcha_halts_worker(tmp_path):
    site = FakeLoquaSite()
    site.inject_captcha()
    planner = ScriptedVisionPlanner(perceive=site.perceive)
    metrics = Metrics(max_steps=50)
    loop = ComputerUseLoop(
        browser=site, planner=planner, metrics=metrics,
        security=SecurityGate(SecurityPolicy(stop_on_captcha=True)),
        config=LoopConfig(evidence_dir=str(tmp_path / "evidence")),
    )
    campaign = Campaign.load(LOQUA_CAMPAIGN)
    result = loop.run_campaign(campaign, run_dir=str(tmp_path / "evidence"))

    assert result.halted
    assert result.halted_at_task == "t1_open"
    assert "CAPTCHA" in result.halt_reason
    halt_files = [f for f in os.listdir(str(tmp_path / "evidence")) if "HALT_captcha" in f]
    assert halt_files  # evidence screenshot saved


def test_wallet_halts_worker_without_approval(tmp_path):
    site = FakeLoquaSite()
    site.inject_wallet()
    planner = ScriptedVisionPlanner(perceive=site.perceive)
    metrics = Metrics(max_steps=50)
    loop = ComputerUseLoop(
        browser=site, planner=planner, metrics=metrics,
        security=SecurityGate(SecurityPolicy(require_manual_approval_for_wallet=True)),
        config=LoopConfig(evidence_dir=str(tmp_path / "evidence")),
    )
    campaign = Campaign.load(LOQUA_CAMPAIGN)
    result = loop.run_campaign(campaign, run_dir=str(tmp_path / "evidence"))

    assert result.halted
    assert "wallet" in result.halt_reason.lower()


def test_wallet_with_human_approval_does_not_click_the_wallet(tmp_path):
    """Even with human approval, the agent's policy is to NOT interact
    with wallet screens — it reports the situation and stops the task
    (no halt of the whole campaign, no wallet click)."""
    site = FakeLoquaSite()
    site.inject_wallet()
    planner = ScriptedVisionPlanner(perceive=site.perceive)
    metrics = Metrics(max_steps=50)
    loop = ComputerUseLoop(
        browser=site, planner=planner, metrics=metrics,
        security=SecurityGate(SecurityPolicy(
            require_manual_approval_for_wallet=True,
            wallet_approver=lambda reason: True,
        )),
        config=LoopConfig(evidence_dir=str(tmp_path / "evidence")),
    )
    task = TaskSpec(id="t1", goal="Enter the airdrop flow: click Get Started.",
                    done_criteria="The landing hero is gone.")
    run = loop.run_task(task, run_dir=str(tmp_path / "evidence"))

    assert not run.completed
    assert run.halt_category is None          # not a security halt...
    assert "wallet" in (run.error or "").lower()  # ...but the task refused wallet interaction
    assert site._action_count == 0             # zero actions executed on the wallet screen


# ---------------------------------------------------------------------------
# 6. Step budgets
# ---------------------------------------------------------------------------
def test_campaign_step_budget_halts(tmp_path):
    site = FakeLoquaSite()
    planner = ScriptedVisionPlanner(perceive=site.perceive)
    metrics = Metrics(max_steps=6)
    loop = ComputerUseLoop(
        browser=site, planner=planner, metrics=metrics,
        security=SecurityGate(SecurityPolicy()),
        config=LoopConfig(max_steps=6, evidence_dir=str(tmp_path / "evidence")),
    )
    campaign = Campaign.load(LOQUA_CAMPAIGN)
    result = loop.run_campaign(campaign, run_dir=str(tmp_path / "evidence"))
    assert result.halted
    assert "budget" in result.halt_reason
