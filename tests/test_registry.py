"""Profile registry: single source of truth for browser profiles."""
import json

import pytest

from agentdrop.registry.registry import ProfileRegistry, RegistryError

REGISTRY = None  # loaded per-test from the repo's data file


def _load():
    return ProfileRegistry.load()


def test_loads_shipped_registry():
    reg = _load()
    assert {"hana", "execution", "discord"} <= set(reg.names())


def test_resolve_execution_profile():
    reg = _load()
    p = reg.resolve("execution")
    assert p.cdp_port == 9223
    assert p.path.endswith("browser-profiles/execution")
    assert "phantom" in p.accounts
    assert p.cdp_endpoint == "127.0.0.1:9223"


def test_unknown_profile_raises():
    reg = _load()
    with pytest.raises(RegistryError):
        reg.resolve("does-not-exist")


def test_cdp_liveness_offline():
    """Nothing listens on these ports in CI -> liveness must report
    False gracefully (this is exactly the drift the registry fixes)."""
    reg = _load()
    p = reg.resolve("execution")
    assert reg.cdp_alive(p, timeout=1.0) is False
    assert reg.cdp_target(p, timeout=1.0) is None


def test_status_report_shape():
    reg = _load()
    rows = reg.status_report()
    assert len(rows) == 3
    assert all({"profile", "cdp_alive", "cdp_endpoint"} <= set(r) for r in rows)


def test_invalid_registry_rejected(tmp_path):
    bad = tmp_path / "reg.json"
    bad.write_text(json.dumps({"profiles": {"x": {"path": "/x", "cdp_port": "nope"}}}))
    with pytest.raises(RegistryError):
        ProfileRegistry.load(str(bad))
    bad2 = tmp_path / "reg2.json"
    bad2.write_text(json.dumps({"profiles": {}}))
    with pytest.raises(RegistryError):
        ProfileRegistry.load(str(bad2))


def test_missing_registry_rejected(tmp_path):
    with pytest.raises(RegistryError):
        ProfileRegistry.load(str(tmp_path / "nope.json"))
