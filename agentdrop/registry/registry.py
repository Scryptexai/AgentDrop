"""Profile Registry — the single source of truth for browser profiles.

Before this registry, workers hardcoded profile paths and CDP ports,
which drifted apart (offline ports, duplicated profiles). Every worker
now resolves ``profile name -> (path, cdp_port, accounts)`` from one
file: ``data/profile_registry.json`` (override the location with the
``AGENTDROP_PROFILE_REGISTRY`` environment variable).
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import requests

DEFAULT_REGISTRY_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "data",
    "profile_registry.json",
)


@dataclass
class Profile:
    name: str
    path: str
    cdp_port: int
    hermes_reference: str = ""
    status: str = "ready"
    accounts: List[str] = field(default_factory=list)
    notes: str = ""

    @property
    def cdp_host(self) -> str:
        return os.environ.get("AGENTDROP_CDP_HOST", "127.0.0.1")

    @property
    def cdp_endpoint(self) -> str:
        return f"{self.cdp_host}:{self.cdp_port}"


class RegistryError(Exception):
    pass


class ProfileRegistry:
    def __init__(self, profiles: Dict[str, Profile], source: str):
        self._profiles = profiles
        self.source = source

    # ------------------------------------------------------------------ load
    @classmethod
    def load(cls, path: Optional[str] = None) -> "ProfileRegistry":
        path = path or os.environ.get("AGENTDROP_PROFILE_REGISTRY", DEFAULT_REGISTRY_PATH)
        if not os.path.exists(path):
            raise RegistryError(f"profile registry not found: {path}")
        with open(path, "r", encoding="utf-8") as f:
            raw = json.load(f)
        profiles: Dict[str, Profile] = {}
        for name, data in (raw.get("profiles") or {}).items():
            port = data.get("cdp_port")
            if not isinstance(port, int) or not (1 <= port <= 65535):
                raise RegistryError(f"profile {name!r}: invalid cdp_port {port!r}")
            if not data.get("path"):
                raise RegistryError(f"profile {name!r}: missing path")
            profiles[name] = Profile(
                name=name,
                path=data["path"],
                cdp_port=port,
                hermes_reference=data.get("hermes_reference", ""),
                status=data.get("status", "unknown"),
                accounts=list(data.get("accounts", [])),
                notes=data.get("notes", ""),
            )
        if not profiles:
            raise RegistryError(f"no profiles in {path}")
        return cls(profiles, path)

    # ------------------------------------------------------------------ query
    def names(self) -> List[str]:
        return sorted(self._profiles)

    def resolve(self, name: str) -> Profile:
        try:
            return self._profiles[name]
        except KeyError:
            raise RegistryError(
                f"unknown profile {name!r}; known: {', '.join(self.names())}"
            ) from None

    def all(self) -> List[Profile]:
        return [self._profiles[n] for n in self.names()]

    def to_dict(self) -> dict:
        return {
            "source": self.source,
            "profiles": {
                p.name: {
                    "path": p.path,
                    "cdp_port": p.cdp_port,
                    "hermes_reference": p.hermes_reference,
                    "status": p.status,
                    "accounts": p.accounts,
                }
                for p in self.all()
            },
        }

    # ------------------------------------------------------------------ liveness
    def cdp_alive(self, profile: Profile, timeout: float = 3.0) -> bool:
        """True if a Chrome with a CDP endpoint answers on the profile port."""
        try:
            r = requests.get(
                f"http://{profile.cdp_endpoint}/json/version", timeout=timeout
            )
            return r.status_code == 200
        except requests.RequestException:
            return False

    def cdp_target(self, profile: Profile, timeout: float = 3.0) -> Optional[str]:
        """webSocketDebuggerUrl of the first page target, or None."""
        try:
            targets = requests.get(
                f"http://{profile.cdp_endpoint}/json/list", timeout=timeout
            ).json()
        except (requests.RequestException, ValueError):
            return None
        for t in targets:
            if t.get("type") == "page" and t.get("webSocketDebuggerUrl"):
                return t["webSocketDebuggerUrl"]
        return None

    def status_report(self) -> List[dict]:
        out = []
        for p in self.all():
            alive = self.cdp_alive(p)
            out.append(
                {
                    "profile": p.name,
                    "cdp_endpoint": p.cdp_endpoint,
                    "cdp_alive": alive,
                    "registered_status": p.status,
                    "path": p.path,
                    "accounts": p.accounts,
                }
            )
        return out
