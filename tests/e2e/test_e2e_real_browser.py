"""Real-browser E2E: the Loqua benchmark against a real Chromium + real
vision model. Skips (staying green) when no browser or no API key is
available — e.g. in this sandbox or plain CI.
"""
import glob
import os
import shutil
import subprocess
import threading
import time
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

import pytest

pytestmark = pytest.mark.e2e

SITE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "loqua_site")
CAMPAIGN = os.path.join(os.path.dirname(os.path.dirname(SITE_DIR)), "agentdrop", "campaigns", "loqua.yaml")


def _find_playwright_chromium():
    cache = os.path.expanduser("~/.cache/ms-playwright")
    if not os.path.isdir(cache):
        return None
    for pattern in ("chromium-*/chrome-linux*/chrome", "chromium-*/chrome-linux/headless_shell"):
        hits = glob.glob(os.path.join(cache, pattern))
        if hits:
            return sorted(hits)[-1]
    return None


def _free_port():
    import socket
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def _cdp_alive(host, port, timeout=2.0):
    import requests
    try:
        return requests.get(f"http://{host}:{port}/json/version", timeout=timeout).status_code == 200
    except Exception:
        return False


@pytest.fixture(scope="module")
def cdp_port():
    """Yield a CDP port with a live page, or skip the module."""
    # 1. explicit endpoint
    explicit = os.environ.get("AGENTDROP_E2E_CDP")
    if explicit:
        host, _, port = explicit.partition(":")
        if _cdp_alive(host, int(port or 9223)):
            yield int(port or 9223)
            return
        pytest.skip(f"AGENTDROP_E2E_CDP={explicit} is not alive")

    # 2. Playwright-managed Chromium
    exe = _find_playwright_chromium()
    if exe is None:
        pytest.skip("no browser: set AGENTDROP_E2E_CDP or `playwright install chromium`")
    port = _free_port()
    user_data = "/tmp/agentdrop-e2e-profile"
    shutil.rmtree(user_data, ignore_errors=True)
    proc = subprocess.Popen(
        [
            exe, "--headless=new", f"--remote-debugging-port={port}",
            f"--user-data-dir={user_data}", "--no-first-run", "--no-default-browser-check",
            "--window-size=1280,800", "about:blank",
        ],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    try:
        for _ in range(50):
            if _cdp_alive("127.0.0.1", port):
                break
            time.sleep(0.2)
        else:
            pytest.skip("chromium did not open a CDP endpoint in time")
        yield port
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()


@pytest.fixture(scope="module")
def site_url():
    """Serve the HTML Loqua replica over HTTP."""
    port = _free_port()
    handler = lambda *a, **kw: SimpleHTTPRequestHandler(*a, directory=SITE_DIR, **kw)
    httpd = ThreadingHTTPServer(("127.0.0.1", port), handler)
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    yield f"http://127.0.0.1:{port}/"
    httpd.shutdown()


def _has_vision_credentials():
    return bool(os.environ.get("OPENAI_API_KEY") or os.environ.get("AGENTDROP_VISION_API_KEY")) or os.environ.get(
        "AGENTDROP_VISION_API_KEY_ENV"
    )


def test_loqua_benchmark_real_browser(cdp_port, site_url):
    if not _has_vision_credentials():
        pytest.skip("no vision API credentials set (OPENAI_API_KEY / AGENTDROP_VISION_API_KEY)")

    from agentdrop.campaigns.base import Campaign
    from agentdrop.cdp.browser import BrowserSession
    from agentdrop.loop.computer_use import ComputerUseLoop, LoopConfig
    from agentdrop.loop.metrics import Metrics, TARGETS
    from agentdrop.loop.security import SecurityGate, SecurityPolicy
    from agentdrop.config import EngineConfig
    import tempfile

    browser = BrowserSession.connect(host="127.0.0.1", port=cdp_port, viewport=(1280, 800))
    campaign = Campaign.load(CAMPAIGN)
    for t in campaign.tasks:
        if t.url:
            t.url = t.url.replace("{LIVE_URL}", site_url.rstrip("/"))
    browser.navigate(site_url)

    planner = EngineConfig().build_planner()
    metrics = Metrics(max_steps=50)
    with tempfile.TemporaryDirectory() as tmp:
        loop = ComputerUseLoop(
            browser=browser, planner=planner, metrics=metrics,
            security=SecurityGate(SecurityPolicy()),
            config=LoopConfig(evidence_dir=os.path.join(tmp, "evidence")),
        )
        result = loop.run_campaign(campaign, run_dir=os.path.join(tmp, "evidence"))

    report = metrics.report()
    assert result.all_completed, f"campaign incomplete: {report}"
    assert metrics.total_steps < TARGETS["max_steps"], report
    assert metrics.click_accuracy is None or metrics.click_accuracy >= TARGETS["click_accuracy_min"], report
