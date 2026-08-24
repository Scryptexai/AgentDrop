"""Step logging and validation metrics.

The benchmark (docs/VALIDATION.md) is measured here:
  click accuracy        = first-attempt clicks that produced a verified
                          state change / all first-attempt clicks
  task completion       = completed tasks / all tasks
  UI-change recovery    = task still completes after a mid-run mutation
  screen understanding  = planner descriptions contain the expected keywords
  step count            = total steps for the whole campaign
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional

TARGETS = {
    "click_accuracy_min": 0.90,
    "task_completion_min": 1.0,
    "max_steps": 50,
    "recovery_required": True,
    "understanding_required": True,
}


@dataclass
class StepRecord:
    step: int
    task_id: str
    action: str
    reasoning: str
    page_description: str
    changed: Optional[bool]      # None for non-visual steps
    outcome: str                 # "ok" | "no-change" | "planner-error" | "security-halt" | "done" | "error"
    ts: float = field(default_factory=time.time)
    retry_of: Optional[int] = None  # step this retry belongs to, if any

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class TaskResult:
    task_id: str
    completed: bool
    steps: int
    recoveries: int
    error: Optional[str] = None
    evidence: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


class Metrics:
    def __init__(self, max_steps: int = 50):
        self.max_steps = max_steps
        self.steps: List[StepRecord] = []
        self.tasks: List[TaskResult] = []
        self._click_attempts: Dict[str, bool] = {}  # key -> first attempt succeeded
        self.started = time.time()

    # ------------------------------------------------------------------ record
    def record(
        self,
        step: int,
        task_id: str,
        action: str,
        reasoning: str,
        page_description: str,
        changed: Optional[bool],
        outcome: str,
        retry_of: Optional[int] = None,
    ) -> StepRecord:
        rec = StepRecord(
            step=step,
            task_id=task_id,
            action=action,
            reasoning=reasoning,
            page_description=page_description,
            changed=changed,
            outcome=outcome,
            retry_of=retry_of,
        )
        self.steps.append(rec)
        return rec

    def record_click_attempt(self, task_id: str, x: int, y: int, succeeded: bool) -> None:
        """First-attempt click accuracy: keyed by (task, point); later
        retries of the same point do not count (they are recovery)."""
        key = f"{task_id}:{x}:{y}"
        if key not in self._click_attempts:
            self._click_attempts[key] = succeeded

    def record_task(self, task_id: str, completed: bool, steps: int, recoveries: int,
                    error: Optional[str] = None, evidence: str = "") -> TaskResult:
        res = TaskResult(task_id, completed, steps, recoveries, error, evidence)
        self.tasks.append(res)
        return res

    # ------------------------------------------------------------------ report
    @property
    def total_steps(self) -> int:
        return len(self.steps)

    @property
    def click_accuracy(self) -> Optional[float]:
        if not self._click_attempts:
            return None
        ok = sum(1 for v in self._click_attempts.values() if v)
        return ok / len(self._click_attempts)

    @property
    def tasks_completed(self) -> int:
        return sum(1 for t in self.tasks if t.completed)

    @property
    def task_completion(self) -> float:
        if not self.tasks:
            return 0.0
        return self.tasks_completed / len(self.tasks)

    @property
    def recovery_events(self) -> int:
        return sum(t.recoveries for t in self.tasks)

    def descriptions(self) -> List[str]:
        return [s.page_description for s in self.steps if s.page_description]

    def report(self) -> dict:
        acc = self.click_accuracy
        completion = self.task_completion
        return {
            "targets": TARGETS,
            "total_steps": self.total_steps,
            "click_accuracy": acc,
            "click_accuracy_pass": acc is not None and acc >= TARGETS["click_accuracy_min"],
            "tasks_total": len(self.tasks),
            "tasks_completed": sum(1 for t in self.tasks if t.completed),
            "task_completion": completion,
            "task_completion_pass": completion >= TARGETS["task_completion_min"],
            "steps_under_max": self.total_steps < TARGETS["max_steps"],
            "recovery_events": self.recovery_events,
            "duration_s": round(time.time() - self.started, 2),
            "tasks": [t.to_dict() for t in self.tasks],
        }

    def dump_jsonl(self, path: str) -> None:
        with open(path, "w", encoding="utf-8") as f:
            for s in self.steps:
                f.write(json.dumps(s.to_dict()) + "\n")
