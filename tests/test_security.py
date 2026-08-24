"""Security policy: CAPTCHA halt, wallet approval gate, key guard."""
import pytest

from agentdrop.loop.actions import Action
from agentdrop.loop.security import (
    SecurityGate,
    SecurityHalt,
    SecurityPolicy,
    guard_config_text,
    scan_for_keys,
)
from agentdrop.vision.planner import PageState, Plan

SEED_PHRASE = "abandon ability able about above absorb abstract absurd abuse access accident account"
PRIVATE_KEY_HEX = "0x4c0883a69102937d6231471b5dbb6204fe5129617082792ae468d01a3f362318"
PEM_KEY = "-----BEGIN PRIVATE KEY-----\nMIIEv...\n-----END PRIVATE KEY-----"


def test_scan_detects_seed_phrase():
    assert scan_for_keys(SEED_PHRASE) is not None


def test_scan_detects_private_key_hex():
    assert scan_for_keys(f"key={PRIVATE_KEY_HEX}") is not None


def test_scan_detects_pem():
    assert scan_for_keys(PEM_KEY) is not None


def test_scan_clean_text():
    assert scan_for_keys("agent@drop.test https://loqua.example Get Started") is None


def test_guard_config_text_refuses_seed_phrase():
    with pytest.raises(SecurityHalt):
        guard_config_text(f"secret: {SEED_PHRASE}")


def _plan(desc="a normal page", captcha=False, wallet=False, reasoning="agent reasoning"):
    return Plan(
        action=Action(type="click", x=10, y=10),
        page_state=PageState(description=desc, captcha_detected=captcha, wallet_prompt_detected=wallet),
        reasoning=reasoning,
    )


def test_captcha_halts():
    gate = SecurityGate(SecurityPolicy(stop_on_captcha=True))
    with pytest.raises(SecurityHalt) as ei:
        gate.check_plan(_plan(captcha=True))
    assert ei.value.category == "captcha"


def test_captcha_policy_can_be_disabled_for_research():
    gate = SecurityGate(SecurityPolicy(stop_on_captcha=False))
    gate.check_plan(_plan(captcha=True))  # no raise


def test_wallet_halts_without_approval():
    gate = SecurityGate(SecurityPolicy(require_manual_approval_for_wallet=True))
    with pytest.raises(SecurityHalt) as ei:
        gate.check_plan(_plan(wallet=True))
    assert ei.value.category == "wallet"


def test_wallet_halts_when_approver_says_no():
    gate = SecurityGate(SecurityPolicy(require_manual_approval_for_wallet=True, wallet_approver=lambda r: False))
    with pytest.raises(SecurityHalt):
        gate.check_plan(_plan(wallet=True))


def test_wallet_proceeds_when_human_approves():
    seen = []
    gate = SecurityGate(SecurityPolicy(
        require_manual_approval_for_wallet=True,
        wallet_approver=lambda r: (seen.append(r), True)[1],
    ))
    gate.check_plan(_plan(wallet=True, reasoning="tx modal visible"))
    assert seen == ["tx modal visible"]


def test_approver_exception_is_a_halt_not_an_approval():
    def bad_approver(reason):
        raise RuntimeError("approver crashed")
    gate = SecurityGate(SecurityPolicy(require_manual_approval_for_wallet=True, wallet_approver=bad_approver))
    with pytest.raises(SecurityHalt) as ei:
        gate.check_plan(_plan(wallet=True))
    assert ei.value.category == "wallet"


def test_normal_plan_passes():
    SecurityGate(SecurityPolicy()).check_plan(_plan())
