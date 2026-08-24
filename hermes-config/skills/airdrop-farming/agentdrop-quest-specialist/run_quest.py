#!/usr/bin/env python3
"""Skill runner: agentdrop-quest-specialist (vision-first).

Invoked by Hermes (skill.yaml) or directly. Wires the worker profile
config -> profile registry -> CDP browser -> vision planner -> the
computer-use loop over the campaign.

Usage:
    python3 run_quest.py --campaign loqua --profile execution [--url https://...]
"""
import os
import sys

# Make the repo root importable regardless of where Hermes runs us from.
_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.abspath(os.path.join(_HERE, "..", "..", "..", ".."))
if os.path.isdir(os.path.join(_REPO, "agentdrop")):
    sys.path.insert(0, _REPO)

from agentdrop.worker import quest_worker  # noqa: E402


def main() -> int:
    import argparse

    p = argparse.ArgumentParser()
    p.add_argument("--campaign", default="loqua")
    p.add_argument("--profile", default=None)
    p.add_argument("--url", default=None)
    p.add_argument("--config", default=None,
                   help="worker config yaml (default: ~/.hermes/profiles/workers/worker-quests/config.yaml)")
    p.add_argument("--evidence", default=None)
    args = p.parse_args()

    campaign = args.campaign
    if os.path.isabs(campaign):
        campaign_path = campaign
    else:
        campaign_path = os.path.join(_REPO, "agentdrop", "campaigns", f"{campaign}.yaml")

    config_path = args.config or os.path.expanduser(
        "~/.hermes/profiles/workers/worker-quests/config.yaml"
    )
    if not os.path.exists(config_path):
        config_path = os.path.join(_REPO, "hermes-config", "profiles", "workers",
                                   "worker-quests", "config.yaml")

    return quest_worker.run(
        campaign_path,
        profile=args.profile,
        config_path=config_path,
        live_url=args.url,
        evidence=args.evidence,
    )


if __name__ == "__main__":
    raise SystemExit(main())
