"""Campaigns: natural-language task sequences.

A campaign is a list of tasks with GOALS, not selectors. The vision
agent reads "open the Loqua airdrop and click Get Started" and finds
the button on the screenshot itself. If the site moves the button,
the task text does not need to change — that is the whole point.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

import yaml


@dataclass
class TaskSpec:
    id: str
    goal: str                     # natural language, shown to the vision model
    done_criteria: str            # shown to the completion verifier
    url: Optional[str] = None     # optional start URL hint (metadata only)
    category: str = "quest"       # "wallet" tasks get the approval gate
    max_steps: Optional[int] = None


@dataclass
class Campaign:
    id: str
    name: str
    profile: str                  # profile registry name, e.g. "execution"
    tasks: List[TaskSpec] = field(default_factory=list)
    notes: str = ""

    @classmethod
    def load(cls, path: str) -> "Campaign":
        with open(path, "r", encoding="utf-8") as f:
            text = f.read()
        # never_store_private_keys: refuse key-like material in campaign files
        from ..loop.security import guard_config_text
        guard_config_text(text)
        raw = yaml.safe_load(text)
        tasks = [
            TaskSpec(
                id=t["id"],
                goal=t["goal"],
                done_criteria=t.get("done_criteria", t["goal"]),
                url=t.get("url"),
                category=t.get("category", "quest"),
                max_steps=t.get("max_steps"),
            )
            for t in raw.get("tasks", [])
        ]
        return cls(
            id=raw["id"],
            name=raw.get("name", raw["id"]),
            profile=raw.get("profile", "execution"),
            tasks=tasks,
            notes=raw.get("notes", ""),
        )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "profile": self.profile,
            "tasks": [
                {
                    "id": t.id,
                    "goal": t.goal,
                    "done_criteria": t.done_criteria,
                    "url": t.url,
                    "category": t.category,
                }
                for t in self.tasks
            ],
        }
