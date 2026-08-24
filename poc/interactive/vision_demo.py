#!/usr/bin/env python3
"""Interactive vision demo driver.

This is a manual stepping tool where a HUMAN (or any vision model) plays
the role of the planner. Per call it is given EXACTLY what a real vision
planner would receive:

  * a numbered PNG screenshot (view it with your own eyes)
  * URL + title (metadata — a human glances at the URL bar too)
  * the previous action and whether the screen CHANGED (pixel diff)

It is given NO ground truth: no element positions, no screen name, no
"what to click next". The operator decides coordinates by looking.

State persists between calls in .state.json so each step is one shell
command. Evidence (screenshots + transcript) lands in ./evidence.

Commands:
    python3 vision_demo.py init
    python3 vision_demo.py shot                 # new screenshot -> evidence/NNN.png
    python3 vision_demo.py click X Y
    python3 vision_demo.py type X Y "text"
    python3 vision_demo.py scroll [N]
    python3 vision_demo.py status               # url/title/last-action summary
"""
import base64
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from fakesites.loqua.site import FakeLoquaSite  # noqa: E402
from agentdrop.vision import verify as vverify  # noqa: E402
from agentdrop.loop.actions import Action, parse_action, execute_action  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
STATE = os.path.join(HERE, ".state.json")
EVIDENCE = os.path.join(HERE, "evidence")


def load():
    with open(STATE) as f:
        d = json.load(f)
    site = FakeLoquaSite.from_state(d["site"])
    return site, d


def save(site, d):
    d["site"] = site.to_state()
    with open(STATE, "w") as f:
        json.dump(d, f, indent=2)


def next_num(d):
    d["n"] = d.get("n", 0) + 1
    return d["n"]


def cmd_shot(d):
    site, _ = load()
    n = next_num(d)
    png = site.screenshot()
    path = os.path.join(EVIDENCE, f"{n:03d}.png")
    with open(path, "wb") as f:
        f.write(png)
    if "prev" in d and d["prev"]:
        changed = vverify.images_changed(base64.b64decode(d["prev"]), png)
        verdict = "CHANGED" if changed else "UNCHANGED"
    else:
        verdict = "first screenshot"
    d["prev"] = base64.b64encode(png).decode()
    save(site, d)
    print(f"step {n}: {verdict}")
    print(f"  url:    {site.get_url()}")
    print(f"  title:  {site.get_title()}")
    print(f"  screen: {site.screen_size[0]}x{site.screen_size[1]}")
    print(f"  image:  {path}")


def _act(d, action_dict, description):
    site, _ = load()
    n = next_num(d)
    before = site.screenshot()
    action = parse_action(action_dict, *site.screen_size)
    execute_action(site, action)
    after = site.screenshot()
    changed = vverify.images_changed(before, after)
    path = os.path.join(EVIDENCE, f"{n:03d}.png")
    with open(path, "wb") as f:
        f.write(after)
    d["last_action"] = description
    d["prev"] = base64.b64encode(after).decode()
    save(site, d)
    print(f"step {n}: {description} -> {'CHANGED' if changed else 'UNCHANGED'}")
    print(f"  url:    {site.get_url()}")
    print(f"  screen: {site.screen_size[0]}x{site.screen_size[1]}")
    print(f"  image:  {path}")


def main():
    os.makedirs(EVIDENCE, exist_ok=True)
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        return 1
    cmd = args[0]

    if cmd == "init":
        site = FakeLoquaSite()
        d = {"n": 0, "prev": None, "last_action": None}
        save(site, d)
        print("initialized: landing page loaded")
        return 0

    if not os.path.exists(STATE):
        print("run `init` first")
        return 1
    with open(STATE) as f:
        d = json.load(f)

    if cmd == "shot":
        cmd_shot(d)
    elif cmd == "status":
        site, _ = load()
        print(json.dumps({
            "last_action": d.get("last_action"),
            "url": site.get_url(),
            "title": site.get_title(),
            "screen": list(site.screen_size),
        }, indent=2))
    elif cmd == "click" and len(args) == 3:
        _act(d, {"type": "click", "x": int(args[1]), "y": int(args[2])},
             f"click @ {args[1]},{args[2]}")
    elif cmd == "type" and len(args) == 4:
        _act(d, {"type": "type", "x": int(args[1]), "y": int(args[2]), "value": args[3]},
             f"type {args[3]!r} at {args[1]},{args[2]}")
    elif cmd == "scroll":
        n = int(args[1]) if len(args) > 1 else 3
        _act(d, {"type": "scroll", "direction": "down", "amount": n,
                 "x": 640, "y": 400}, f"scroll down x{n}")
    else:
        print(__doc__)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
