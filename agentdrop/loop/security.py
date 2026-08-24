"""Security policy for the computer-use loop.

Hard guarantees (configurable in the worker profile, NOT in skills):
  stop_on_captcha                     -> worker halts, saves evidence, exits
  require_manual_approval_for_wallet  -> wallet/tx screens block until a
                                         human approves (or the worker halts)
  never_store_private_keys            -> config & log guard: key-like strings
                                         are rejected at load time
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable, Optional

# Crude but effective private-key/seed-phrase detector for config & logs.
_KEY_PATTERNS = [
    re.compile(r"-----BEGIN (?:RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----"),
    re.compile(r"\b[A-HJ-KM-NP-Z2-9]{24,}\b"),                      # 24+ bech32/base58 words
    re.compile(r"\b(\w{2,20} ){11,}\w{2,20}\b", re.I),              # 12+ word seed phrase
    re.compile(r"\b0x[0-9a-fA-F]{64}\b"),                           # raw 32-byte key hex
]


class SecurityHalt(Exception):
    """Raised to stop the worker immediately for a security reason."""

    def __init__(self, reason: str, category: str):
        self.reason = reason
        self.category = category  # "captcha" | "wallet" | "policy"
        super().__init__(f"[{category}] {reason}")


class WalletApprovalRequired(Exception):
    """A wallet/tx screen was detected; a human decision is needed."""

    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(reason)


def scan_for_keys(text: str) -> Optional[str]:
    """Return the matched pattern name if key-like material is found."""
    for i, pat in enumerate(_KEY_PATTERNS):
        if pat.search(text):
            return f"pattern #{i}"
    return None


def guard_config_text(config_text: str) -> None:
    """Refuse configs that embed private keys / seed phrases."""
    found = scan_for_keys(config_text)
    if found:
        raise SecurityHalt(
            f"config contains private-key-like material ({found}); "
            "never_store_private_keys policy forbids it",
            "policy",
        )


@dataclass
class SecurityPolicy:
    stop_on_captcha: bool = True
    require_manual_approval_for_wallet: bool = True
    never_store_private_keys: bool = True
    # Wallet approval callback: (reason) -> bool. Defaults to "refuse"
    # so a headless run can never silently sign a transaction.
    wallet_approver: Optional[Callable[[str], bool]] = None

    @classmethod
    def from_dict(cls, data: dict) -> "SecurityPolicy":
        return cls(
            stop_on_captcha=bool(data.get("stop_on_captcha", True)),
            require_manual_approval_for_wallet=bool(
                data.get("require_manual_approval_for_wallet", True)
            ),
            never_store_private_keys=bool(data.get("never_store_private_keys", True)),
        )


class SecurityGate:
    """Checks each Plan before it executes. Raises SecurityHalt to stop."""

    def __init__(self, policy: SecurityPolicy):
        self.policy = policy

    def check_plan(self, plan) -> None:
        if self.policy.stop_on_captcha and plan.page_state.captcha_detected:
            raise SecurityHalt(
                "vision model reports a CAPTCHA on screen; stopping per stop_on_captcha",
                "captcha",
            )
        if (
            self.policy.require_manual_approval_for_wallet
            and plan.page_state.wallet_prompt_detected
        ):
            approved = False
            if self.policy.wallet_approver is not None:
                try:
                    approved = bool(self.policy.wallet_approver(plan.reasoning))
                except Exception as e:  # an approver bug must not become an approval
                    raise SecurityHalt(f"wallet approver failed: {e}", "wallet") from e
            if not approved:
                raise SecurityHalt(
                    "wallet/transaction screen detected; no manual approval given",
                    "wallet",
                )

    def check_text(self, text: str, label: str = "config") -> None:
        if not self.policy.never_store_private_keys:
            return
        found = scan_for_keys(text)
        if found:
            raise SecurityHalt(
                f"{label} contains private-key-like material ({found})", "policy"
            )
