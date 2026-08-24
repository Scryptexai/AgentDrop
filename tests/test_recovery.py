"""Recovery state machine: episode -> reobserve -> stuck."""
from agentdrop.loop.actions import parse_action
from agentdrop.loop.recovery import RecoveryManager


def _click(x=10, y=10):
    return parse_action({"type": "click", "x": x, "y": y}, 1280, 800)


def test_reobserve_then_stuck_sequence():
    r = RecoveryManager(max_action_retries=1, max_recoveries=3)
    assert r.episode_failed(_click()) == "reobserve"
    assert r.episode_failed(_click()) == "reobserve"
    assert r.episode_failed(_click()) == "reobserve"
    assert r.episode_failed(_click()) == "stuck"
    assert r.recoveries_used == 3


def test_different_actions_do_not_share_recovery_budget():
    r = RecoveryManager(max_recoveries=2)
    assert r.episode_failed(_click(1, 1)) == "reobserve"
    assert r.episode_failed(_click(2, 2)) == "reobserve"
    assert r.episode_failed(_click(3, 3)) == "stuck"


def test_planner_error_budget():
    r = RecoveryManager(max_recoveries=2)
    assert r.note_planner_error() is True
    assert r.note_planner_error() is True
    assert r.note_planner_error() is False
    r.reset_planner_errors()
    assert r.note_planner_error() is True


def test_reobserve_hint_is_delivered_once():
    r = RecoveryManager()
    r.note_reobserve("click @ 1,2", "no visible change")
    hint = r.pending_hint()
    assert hint is not None and "no visible change" in hint
    assert r.pending_hint() is None  # consumed
