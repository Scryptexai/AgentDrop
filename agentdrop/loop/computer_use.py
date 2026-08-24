"""The computer-use loop: screenshot -> observe -> reason -> act -> verify.

This module contains NO knowledge of DOM, selectors, or page structure.
It only moves pixels and records what the vision model claims to see.
"""
from __future__ import annotations

import base64
import os
from dataclasses import dataclass, field
from typing import List, Optional

from .actions import Action, ActionError, execute_action
from .metrics import Metrics
from .recovery import RecoveryManager
from .security import SecurityGate, SecurityHalt
from ..vision import verify as vverify
from ..vision.planner import PlannerError

STEP_LIMIT_PER_TASK_DEFAULT = 14


@dataclass
class LoopConfig:
    max_steps: int = 50                 # hard cap for the whole campaign
    max_steps_per_task: int = STEP_LIMIT_PER_TASK_DEFAULT
    max_action_retries: int = 1         # inline repeats of the identical action within one episode
    max_recoveries: int = 3             # re-observe & adapt attempts per task
    verify_after_action: bool = True
    verify_completion: bool = True
    change_threshold: float = vverify.CHANGE_THRESHOLD
    evidence_dir: Optional[str] = None


@dataclass
class TaskRun:
    task_id: str
    completed: bool
    steps: int
    recoveries: int
    error: Optional[str] = None
    halt_category: Optional[str] = None


@dataclass
class CampaignResult:
    campaign: str
    profile: str
    tasks: List[TaskRun] = field(default_factory=list)
    halted: bool = False
    halt_reason: Optional[str] = None
    halted_at_task: Optional[str] = None

    @property
    def all_completed(self) -> bool:
        return not self.halted and all(t.completed for t in self.tasks)

    def to_dict(self) -> dict:
        return {
            "campaign": self.campaign,
            "profile": self.profile,
            "halted": self.halted,
            "halt_reason": self.halt_reason,
            "halted_at_task": self.halted_at_task,
            "all_completed": self.all_completed,
            "tasks": [
                {
                    "task_id": t.task_id,
                    "completed": t.completed,
                    "steps": t.steps,
                    "recoveries": t.recoveries,
                    "error": t.error,
                    "halt_category": t.halt_category,
                }
                for t in self.tasks
            ],
        }


class ComputerUseLoop:
    """Runs natural-language tasks against any BrowserLike (CDP or fake)."""

    def __init__(
        self,
        browser,
        planner,
        metrics: Metrics,
        security: SecurityGate,
        config: Optional[LoopConfig] = None,
    ):
        self.browser = browser
        self.planner = planner
        self.metrics = metrics
        self.security = security
        self.config = config or LoopConfig()

    # ------------------------------------------------------------------ evidence
    def _evidence(self, run_dir: Optional[str], name: str, png: bytes) -> str:
        if not run_dir:
            return ""
        os.makedirs(run_dir, exist_ok=True)
        path = os.path.join(run_dir, name)
        with open(path, "wb") as f:
            f.write(png)
        return path

    # ------------------------------------------------------------------ one task
    def run_task(self, task, run_dir: Optional[str] = None) -> TaskRun:
        recovery = RecoveryManager(
            max_action_retries=self.config.max_action_retries,
            max_recoveries=self.config.max_recoveries,
        )
        history: List[dict] = []
        run = TaskRun(task.id, False, 0, 0)
        screen = self.browser.screen_size

        while self.metrics.total_steps < self.config.max_steps:
            if run.steps >= self.config.max_steps_per_task:
                run.error = f"exceeded {self.config.max_steps_per_task} steps per task"
                break

            # 1. CAPTURE ----------------------------------------------------
            shot = self.browser.screenshot()
            self._evidence(run_dir, f"{task.id}_{run.steps:02d}_before.png", shot)
            shot_b64 = base64.b64encode(shot).decode("ascii")
            step_no = self.metrics.total_steps + 1

            # 2. OBSERVE + 3. REASON ----------------------------------------
            hint = recovery.pending_hint()
            try:
                plan = self.planner.plan(
                    task.goal, shot_b64, screen, history, extra_hint=hint or ""
                )
                recovery.reset_planner_errors()
            except (PlannerError, ActionError) as e:
                self.metrics.record(
                    step_no, task.id, "planner-error", "", "", None, "planner-error"
                )
                run.steps += 1
                if not recovery.note_planner_error():
                    run.error = f"planner failed repeatedly: {e}"
                    break
                continue

            # 3b. SECURITY ----------------------------------------------------
            try:
                self.security.check_plan(plan)
            except SecurityHalt as e:
                shot_after = self.browser.screenshot()
                self._evidence(run_dir, f"{task.id}_{run.steps:02d}_HALT_{e.category}.png", shot_after)
                self.metrics.record(
                    step_no, task.id, plan.action.summary(), plan.reasoning,
                    plan.page_state.description, None, "security-halt",
                )
                run.steps += 1
                run.halt_category = e.category
                run.error = str(e)
                run.recoveries = recovery.recoveries_used
                return run  # caller halts the whole campaign

            action = plan.action

            # 3c. TERMINAL actions -------------------------------------------
            if action.type == "done":
                complete, evidence = True, "planner reports done"
                if self.config.verify_completion:
                    complete, evidence = self.planner.verify(
                        task.goal, task.done_criteria, shot_b64, screen
                    )
                self.metrics.record(
                    step_no, task.id, "done", plan.reasoning,
                    plan.page_state.description, None, "done" if complete else "ok",
                )
                run.steps += 1
                if complete:
                    run.completed = True
                    run.recoveries = recovery.recoveries_used
                    return run
                history.append(
                    {
                        "step": step_no,
                        "action": "done (rejected by verifier)",
                        "changed": None,
                        "note": f"verifier says NOT complete: {evidence}",
                    }
                )
                recovery.note_reobserve("done", f"verifier: {evidence}")
                continue
            if action.type == "error":
                self.metrics.record(
                    step_no, task.id, action.summary(), plan.reasoning,
                    plan.page_state.description, None, "error",
                )
                run.error = action.value or "agent reported error"
                run.steps += 1
                run.recoveries = recovery.recoveries_used
                break

            # 4. EXECUTE + 5. VERIFY ---------------------------------------------
            # One "episode" = the action plus up to max_action_retries inline
            # repeats (mouse slipped / page not ready). Each attempt is
            # verified against the previous screenshot; the first attempt
            # alone decides first-try click accuracy.
            try:
                if self.config.verify_after_action and (
                    action.needs_change or action.is_soft_visual
                ):
                    attempts = self.config.max_action_retries + 1
                    prev = shot
                    changed = False
                    attempt_outcomes: List[bool] = []
                    for _attempt in range(attempts):
                        execute_action(self.browser, action)
                        shot_after = self.browser.screenshot()
                        changed = vverify.images_changed(
                            prev, shot_after, threshold=self.config.change_threshold
                        )
                        attempt_outcomes.append(changed)
                        prev = shot_after
                        self._evidence(run_dir, f"{task.id}_{run.steps:02d}_after_a{len(attempt_outcomes)}.png", shot_after)
                        if changed:
                            break

                    if changed:
                        first_try_ok = attempt_outcomes[0]
                        if action.type in ("click", "double_click", "right_click") and action.point:
                            self.metrics.record_click_attempt(
                                task.id, action.x, action.y, first_try_ok
                            )
                        label = action.summary()
                        if len(attempt_outcomes) > 1:
                            label += f" ({len(attempt_outcomes)} attempts)"
                        self.metrics.record(
                            step_no, task.id, label, plan.reasoning,
                            plan.page_state.description, True, "ok",
                        )
                        run.steps += 1
                        history.append(
                            {"step": step_no, "action": label, "changed": True}
                        )
                        continue

                    # ---- whole episode produced no change: escalate -------
                    if action.type in ("click", "double_click", "right_click") and action.point:
                        self.metrics.record_click_attempt(task.id, action.x, action.y, False)
                    verdict = recovery.episode_failed(action)
                    label = action.summary()
                    if len(attempt_outcomes) > 1:
                        label += f" ({len(attempt_outcomes)} attempts)"
                    self.metrics.record(
                        step_no, task.id, label, plan.reasoning,
                        plan.page_state.description, False, "no-change",
                    )
                    run.steps += 1
                    if verdict == "reobserve":
                        history.append(
                            {
                                "step": step_no,
                                "action": label,
                                "changed": False,
                                "note": "no visible change — re-observe and adapt",
                            }
                        )
                        recovery.note_reobserve(label, "no visible change after action")
                        continue
                    run.error = (
                        f"stuck: {label} produced no change and the recovery "
                        f"budget ({self.config.max_recoveries}) is exhausted"
                    )
                    break
                else:
                    execute_action(self.browser, action)

            except ActionError as e:
                self.metrics.record(
                    step_no, task.id, f"{action.summary()} (invalid)", plan.reasoning,
                    plan.page_state.description, None, "planner-error",
                )
                run.steps += 1
                history.append(
                    {"step": step_no, "action": action.summary(), "changed": None,
                     "note": f"REJECTED: {e}"}
                )
                continue

            # non-visual action (wait) or verification disabled
            self._record_and_continue(step_no, task, run, history, plan, None)

        if not run.completed and run.error is None:
            run.error = "step budget exhausted"
        run.recoveries = recovery.recoveries_used
        return run

    def _record_and_continue(self, step_no, task, run, history, plan, changed) -> None:
        self.metrics.record(
            step_no, task.id, plan.action.summary(), plan.reasoning,
            plan.page_state.description, changed, "ok",
        )
        run.steps += 1
        history.append(
            {"step": step_no, "action": plan.action.summary(), "changed": changed}
        )

    # ------------------------------------------------------------------ campaign
    def run_campaign(self, campaign, run_dir: Optional[str] = None) -> CampaignResult:
        result = CampaignResult(campaign=campaign.id, profile=campaign.profile)
        for task in campaign.tasks:
            if self.metrics.total_steps >= self.config.max_steps:
                result.halted = True
                result.halt_reason = "campaign step budget exhausted"
                result.halted_at_task = task.id
                break
            run = self.run_task(task, run_dir=run_dir)
            self.metrics.record_task(
                task.id, run.completed, run.steps, run.recoveries, run.error
            )
            result.tasks.append(
                TaskRun(task.id, run.completed, run.steps, run.recoveries, run.error, run.halt_category)
            )
            if run.halt_category:
                result.halted = True
                result.halt_reason = run.error
                result.halted_at_task = task.id
                break
        return result
