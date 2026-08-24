"""agentdrop command-line interface.

    agentdrop registry status            # profile liveness from the registry
    agentdrop registry show execution
    agentdrop run --campaign <yaml> [--profile execution] [--url <base>]
    agentdrop poc                         # offline Loqua benchmark on the pixel site
"""
from __future__ import annotations

import argparse
import json
import sys


def _cmd_registry(args) -> int:
    from .registry.registry import ProfileRegistry, RegistryError

    try:
        reg = ProfileRegistry.load()
    except RegistryError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    if args.registry_cmd == "status":
        for row in reg.status_report():
            flag = "ONLINE " if row["cdp_alive"] else "OFFLINE"
            print(
                f"[{flag}] {row['profile']:<10} cdp={row['cdp_endpoint']:<14} "
                f"accounts={','.join(row['accounts']) or '-'}"
            )
        return 0
    if args.registry_cmd == "show":
        p = reg.resolve(args.name)
        print(json.dumps(
            {
                "name": p.name,
                "path": p.path,
                "cdp_port": p.cdp_port,
                "hermes_reference": p.hermes_reference,
                "status": p.status,
                "accounts": p.accounts,
                "alive": reg.cdp_alive(p),
            },
            indent=2,
        ))
        return 0
    return 2


def _cmd_run(args) -> int:
    from .worker.quest_worker import main as run_main
    argv = ["--campaign", args.campaign]
    if args.profile:
        argv += ["--profile", args.profile]
    if args.url:
        argv += ["--url", args.url]
    if args.evidence:
        argv += ["--evidence", args.evidence]
    if args.quiet:
        argv.append("--quiet")
    return run_main(argv)


def _cmd_poc(args) -> int:
    import os
    import time

    from fakesites.loqua.site import FakeLoquaSite
    from .campaigns.base import Campaign
    from .loop.computer_use import ComputerUseLoop, LoopConfig
    from .loop.metrics import Metrics
    from .loop.security import SecurityGate, SecurityPolicy
    from .vision.planner import ScriptedVisionPlanner

    repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    campaign = Campaign.load(os.path.join(repo, "agentdrop", "campaigns", "loqua.yaml"))
    evidence = os.path.join(repo, "poc", "evidence", time.strftime("%Y%m%d-%H%M%S"))

    site = FakeLoquaSite()
    if args.ui_change:
        site.arm_ui_change()
    planner = ScriptedVisionPlanner(perceive=site.perceive)
    metrics = Metrics(max_steps=50)
    loop = ComputerUseLoop(
        browser=site,
        planner=planner,
        metrics=metrics,
        security=SecurityGate(SecurityPolicy()),
        config=LoopConfig(evidence_dir=evidence),
    )
    result = loop.run_campaign(campaign, run_dir=evidence)
    report = metrics.report()
    report["campaign_result"] = result.to_dict()
    report["evidence_dir"] = evidence
    print(json.dumps(report, indent=2, default=str))
    return 0 if result.all_completed else 1


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="agentdrop")
    sub = p.add_subparsers(dest="cmd", required=True)

    reg = sub.add_parser("registry", help="profile registry")
    regsub = reg.add_subparsers(dest="registry_cmd", required=True)
    regsub.add_parser("status")
    show = regsub.add_parser("show")
    show.add_argument("name")

    run = sub.add_parser("run", help="run a campaign with worker-quests")
    run.add_argument("--campaign", required=True)
    run.add_argument("--profile")
    run.add_argument("--url")
    run.add_argument("--evidence")
    run.add_argument("--quiet", action="store_true")

    poc = sub.add_parser("poc", help="offline Loqua benchmark (pixel site)")
    poc.add_argument("--ui-change", action="store_true",
                     help="inject a mid-run UI mutation to prove recovery")

    args = p.parse_args(argv)
    if args.cmd == "registry":
        return _cmd_registry(args)
    if args.cmd == "run":
        return _cmd_run(args)
    if args.cmd == "poc":
        return _cmd_poc(args)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
