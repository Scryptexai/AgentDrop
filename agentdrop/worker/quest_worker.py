"""worker-quests: the vision-first worker entry point.

Wires: worker config -> profile registry -> CDP browser (or offline
pixel site) -> vision planner -> computer-use loop -> campaign.

Usage:
    agentdrop run --campaign agentdrop/campaigns/loqua.yaml --profile execution
    AGENTDROP_FAKE_SITE=1 agentdrop run --campaign ...     # offline PoC
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from typing import Optional

from ..campaigns.base import Campaign
from ..cdp.browser import BrowserSession
from ..config import EngineConfig
from ..loop.computer_use import ComputerUseLoop, LoopConfig
from ..loop.metrics import Metrics
from ..registry.registry import ProfileRegistry
from ..vision.planner import ScriptedVisionPlanner, PlannerError

DEFAULT_WORKER_CONFIG = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "hermes-config",
    "profiles",
    "workers",
    "worker-quests",
    "config.yaml",
)


def _offline_browser():
    """The pixel-rendered Loqua replica — same interface, zero network."""
    from fakesites.loqua.site import FakeLoquaSite
    return FakeLoquaSite()


def _offline_planner(browser):
    return ScriptedVisionPlanner(perceive=browser.perceive)


def build_browser(config: EngineConfig, profile_name: str, fake: bool):
    if fake:
        return _offline_browser()
    registry = ProfileRegistry.load()
    profile = registry.resolve(profile_name or config.profile_reference)
    if not registry.cdp_alive(profile):
        raise SystemExit(
            f"CDP endpoint for profile {profile.name!r} ({profile.cdp_endpoint}) is OFFLINE.\n"
            "Start it with: scripts/start-browser.sh " + profile.name
        )
    return BrowserSession.connect(
        host=profile.cdp_host, port=profile.cdp_port, prefer_url=None
    )


def run(
    campaign_path: str,
    profile: Optional[str] = None,
    config_path: Optional[str] = None,
    live_url: Optional[str] = None,
    fake: Optional[bool] = None,
    evidence: Optional[str] = None,
    verbose: bool = True,
) -> int:
    config = EngineConfig.from_worker_yaml(config_path or os.environ.get("AGENTDROP_WORKER_CONFIG", DEFAULT_WORKER_CONFIG))
    if fake is None:
        fake = bool(os.environ.get("AGENTDROP_FAKE_SITE"))

    campaign = Campaign.load(campaign_path)
    if live_url:
        for t in campaign.tasks:
            if t.url:
                t.url = t.url.replace("{LIVE_URL}", live_url)
        campaign.notes = f"live_url={live_url}"

    browser = build_browser(config, profile, fake)
    planner = _offline_planner(browser) if fake else config.build_planner()
    metrics = Metrics(max_steps=config.max_steps)
    loop = ComputerUseLoop(
        browser=browser,
        planner=planner,
        metrics=metrics,
        security=config.build_security(),
        config=LoopConfig(
            max_steps=config.max_steps,
            verify_after_action=config.verify_after_action,
            max_recoveries=config.recovery_attempts,
            evidence_dir=evidence,
        ),
    )

    if verbose:
        print(f"[worker-quests] campaign={campaign.id} profile={campaign.profile} "
              f"planner={planner.name} fake_site={fake}")
        print(f"[worker-quests] tasks: {', '.join(t.id for t in campaign.tasks)}")

    result = loop.run_campaign(campaign, run_dir=evidence)

    report = metrics.report()
    report["campaign_result"] = result.to_dict()
    print("\n" + json.dumps(report, indent=2, default=str))

    if evidence:
        with open(os.path.join(evidence, "report.json"), "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, default=str)
        metrics.dump_jsonl(os.path.join(evidence, "steps.jsonl"))

    browser.close()
    if result.halted:
        print(f"\n[worker-quests] HALTED at {result.halted_at_task}: {result.halt_reason}", file=sys.stderr)
        return 2
    if result.all_completed:
        print("\n[worker-quests] all tasks completed")
        return 0
    print("\n[worker-quests] campaign incomplete", file=sys.stderr)
    return 1


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="agentdrop-run", description=__doc__)
    p.add_argument("--campaign", required=True)
    p.add_argument("--profile", default=None)
    p.add_argument("--config", default=None, help="worker config yaml")
    p.add_argument("--url", default=None, help="live campaign base URL (replaces {LIVE_URL})")
    p.add_argument("--fake-site", action="store_true", default=None)
    p.add_argument("--evidence", default=None)
    p.add_argument("--quiet", action="store_true")
    args = p.parse_args(argv)
    return run(
        args.campaign,
        profile=args.profile,
        config_path=args.config,
        live_url=args.url,
        fake=args.fake_site if args.fake_site else None,
        evidence=args.evidence,
        verbose=not args.quiet,
    )


if __name__ == "__main__":
    raise SystemExit(main())
