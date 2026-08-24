"""Recovery: what to do when an action produces no visible change.

One "episode" = one action plus its up-to-``max_action_retries`` inline
repeats (the "the mouse may have slipped / the page wasn't ready yet"
case). The loop retries the identical action within the episode; if the
episode still shows no change, recovery decides:

  reobserve — take a fresh screenshot and ask the vision model to
              re-read the screen and pick a DIFFERENT action. Bounded by
              ``max_recoveries`` per task. This is the level that absorbs
              real UI change: a moved button, a relabelled control, an
              unexpected overlay, an element below the fold.
  stuck     — recovery budget exhausted -> task fails with evidence.

Planner errors (malformed model output) get their own bounded budget.
"""
from __future__ import annotations

from typing import Optional

from ..vision import prompts


class RecoveryManager:
    def __init__(self, max_action_retries: int = 1, max_recoveries: int = 3):
        self.max_action_retries = max_action_retries
        self.max_recoveries = max_recoveries
        self.recoveries_used = 0
        self._planner_errors = 0
        self._hints: list = []

    # ------------------------------------------------------------------ hints
    def pending_hint(self) -> Optional[str]:
        if not self._hints:
            return None
        return self._hints.pop(0)

    def note_reobserve(self, last_action_summary: str, reason: str) -> None:
        base = prompts.RECOVERY_HINT.format(last_action=last_action_summary, n=2)
        self._hints.append(f"{base}\nLoop note: {reason}")

    # ------------------------------------------------------------------ flow
    def episode_failed(self, action) -> str:
        """An action and all its retries produced no change.
        Returns 'reobserve' (budget left) or 'stuck'."""
        if self.recoveries_used < self.max_recoveries:
            self.recoveries_used += 1
            return "reobserve"
        return "stuck"

    def ack_success(self) -> None:
        # Nothing to reset for re-observe accounting, but kept for symmetry
        # with per-action counters in case they are reintroduced.
        pass

    def note_planner_error(self) -> bool:
        """Record a planner parse failure. Returns False when we should give up."""
        self._planner_errors += 1
        return self._planner_errors <= self.max_recoveries

    def reset_planner_errors(self) -> None:
        self._planner_errors = 0
