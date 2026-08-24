"""Worker configuration.

The worker profiles in ``hermes-config/profiles/`` carry the same YAML
blocks the Hermes runtime reads — this module extracts the
engine-relevant parts so the exact same file drives both Hermes and
the Python computer-use engine (single source of truth).
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional

import yaml

from .loop.security import SecurityGate, SecurityPolicy, guard_config_text


@dataclass
class EngineConfig:
    # model / planner
    model_provider: str = "cx/gpt-5.6-luna"
    vision_enabled: bool = True
    # loop
    max_steps: int = 50
    screenshot_interval: str = "always"
    verify_after_action: bool = True
    recovery_attempts: int = 3
    coordinate_system: str = "absolute"
    # profile
    profile_reference: str = "execution"
    cdp_port: Optional[int] = None
    # evidence
    evidence_dir: str = "runs"

    @classmethod
    def from_worker_yaml(cls, path: str) -> "EngineConfig":
        with open(path, "r", encoding="utf-8") as f:
            text = f.read()
        guard_config_text(text)
        raw = yaml.safe_load(text) or {}
        model = raw.get("model", {}) or {}
        cu = raw.get("computer_use", {}) or {}
        browser = raw.get("browser", {}) or {}
        return cls(
            model_provider=str(model.get("provider", cls.model_provider)),
            vision_enabled=bool(model.get("vision_enabled", True)),
            max_steps=int(cu.get("max_steps", 50)),
            screenshot_interval=str(cu.get("screenshot_interval", "always")),
            verify_after_action=bool(cu.get("verify_after_action", True)),
            recovery_attempts=int(cu.get("recovery_attempts", 3)),
            coordinate_system=str(cu.get("coordinate_system", "absolute")),
            profile_reference=str(browser.get("profile_reference", "execution")),
            cdp_port=browser.get("cdp_port"),
            evidence_dir=str(raw.get("evidence_dir", "runs")),
        )

    def security_policy(self) -> SecurityPolicy:
        return SecurityPolicy()  # strict defaults; worker yaml may loosen only explicitly

    def build_planner(self):
        """Instantiate the vision planner from env-driven settings."""
        from .vision.planner import AnthropicPlanner, OpenAICompatiblePlanner, PlannerError

        if os.environ.get("AGENTDROP_PLANNER", "").startswith("anthropic:"):
            model = os.environ["AGENTDROP_PLANNER"].split(":", 1)[1]
            return AnthropicPlanner(model=model)
        # default: OpenAI-compatible endpoint (works with OpenAI, HNCSEC
        # proxies, DeepSeek, local vLLM/Ollama — anything speaking the
        # Chat Completions protocol with image input)
        model = os.environ.get("AGENTDROP_VISION_MODEL", self.model_provider)
        base_url = os.environ.get("AGENTDROP_VISION_BASE_URL")
        api_key_env = os.environ.get("AGENTDROP_VISION_API_KEY_ENV", "OPENAI_API_KEY")
        return OpenAICompatiblePlanner(
            model=model, base_url=base_url, api_key_env=api_key_env
        )

    def build_security(self) -> SecurityGate:
        return SecurityGate(self.security_policy())
