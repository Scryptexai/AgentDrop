#!/usr/bin/env python3
"""
validate_config.py — validator statis untuk repo AgentDrop.

Memastikan setiap file yang kita kirim benar-benar cocok dengan skema Hermes
Agent yang sesungguhnya, BUKAN dengan skema karangan.

Daftar key di bawah diekstrak langsung dari:
    NousResearch/hermes-agent @ 25 Aug 2026
    hermes_cli/config_defaults.py  -> DEFAULT_CONFIG (89 top-level keys)
    cli-config.yaml.example
    hermes_cli/tools_config.py     -> id toolset
    skill bawaan                   -> format frontmatter SKILL.md

Kalau Anda punya clone hermes-agent lokal, validator bisa menurunkan ulang
daftar key dari sumber aslinya (bukan memakai salinan beku):

    HERMES_SRC=/path/to/hermes-agent python3 tools/validate_config.py

Itu jalur yang lebih dapat dipercaya — salinan beku di bawah bisa basi.

Exit code 0 = semua lolos. 1 = ada ERROR.
"""

from __future__ import annotations

import ast
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover
    print("Butuh PyYAML:  pip install pyyaml", file=sys.stderr)
    sys.exit(2)

REPO = Path(__file__).resolve().parent.parent

# ============================================================================
# Daftar valid — hasil ekstraksi dari sumber Hermes (lihat docstring)
# ============================================================================

TOP_LEVEL_KEYS = {
    "_config_version", "agent", "approvals", "auxiliary", "bedrock", "bot_mode",
    "browser", "checkpoints", "code_execution", "command_allowlist",
    "compression", "computer_use", "context", "context_file_max_chars",
    "credential_pool_strategies", "cron", "curator", "dashboard", "database",
    "delegation", "desktop", "discord", "display", "doctor",
    "fallback_providers", "file_read_max_chars", "gateway", "goals", "honcho",
    "hooks", "hooks_auto_accept", "human_delay", "kanban", "logging", "loops",
    "lsp", "matrix", "mattermost", "max_concurrent_sessions", "max_live_sessions",
    "mcp", "mcp_discovery_timeout", "mcp_single_query_discovery_timeout",
    "memory", "moa", "model", "model_catalog", "model_overrides", "models_dev",
    "monitoring", "network", "onboarding", "openrouter",
    "paste_collapse_char_threshold", "paste_collapse_threshold",
    "paste_collapse_threshold_fallback", "personalities", "platform_hints",
    "prefill_messages_file", "privacy", "prompt_caching", "providers", "proxy",
    "quick_commands", "runtime", "secrets", "security", "session", "sessions",
    "skills", "slack", "streaming", "stt", "telegram", "telemetry", "terminal",
    "timezone", "tool_loop_guardrails", "tool_output", "tools", "toolsets",
    "tts", "updates", "vertex", "voice", "wake_word", "web", "whatsapp",
    "x_search",
}

# PENTING — DEFAULT_CONFIG BUKAN daftar lengkap key yang valid.
# Tiga key ini didokumentasikan di cli-config.yaml.example dan dibaca kode,
# tapi tidak muncul di DEFAULT_CONFIG. Diverifikasi: `platform_toolsets`
# bahkan punya validator khusus (hermes_cli/config.py:2405
# validate_platform_toolsets) dan ditulis oleh setup wizard (config.py:1999).
#
# Bug ini ditemukan saat config worker-orchestrator memakai platform_toolsets
# dan validator menolaknya sebagai "tidak dikenal" — false positive.
TOP_LEVEL_KEYS_ONLY_IN_EXAMPLE = {
    "platform_toolsets",
    "group_sessions_per_user",
    "session_reset",
}
TOP_LEVEL_KEYS |= TOP_LEVEL_KEYS_ONLY_IN_EXAMPLE

BROWSER_KEYS = {
    "allow_private_urls", "allow_unsafe_evaluate", "auto_local_for_private_urls",
    # "camofox" sengaja tetap di daftar key valid meskipun AgentDrop sudah tidak
    # memakainya: dengan begini, config yang masih menyisakan browser.camofox
    # tertangkap oleh pesan error SPESIFIK di check_browser_config ("Camofox dan
    # CDP saling eksklusif"), bukan oleh pesan generik "bukan key yang valid".
    "backend", "camofox", "cdp_url", "command_timeout", "dialog_policy",
    "dialog_timeout_s", "engine", "extension_control", "headed",
    "inactivity_timeout", "record_sessions", "restrict_evaluate",
    "snapshot_threshold",
}

CRON_KEYS = {
    "allow_agent_scheduling", "chronos", "max_parallel_jobs",
    "media_send_timeout_seconds", "mirror_delivery", "model",
    "model_drift_guard", "model_provider", "output_retention", "preflight",
    "provider", "script_timeout_seconds", "session_db_timeout_seconds",
    "wrap_response",
}

APPROVALS_KEYS = {
    "cron_mode", "denial_breaker_threshold", "deny",
    "destructive_slash_confirm", "mcp_reload_confirm", "mode",
    "single_query_mode", "smart_policy", "timeout",
}

SECURITY_KEYS = {
    "acked_advisories", "allow_data_training_tiers_noninteractive",
    "allow_lazy_installs", "allow_private_urls", "approval",
    "protected_instruction_extra_patterns", "protected_instruction_files",
    "redact_secrets", "tirith_enabled", "tirith_fail_open", "tirith_path",
    "tirith_timeout", "website_blocklist",
}

# Dari hermes_cli/tools_config.py
# 58 id toolset, diturunkan dari toolsets.py:TOOLSETS di sumber Hermes
# (bukan dikarang). delegate_task BUKAN id toolset — ia adalah NAMA TOOL di
# dalam toolset "delegation". Menyebutnya di platform_toolsets membuat
# Hermes tidak memberi tool delegasi sama sekali.
TOOLSET_IDS = {
    "browser", "clarify", "code_execution", "coding", "computer_use", "context_engine",
    "cronjob", "debugging", "delegation", "desktop_ui", "discord", "discord_admin",
    "feishu_doc", "feishu_drive", "file", "hermes-acp", "hermes-api-server",
    "hermes-bluebubbles", "hermes-cli", "hermes-cron", "hermes-dingtalk", "hermes-discord",
    "hermes-email", "hermes-feishu", "hermes-gateway", "hermes-homeassistant",
    "hermes-matrix", "hermes-mattermost", "hermes-qqbot", "hermes-signal", "hermes-slack",
    "hermes-sms", "hermes-telegram", "hermes-webhook", "hermes-wecom",
    "hermes-wecom-callback", "hermes-weixin", "hermes-whatsapp", "hermes-yuanbao",
    "homeassistant", "image_gen", "kanban", "memory", "project", "safe", "search",
    "session_search", "skills", "spotify", "terminal", "todo", "tts", "video", "video_gen",
    "vision", "web", "x_search", "yuanbao",
}

# Frontmatter wajib, dari skill bawaan Hermes
SKILL_REQUIRED = ["name", "description", "version", "license"]
SKILL_PLATFORMS = {"linux", "macos", "windows"}

REASONING_LEVELS = {"none", "minimal", "low", "medium", "high", "xhigh", "max", "ultra"}

errors: list[str] = []
warnings: list[str] = []
checks = 0


def err(msg: str) -> None:
    errors.append(msg)


def warn(msg: str) -> None:
    warnings.append(msg)


# ============================================================================
# Opsional: turunkan ulang daftar key dari clone hermes-agent asli
# ============================================================================
def maybe_refresh_from_source() -> None:
    src = os.environ.get("HERMES_SRC")
    if not src:
        print("  (memakai daftar key beku; set HERMES_SRC=<clone> untuk menurunkan ulang dari sumber)")
        return
    p = Path(src) / "hermes_cli" / "config_defaults.py"
    if not p.exists():
        warn(f"HERMES_SRC diset tapi {p} tidak ada — pakai daftar beku")
        return
    try:
        tree = ast.parse(p.read_text())
        dc = None
        for node in tree.body:
            if isinstance(node, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id == "DEFAULT_CONFIG" for t in node.targets
            ):
                dc = node.value
        if not isinstance(dc, ast.Dict):
            warn("DEFAULT_CONFIG tidak ditemukan — pakai daftar beku")
            return
        live = {k.value for k in dc.keys if isinstance(k, ast.Constant)}
        # DEFAULT_CONFIG saja TIDAK cukup. Gabungkan dengan top-level key yang
        # didokumentasikan di cli-config.yaml.example — kalau tidak, key sah
        # seperti platform_toolsets akan ditolak sebagai tidak dikenal.
        example = Path(src) / "cli-config.yaml.example"
        if example.exists():
            documented = set(re.findall(r"(?m)^([a-z_][a-z0-9_]*):", example.read_text()))
            live |= documented
            print(f"  (menggabungkan {len(documented)} key dari cli-config.yaml.example)")
        else:
            warn("cli-config.yaml.example tidak ditemukan di HERMES_SRC — "
                 "hanya DEFAULT_CONFIG yang dipakai, bisa ada false positive")
        missing = live - TOP_LEVEL_KEYS
        extra = TOP_LEVEL_KEYS - live
        if missing:
            print(f"  + {len(missing)} key baru di sumber yang belum ada di daftar beku: {sorted(missing)}")
        if extra:
            print(f"  - {len(extra)} key di daftar beku yang sudah tidak ada di sumber: {sorted(extra)}")
        if not missing and not extra:
            print("  ✓ daftar key beku cocok persis dengan sumber")
        TOP_LEVEL_KEYS.clear()
        TOP_LEVEL_KEYS.update(live)
    except Exception as exc:  # pragma: no cover
        warn(f"gagal membaca sumber Hermes: {exc}")


# ============================================================================
# Cek config.yaml
# ============================================================================
def check_config(path: Path) -> None:
    global checks
    checks += 1
    rel = path.relative_to(REPO)
    try:
        data = yaml.safe_load(path.read_text())
    except yaml.YAMLError as exc:
        err(f"{rel}: YAML tidak valid — {exc}")
        return
    if not isinstance(data, dict):
        err(f"{rel}: isi file bukan mapping")
        return

    for key in data:
        if key not in TOP_LEVEL_KEYS:
            err(f"{rel}: top-level key '{key}' tidak dikenal Hermes")

    # model.default harus "provider/model"
    model = data.get("model")
    if isinstance(model, dict):
        for k in model:
            if k not in {"default", "model", "provider", "base_url", "api_key",
                         "context_length", "max_tokens", "default_headers",
                         "extra_headers", "reasoning_effort", "timeout_seconds"}:
                warn(f"{rel}: model.{k} tidak diverifikasi terhadap sumber")
        d = model.get("default")
        if isinstance(d, str) and "/" not in d:
            err(f"{rel}: model.default='{d}' harus format 'provider/model'")

    # toolsets
    ts = data.get("toolsets")
    if isinstance(ts, list):
        for t in ts:
            if t not in TOOLSET_IDS:
                err(f"{rel}: toolset '{t}' bukan id valid Hermes (mis. 'file', bukan 'file_ops')")

    # browser
    br = data.get("browser")
    if isinstance(br, dict):
        for k in br:
            if k not in BROWSER_KEYS:
                err(f"{rel}: browser.{k} bukan key Hermes yang valid")

    # cron
    cr = data.get("cron")
    if isinstance(cr, dict):
        for k in cr:
            if k not in CRON_KEYS:
                err(f"{rel}: cron.{k} bukan key valid Hermes")

    # approvals / security
    ap = data.get("approvals")
    if isinstance(ap, dict):
        for k in ap:
            if k not in APPROVALS_KEYS:
                err(f"{rel}: approvals.{k} bukan key valid Hermes")

    sec = data.get("security")
    if isinstance(sec, dict):
        for k in sec:
            if k not in SECURITY_KEYS:
                err(f"{rel}: security.{k} bukan key valid Hermes "
                    f"(key karangan seperti never_store_private_keys/stop_on_captcha tidak ada)")

    # agent.reasoning_effort
    ag = data.get("agent")
    if isinstance(ag, dict):
        re_ = ag.get("reasoning_effort")
        if isinstance(re_, str) and re_ not in REASONING_LEVELS:
            err(f"{rel}: agent.reasoning_effort='{re_}' bukan level valid "
                f"({sorted(REASONING_LEVELS)})")


# ============================================================================
# Cek SKILL.md
# ============================================================================
def check_skill(path: Path) -> None:
    global checks
    checks += 1
    rel = path.relative_to(REPO)
    text = path.read_text()
    m = re.match(r"^---\n(.*?)\n---\n", text, re.DOTALL)
    if not m:
        err(f"{rel}: tidak ada YAML frontmatter. Skill Hermes WAJIB punya "
            f"frontmatter (lihat skills/apple/*/SKILL.md di repo Hermes).")
        return
    try:
        fm = yaml.safe_load(m.group(1))
    except yaml.YAMLError as exc:
        err(f"{rel}: frontmatter YAML tidak valid — {exc}")
        return
    if not isinstance(fm, dict):
        err(f"{rel}: frontmatter bukan mapping")
        return

    for field in SKILL_REQUIRED:
        if field not in fm:
            err(f"{rel}: frontmatter kehilangan field wajib '{field}'")

    if fm.get("name") and fm["name"] != path.parent.name:
        warn(f"{rel}: name='{fm['name']}' berbeda dari nama direktori '{path.parent.name}'")

    plats = fm.get("platforms")
    if isinstance(plats, list):
        for p in plats:
            if p not in SKILL_PLATFORMS:
                err(f"{rel}: platform '{p}' tidak valid ({sorted(SKILL_PLATFORMS)})")

    body = text[m.end():]
    if len(body.strip()) < 200:
        warn(f"{rel}: isi skill sangat pendek ({len(body.strip())} char) — "
             f"agent mungkin tidak punya cukup instruksi")


# ============================================================================
# Cek shell script
# ============================================================================
def check_shell(path: Path) -> None:
    global checks
    checks += 1
    rel = path.relative_to(REPO)
    r = subprocess.run(["bash", "-n", str(path)], capture_output=True, text=True)
    if r.returncode != 0:
        err(f"{rel}: bash -n gagal — {r.stderr.strip()}")

    text = path.read_text()

    # `hermes ... chat <teks>` tanpa -q adalah bug: chat tidak punya argumen posisional.
    for line in text.splitlines():
        if "chat " in line and "-q" not in line and "--query" not in line:
            if re.search(r"hermes.*\bchat\s+['\"]", line) or re.search(r"hermes.*\bchat\s+[A-Za-z]", line):
                err(f"{rel}: kemungkinan pemanggilan 'hermes chat' dengan argumen "
                    f"posisional. `hermes chat` hanya menerima -q/--query atau "
                    f"--query-file (mutually exclusive). Baris: {line.strip()}")

    # crontab sistem: kita sengaja pakai cron internal Hermes
    if re.search(r"^\s*\(crontab", text, re.MULTILINE):
        warn(f"{rel}: memakai system crontab. AgentDrop memakai scheduler internal "
             f"Hermes (`hermes cron create`) — lihat scripts/install-cron.sh")


# ============================================================================
# Cek .env.example
# ============================================================================
def check_env_example() -> None:
    global checks
    checks += 1
    p = REPO / ".env.example"
    if not p.exists():
        err(".env.example tidak ada")
        return
    text = p.read_text()

    # CDP_PORT adalah kunci yang menyambungkan Hermes ke Chrome yang kita
    # jalankan sendiri. Kalau hilang, agent jatuh kembali ke Chromium headless
    # milik agent-browser tanpa ekstensi.
    if "CDP_PORT" not in text:
        err(".env.example: tidak ada CDP_PORT — port browser tidak terdokumentasi")

    for must, why in (
        ("NOVNC_PORT", "port GUI browser tidak terdokumentasi"),
        ("CDP_PROFILE_DIR", "lokasi profil Chrome tidak terdokumentasi — login tidak akan bertahan"),
    ):
        if must not in text:
            err(f".env.example: tidak ada {must} — {why}")

    # Tidak boleh ada nilai secret sungguhan di template
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        if k.endswith(("API_KEY", "TOKEN", "SECRET", "PASSWORD")) and v.strip():
            err(f".env.example: {k} punya nilai '{v.strip()}' — template harus kosong")

    # Tidak boleh menyediakan tempat untuk private key
    for banned in ("PRIVATE_KEY=", "SEED_PHRASE=", "MNEMONIC="):
        if re.search(rf"^\s*{banned}", text, re.MULTILINE):
            err(f".env.example: menyediakan field {banned.rstrip('=')} — "
                f"agentdrop tidak boleh menyimpan private key")


# ============================================================================
# Cek .gitignore melindungi secret
# ============================================================================
def check_gitignore() -> None:
    global checks
    checks += 1
    p = REPO / ".gitignore"
    if not p.exists():
        err(".gitignore tidak ada")
        return
    text = p.read_text()
    for must in (".env", "auth.json", "browser-profiles/"):
        if must not in text:
            err(f".gitignore: tidak mengabaikan '{must}'")


# ============================================================================
# Cek bahwa SETIAP profil worker punya akses browser yang berkelanjutan
# ============================================================================
def check_browser_access(configs: list[Path]) -> None:
    """Setiap worker wajib punya browser lewat CDP.

    Persyaratan: 99% task airdrop adalah interaksi GUI, jadi worker tanpa
    toolset `browser` atau tanpa `managed_persistence` tidak berguna.
    """
    global checks
    for c in configs:
        if "/profiles/" not in str(c):
            continue
        checks += 1
        rel = c.relative_to(REPO)
        data = yaml.safe_load(c.read_text()) or {}
        name = c.parent.name

        ts = data.get("toolsets") or []
        if "browser" not in ts:
            err(f"{rel}: worker '{name}' tidak punya toolset 'browser' — "
                f"tidak bisa mengerjakan task GUI airdrop")

        br = data.get("browser")
        if not isinstance(br, dict):
            err(f"{rel}: worker '{name}' tidak punya blok browser sama sekali")
            continue

        cdp = br.get("cdp_url")
        if not isinstance(cdp, str) or not cdp.strip():
            err(f"{rel}: worker '{name}' tidak punya browser.cdp_url — Hermes akan "
                f"meluncurkan Chromium headless milik agent-browser sendiri, "
                f"tanpa ekstensi wallet")
        else:
            # CDP adalah remote control penuh atas browser. Kalau ia terikat ke
            # antarmuka publik, siapa pun di jaringan itu bisa mengemudikan
            # browser yang memegang wallet.
            host = cdp.split("//", 1)[-1].split("/", 1)[0].split(":")[0]
            if host not in ("127.0.0.1", "localhost"):
                err(f"{rel}: worker '{name}' browser.cdp_url menunjuk host "
                    f"'{host}' — harus loopback. CDP yang terbuka ke jaringan "
                    f"berarti browser ber-wallet bisa dikendalikan siapa pun.")

        # Camofox dan CDP saling eksklusif: backend Camofox REST-only dan tidak
        # mengekspos CDP (hermes-agent/tools/browser_cdp_tool.py:466).
        # Meninggalkan keduanya terpasang membuat niat konfigurasi ambigu.
        if isinstance(br.get("camofox"), dict):
            err(f"{rel}: worker '{name}' masih punya browser.camofox padahal sudah "
                f"berpindah ke cdp_url — Camofox dan CDP saling eksklusif, hapus "
                f"salah satunya")

        # headed tidak berlaku di mode CDP (hanya dipakai mode lokal), tapi
        # true di sini menyiratkan salah paham soal dari mana GUI datang.
        if br.get("headed") is True:
            warn(f"{rel}: browser.headed=true tidak berpengaruh di mode CDP. "
                 f"GUI setup ini datang dari noVNC (agentdrop browser).")

        # inactivity_timeout terlalu pendek memutus sesi login di tengah aksi
        it = br.get("inactivity_timeout")
        if isinstance(it, int) and it < 600:
            warn(f"{rel}: browser.inactivity_timeout={it}s terlalu pendek untuk "
                 f"rangkaian aksi farming (default Hermes 120s memutus sesi)")




# ============================================================================
# Skill yang memakai browser WAJIB punya aturan verifikasi alamat
# ============================================================================
def check_url_verification_rule() -> None:
    """_adopt_existing_tab bisa menempelkan agent ke tab yang salah.

    tools/browser_camofox.py:352 -> kalau tidak ada tab yang cocok session_key,
    Hermes mengambil tab TERBARU milik userId itu (bukan gagal). Jadi agent bisa
    snapshot halaman yang bukan tujuannya. Satu-satunya penahan adalah aturan
    "navigasi eksplisit lalu verifikasi URL" di dalam skill.

    Aturan itu harus ada di setiap skill yang menyuruh agent memakai browser,
    dan tidak boleh hilang diam-diam saat skill diedit.
    """
    global checks
    markers = ("browser_navigate", "browser_snapshot")
    for skill in sorted(REPO.glob("skills/*/SKILL.md")):
        text = skill.read_text()
        rel = skill.relative_to(REPO)
        uses_browser = any(m in text for m in markers)
        if not uses_browser:
            continue
        checks += 1
        # Aturan dianggap ada kalau skill menyebut navigasi eksplisit DAN
        # keharusan mencocokkan URL/judul.
        has_navigate_rule = "browser_navigate" in text
        has_verify_rule = ("cocokkan URL" in text) or ("URL/judul" in text) or ("URL + judul" in text)
        if not (has_navigate_rule and has_verify_rule):
            err(f"{rel}: memakai tool browser tapi tidak punya aturan "
                f"'navigasi eksplisit lalu verifikasi URL'. Tanpa itu agent bisa "
                f"bertindak di tab adopsi yang salah (_adopt_existing_tab mengambil "
                f"tab terbaru milik userId, bukan gagal).")
        else:
            print(f"  · {skill.parent.name}: aturan verifikasi alamat ada")


# ============================================================================
# Cek arsitektur delegasi: orchestrator + worker
# ============================================================================
def check_browser_protocol_adoption(configs: list[Path]) -> None:
    """SOUL.md adalah system prompt — protokol browser harus ada di sana.

    Skill `browser-operation` berisi protokolnya, tapi skill hanya *tersedia*;
    agent boleh memilih untuk tidak membacanya. Satu-satunya yang benar-benar
    mengikat adalah SOUL.md. Tanpa blok protokol di SOUL.md, agent bisa kembali
    ke CSS selector / XPath dan mengunci diri ke UI yang dinamis — persis
    kegagalan yang kita hindari.

    Yang wajib ada di setiap profil ber-browser:
      - larangan CSS selector / XPath
      - ref hanya sah pada snapshot yang menghasilkannya
      - verifikasi hasil sebelum melanjutkan aksi berikutnya
    """
    global checks
    required = (
        ("Protokol Browser", "blok protokol"),
        ("CSS selector", "larangan CSS selector"),
        ("hanya sah pada snapshot", "aturan ref tidak boleh diingat lintas snapshot"),
        ("Verifikasi sebelum lanjut", "kewajiban verifikasi hasil sebelum aksi berikutnya"),
    )
    for c in configs:
        if "/profiles/" not in str(c):
            continue
        data = yaml.safe_load(c.read_text()) or {}
        if "browser" not in (data.get("toolsets") or []):
            continue
        checks += 1
        name = c.parent.name
        soul = c.parent / "SOUL.md"
        if not soul.exists():
            err(f"{name}: config.yaml memberi toolset browser tapi SOUL.md tidak ada")
            continue
        text = soul.read_text()
        missing = [label for needle, label in required if needle not in text]
        if missing:
            err(f"{name}/SOUL.md: memakai browser tapi protokolnya hilang — {', '.join(missing)}. "
                f"SOUL.md adalah system prompt; kalau protokolnya tidak di sini, "
                f"agent boleh mengabaikannya dan kembali ke CSS selector.")


def check_burnin_gating() -> None:
    """Uji burn-in yang menyentuh wallet/sosial tidak boleh jalan diam-diam."""
    global checks
    sh = REPO / "scripts" / "burn-in.sh"
    if not sh.exists():
        err("scripts/burn-in.sh tidak ada — skill browser-burn-in tidak punya runner")
        return
    checks += 1
    text = sh.read_text()
    # Default harus 1-4 saja; 5 dan 6 butuh flag eksplisit.
    for needle, label in (
        ("--with-wallet", "flag untuk Uji 5 (wallet)"),
        ("--with-social", "flag untuk Uji 6 (sosial)"),
        ("TESTNET", "konfirmasi testnet sebelum Uji 5"),
    ):
        if needle not in text:
            err(f"scripts/burn-in.sh: kehilangan {label}")
    # Harus dipatok ke akhir baris: cek substring murni lolos saat seseorang
    # menulis "add 1; add 2; add 3; add 4; add 5; add 6".
    if not re.search(r"^\s*add 1; add 2; add 3; add 4\s*$", text, re.MULTILINE):
        err("scripts/burn-in.sh: daftar uji default harus tepat 1-4 saja "
            "(Uji 5/6 tidak boleh ikut tanpa flag)")
    # Burn-in harus reachable dari alur instal, kalau tidak pasti dilewati.
    checks += 1
    inst = REPO / "install.sh"
    # install.sh menyebutnya lewat CLI (agentdrop burn-in), bukan nama berkas.
    if "burn-in" not in inst.read_text():
        err("install.sh tidak menyebut burn-in — pengguna akan langsung "
            "memakai agent sebelum browser distabilkan")
    if "burn-in" not in (REPO / "README.md").read_text():
        err("README.md tidak menyebut burn-in")


def check_delegation_architecture() -> None:
    """Telegram -> orchestrator -> worker. Kalau salah satu mata rantai putus,
    workflow yang dijanjikan README tidak akan jalan."""
    global checks
    checks += 1
    orch = REPO / "config/hermes/profiles/worker-orchestrator/config.yaml"
    if not orch.exists():
        err("profil worker-orchestrator tidak ada — tidak ada pintu masuk Telegram")
        return
    data = yaml.safe_load(orch.read_text()) or {}

    ts = data.get("toolsets") or []
    # HANYA "delegation". "delegate_task" adalah NAMA TOOL di dalam toolset itu
    # (toolsets.py: "delegation": {"tools": ["delegate_task"]}), bukan id
    # toolset. Pemeriksaan lama menuntut keduanya, sehingga justru memaksa
    # nilai yang tidak valid masuk ke config.
    if "delegation" not in ts:
        err("worker-orchestrator: toolset 'delegation' tidak ada — tidak bisa mendelegasikan")
    if "delegate_task" in ts:
        err("worker-orchestrator: 'delegate_task' dipakai sebagai id toolset. "
            "Id-nya 'delegation'; 'delegate_task' adalah nama tool di dalamnya.")

    # Guard regresi: pintu masuk Telegram adalah satu-satunya jalan operator
    # memberi task. Kalau "delegation" hilang dari platform_toolsets.telegram,
    # orchestrator menerima pesan tapi TIDAK BISA mendelegasikan ke worker mana
    # pun — dan kegagalannya sunyi, karena tool-nya memang tidak pernah ada.
    pt = (data.get("platform_toolsets") or {}).get("telegram")
    if isinstance(pt, list) and "delegation" not in pt:
        err("worker-orchestrator: platform_toolsets.telegram tanpa 'delegation' — "
            "orchestrator bisa menerima task dari Telegram tapi tidak bisa "
            "mendelegasikannya ke worker")

    d = data.get("delegation")
    if not isinstance(d, dict):
        err("worker-orchestrator: blok 'delegation' tidak ada")
    else:
        if d.get("orchestrator_enabled") is not True:
            err("worker-orchestrator: delegation.orchestrator_enabled bukan true")
        depth = d.get("max_spawn_depth")
        if depth != 1:
            warn(f"worker-orchestrator: delegation.max_spawn_depth={depth}. "
                 f"Nilai >1 mengizinkan delegasi berantai — biaya bisa meledak.")
        if d.get("subagent_auto_approve") is True:
            err("worker-orchestrator: subagent_auto_approve=true — child bisa "
                "menyetujui aksinya sendiri tanpa manusia")

    # Pintu masuk publik tidak boleh punya shell
    pt = data.get("platform_toolsets") or {}
    tg = pt.get("telegram") or []
    if "terminal" in tg:
        err("worker-orchestrator: platform_toolsets.telegram memuat 'terminal' — "
            "pintu masuk Telegram tidak boleh punya akses shell")

    # Setiap worker harus disebut di routing orchestrator. Profil yang terpasang
    # tapi tidak pernah dirutekan tidak akan pernah dipakai — worker-x sempat
    # lolos dari sini karena ditambahkan ke setup.sh tapi tidak ke SOUL.md.
    soul = REPO / "config/hermes/profiles/worker-orchestrator/SOUL.md"
    if soul.exists():
        checks += 1
        soul_text = soul.read_text()
        workers = [p.name for p in sorted((REPO / "config/hermes/profiles").iterdir())
                   if p.is_dir() and p.name != "worker-orchestrator"]
        for w in workers:
            if f"`{w}`" not in soul_text:
                err(f"worker-orchestrator/SOUL.md tidak merutekan ke '{w}' — "
                    f"profil terpasang tapi tidak akan pernah didelegasikan")


# ============================================================================
# Cek setup.sh tidak melupakan profil/skill yang ada di disk
# ============================================================================
def check_setup_coverage() -> None:
    """Guard terhadap drift: direktori ada tapi tidak pernah terpasang."""
    global checks
    checks += 1
    setup = REPO / "lib/30-hermes.sh"
    if not setup.exists():
        err("./install.sh tidak ada")
        return
    text = setup.read_text()

    m_prof = re.search(r"^PROFILES=\(([^)]*)\)", text, re.MULTILINE)
    m_skill = re.search(r"^SKILLS=\(([^)]*)\)", text, re.MULTILINE)
    if not m_prof or not m_skill:
        err("lib/30-hermes.sh: tidak menemukan daftar PROFILES=(...) atau SKILLS=(...)")
        return

    listed_profiles = set(m_prof.group(1).split())
    listed_skills = set(m_skill.group(1).split())

    on_disk_profiles = {p.name for p in (REPO / "config/hermes/profiles").iterdir() if p.is_dir()}
    on_disk_skills = {p.name for p in (REPO / "skills").iterdir() if p.is_dir()}

    for missing in sorted(on_disk_profiles - listed_profiles):
        err(f"setup.sh: profil '{missing}' ada di disk tapi tidak ada di PROFILES=() "
            f"— tidak akan pernah terpasang")
    for missing in sorted(on_disk_skills - listed_skills):
        err(f"setup.sh: skill '{missing}' ada di disk tapi tidak ada di SKILLS=() "
            f"— tidak akan pernah terpasang")
    for ghost in sorted(listed_profiles - on_disk_profiles):
        err(f"setup.sh: PROFILES=() menyebut '{ghost}' tapi direktorinya tidak ada")
    for ghost in sorted(listed_skills - on_disk_skills):
        err(f"setup.sh: SKILLS=() menyebut '{ghost}' tapi direktorinya tidak ada")

    print(f"  · {len(on_disk_profiles)} profil, {len(on_disk_skills)} skill — semuanya tercakup")

    # ---- Pemetaan skill per profil -----------------------------------------
    # Tanpa pemetaan, setup.sh menyalin semua skill ke semua profil dan Hermes
    # tidak membatasi apa yang boleh dipanggil — worker-discord bisa
    # menjalankan daily-executor.
    checks += 1
    m_map = re.search(r"declare -A PROFILE_SKILLS=\((.*?)\n\)", text, re.DOTALL)
    if not m_map:
        err("setup.sh: tidak menemukan 'declare -A PROFILE_SKILLS=(...)' — "
            "skill akan tersalin ke semua profil tanpa pembatasan")
        return
    mapping = dict(re.findall(r"\[([\w-]+)\]=\"([^\"]*)\"", m_map.group(1)))

    for p in sorted(on_disk_profiles - set(mapping)):
        err(f"setup.sh: profil '{p}' tidak punya entri di PROFILE_SKILLS")
    for p in sorted(set(mapping) - on_disk_profiles):
        err(f"setup.sh: PROFILE_SKILLS menyebut '{p}' tapi profilnya tidak ada")

    mapped_skills = set()
    for p, slist in mapping.items():
        names = slist.split()
        mapped_skills.update(names)
        for ghost in sorted(set(names) - on_disk_skills):
            err(f"setup.sh: PROFILE_SKILLS[{p}] menyebut skill '{ghost}' yang tidak ada")
        if "browser-operation" not in names:
            err(f"setup.sh: PROFILE_SKILLS[{p}] tidak menyertakan 'browser-operation' "
                f"— protokol browser wajib ada di setiap profil")
    for orphan in sorted(on_disk_skills - mapped_skills):
        err(f"setup.sh: skill '{orphan}' tidak dipetakan ke profil mana pun "
            f"— tidak akan pernah terpasang")

    # setup.sh harus benar-benar MEMAKAI pemetaannya, bukan cuma mendeklarasikannya.
    if "PROFILE_SKILLS[$p]" not in text:
        err("setup.sh: PROFILE_SKILLS dideklarasikan tapi tidak dipakai di loop pemasangan")
    if 'rm -rf "$dst/skills"' not in text:
        err("setup.sh: folder skill tidak dibersihkan sebelum disalin — skill yang "
            "dikeluarkan dari pemetaan akan tetap tertinggal di profil")

    print(f"  · pemetaan skill: {len(mapping)} profil, "
          f"{len(mapped_skills)} skill terpetakan")


# ============================================================================
# Cek .env.example punya konfigurasi Telegram lengkap
# ============================================================================
def check_telegram_env() -> None:
    global checks
    checks += 1
    p = REPO / ".env.example"
    if not p.exists():
        return
    text = p.read_text()
    for must in ("TELEGRAM_BOT_TOKEN", "TELEGRAM_ALLOWED_USERS"):
        if must not in text:
            err(f".env.example: tidak ada {must} — bot Telegram tidak bisa diamankan")




def check_no_stray_cjk() -> None:
    """Karakter CJK yang terselip di tengah kalimat Indonesia.

    Sudah terjadi empat kali: 'membuat它', 'Anda确认', 'delegasi递归',
    'produk penuh低级错误'. Semuanya lolos review mata karena kalimatnya
    tetap terbaca. docs/ dikecualikan karena docs/research.md memang mengutip
    istilah airdrop Mandarin (反撸, 风口) dengan sengaja.
    """
    global checks
    targets = list((REPO / "config").rglob("*.md")) + \
              list((REPO / "config").rglob("*.yaml")) + \
              list((REPO / "skills").rglob("*.md")) + \
              list((REPO / "scripts").glob("*.sh")) + \
              list((REPO / "extensions").rglob("*.js")) + \
              [REPO / "README.md", REPO / "install.sh"]
    cjk = re.compile(r"[\u4e00-\u9fff\u3040-\u30ff]")
    hits = []
    for f in targets:
        if not f.exists():
            continue
        checks += 1
        for i, line in enumerate(f.read_text(errors="ignore").splitlines(), 1):
            if cjk.search(line):
                hits.append(f"{f.relative_to(REPO)}:{i}: {line.strip()[:70]}")
    for h in hits:
        err(f"karakter CJK terselip -> {h}")




def check_shell_disabled(configs: list[Path]) -> None:
    """Worker tidak boleh punya akses shell.

    Toolset `hermes-cli` memuat seluruh _HERMES_CORE_TOOLS
    (hermes-agent/toolsets.py:31-35), yang berisi "terminal" dan "process".
    Jadi mencoret kata `terminal` dari daftar `toolsets:` TIDAK cukup —
    agent tetap mendapatkannya lewat bundle.

    Kegagalan yang dicegah di sini adalah yang paling mahal saat farming:
    alih-alih memakai tool browser native, agent mengetik perintah shell untuk
    membuka browser sendiri (headless, tanpa ekstensi, tanpa sesi login) lalu
    melaporkan sukses.

    `agent.disabled_toolsets` dikurangkan paling akhir
    (hermes_cli/tools_config.py:2712-2726: "This runs last so it overrides
    everything above"), jadi hanya itu yang benar-benar menutup bundle.
    """
    global checks
    dilarang = {"terminal", "code_execution"}
    for c in configs:
        if "/profiles/" not in str(c):
            continue
        checks += 1
        name = c.parent.name
        data = yaml.safe_load(c.read_text()) or {}

        dt = set((data.get("agent") or {}).get("disabled_toolsets") or [])
        for need in sorted(dilarang - dt):
            err(f"{name}: agent.disabled_toolsets tidak memuat '{need}' — "
                f"agent tetap bisa menjalankan perintah shell lewat bundle hermes-cli")

        # Tidak boleh juga disebut eksplisit di toolsets / platform_toolsets.
        for ts in (data.get("toolsets") or []):
            if ts in dilarang:
                err(f"{name}: toolsets memuat '{ts}' padahal harus dimatikan")
        for plat, tss in (data.get("platform_toolsets") or {}).items():
            for ts in (tss or []):
                if ts in dilarang:
                    err(f"{name}: platform_toolsets.{plat} memuat '{ts}'")

        # Blok konfigurasi terminal yang tersisa menyesatkan: ia menyiratkan
        # tool itu aktif.
        if "terminal" in data:
            warn(f"{name}: masih punya blok top-level `terminal:` — tidak dipakai "
                 f"selama toolset-nya dimatikan, tapi sebaiknya dihapus")


def check_browser_tool_contract() -> None:
    """Skill tidak boleh menyuruh agent memakai tool yang tidak dimilikinya.

    Ini kelas bug yang sudah terjadi dua kali: SOUL.md menyuruh agent
    menjalankan tools/signing_policy.py yang sudah dihapus, dan tiga skill
    menyuruh memakai computer_use(mode='som') padahal toolset itu tidak
    diaktifkan untuk profil mana pun. Agent yang memanggil tool yang tidak ada
    akan berimprovisasi -- dan improvisasi paling mahal terjadi di browser.
    """
    global checks

    ADA = {
        "browser_navigate", "browser_snapshot", "browser_click", "browser_type",
        "browser_scroll", "browser_press", "browser_back", "browser_vision",
        "browser_get_images", "browser_console", "browser_exec",
        "browser_dialog", "browser_cdp", "web_search", "web_extract",
    }
    for md in sorted((REPO / "skills").rglob("SKILL.md")):
        checks += 1
        # (?<![\w/]) dan (?!\.py) mengecualikan nama berkas sumber seperti
        # tools/browser_tool.py, yang bukan panggilan tool.
        for m in re.finditer(r"(?<![\w/])(browser_[a-z_]+)(?!\.py)\b", md.read_text()):
            if m.group(1) not in ADA:
                err(f"{md.relative_to(REPO)}: memakai '{m.group(1)}' yang tidak "
                    f"ada di tool browser Hermes")

    for md in sorted(list((REPO / "skills").rglob("SKILL.md")) +
                     list((REPO / "config" / "hermes").rglob("SOUL.md"))):
        checks += 1
        text = md.read_text()
        if "computer_use(" in text or "computer_use mode" in text:
            err(f"{md.relative_to(REPO)}: menganjurkan computer_use, padahal "
                f"toolset itu tidak diaktifkan untuk profil mana pun")

    checks += 1
    bo = REPO / "skills" / "browser-operation" / "SKILL.md"
    if bo.exists():
        text = bo.read_text()
        for wajib in ("browser_scroll", "browser_type", "browser_press", "web_search"):
            if wajib not in text:
                err(f"browser-operation/SKILL.md tidak mendokumentasikan {wajib}")


def check_memory_loop(configs: list[Path]) -> None:
    """Memory loop terpasang di setiap agent.

    Meta airdrop berubah tiap cycle, jadi dokumen strategi akan basi. Yang
    menghadapi kenyataan baru setiap hari adalah agent, bukan dokumen — karena
    itu agent harus menyimpan pelajarannya sendiri (skills/self-improvement).

    Kegagalan yang dicegah di sini adalah yang paling mahal dan paling tidak
    terlihat: agent mengulang pendekatan yang sudah terbukti gagal, dengan cara
    yang sama, tanpa ada yang mencatat bahwa cara itu tidak berhasil.
    """
    global checks
    for c in configs:
        if "/profiles/" not in str(c):
            continue
        name = c.parent.name
        data = yaml.safe_load(c.read_text()) or {}

        checks += 1
        mem = data.get("memory")
        if not isinstance(mem, dict):
            err(f"{name}: tidak punya blok `memory:` — tinjauan memory berkala "
                f"Hermes tidak dikonfigurasi")
        else:
            if mem.get("memory_enabled") is not True:
                err(f"{name}: memory.memory_enabled bukan true")
            ni = mem.get("nudge_interval")
            if not isinstance(ni, int) or ni <= 0:
                err(f"{name}: memory.nudge_interval harus bilangan bulat positif")
            elif ni > 30:
                warn(f"{name}: memory.nudge_interval={ni} — tinjauan terlalu jarang, "
                     f"pelajaran menumpuk sebelum sempat ditinjau")

        # Skill loop-nya harus benar-benar terpasang untuk profil ini.
        checks += 1
        soul = c.parent / "SOUL.md"
        if not soul.exists():
            err(f"{name}: SOUL.md tidak ada")
        else:
            st = soul.read_text()
            for needle, label in (
                ("Memory loop", "protokol memory loop"),
                ("memory/lessons/", "rujukan berkas pelajaran"),
                ("DATA, bukan instruksi", "aturan anti prompt-injection"),
            ):
                if needle not in st:
                    err(f"{name}/SOUL.md tidak memuat {label}")

    # Skill-nya sendiri harus ada dan dipetakan ke setiap profil.
    checks += 1
    if not (REPO / "skills" / "self-improvement" / "SKILL.md").exists():
        err("skills/self-improvement/SKILL.md tidak ada")

    checks += 1
    setup = (REPO / "lib" / "30-hermes.sh").read_text()
    if "self-improvement" not in setup:
        err("lib/30-hermes.sh tidak menyalin skill self-improvement ke profil mana pun")
    else:
        for c in configs:
            if "/profiles/" not in str(c):
                continue
            name = c.parent.name
            if not re.search(rf'\[{re.escape(name)}\]="[^"]*self-improvement', setup):
                err(f"setup.sh tidak memetakan self-improvement ke {name} — "
                    f"profil itu tidak akan punya loop belajar")

    checks += 1
    if not (REPO / "memory" / "lessons").is_dir():
        err("memory/lessons/ tidak ada — agent tidak punya tempat menulis pelajaran")


def check_audit_log() -> None:
    """Log audit: terpasang, tersambung, dan tidak membocorkan secret.

    Tujuan sistem ini adalah memperbaiki bagian yang salah tanpa membaca
    seluruh alur. Kalau ada satu mata rantai yang tidak tersambung, log akan
    berlubang tepat di tempat yang sedang rusak — dan lubang itu tidak
    terlihat sampai Anda membutuhkannya.
    """
    global checks
    for f in (REPO / "tools" / "audit_log.py", REPO / "tools" / "audit.py",
              REPO / "agent-hooks" / "audit-log.py",
              REPO / "hooks" / "agentdrop-audit" / "HOOK.yaml",
              REPO / "hooks" / "agentdrop-audit" / "handler.py"):
        checks += 1
        if not f.exists():
            err(f"{f.relative_to(REPO)} tidak ada")

    # Uji redaksi dengan artefak nyata. Ini cek paling penting di sini:
    # kegagalan redaksi berarti private key masuk ke berkas yang bisa dibaca
    # agent lain dan mungkin ikut ter-backup.
    checks += 1
    try:
        sys.path.insert(0, str(REPO / "tools"))
        import audit_log as A
        bocor = []
        # Lapisan 1: kunci bernama. Nilai dibuang apa pun bentuknya.
        # Lapisan 2: pola nilai. Ini yang melindungi kalau kuncinya TIDAK
        # mencurigakan — misalnya secret yang nyangkut di dalam pesan error
        # atau di field bernama "catatan". Kedua lapisan harus diuji terpisah,
        # kalau tidak uji ini lolos padahal regex-nya sudah rusak.
        kasus_kunci = {
            "private_key": "0x" + "11" * 32,
            "api_key": "sk-" + "A" * 30,
            "mnemonic": "x y z",
        }
        for nama, nilai in kasus_kunci.items():
            out = json.dumps(A.redact({nama: nilai}), ensure_ascii=False)
            if nilai[:16] in out:
                bocor.append(f"kunci:{nama}")
        if A.redact({"mnemonic": "x y z"}) != {"mnemonic": "<DIBUANG>"}:
            bocor.append("kunci-bernama-tidak-dibuang")

        # Lapisan pola. Diuji lewat MARKER-nya, bukan lewat "apakah sesuatu
        # ikut terhapus". Alasannya konkret: pola base64-panjang adalah jaring
        # pengaman yang ikut menangkap hex64 dan base58, jadi memeriksa
        # "secret hilang" saja tidak membuktikan pola yang bersangkutan hidup.
        # Memeriksa marker membuktikan pola itu sendiri yang bekerja.
        kasus_pola = [
            ("hex64", "<HEX64_DIBUANG>",
             "catatan", "key 0x" + "11" * 32 + " dipakai", "11" * 32),
            ("sk-", "<SK_DIBUANG>",
             "pesan", "gagal dengan sk-" + "A" * 30, "A" * 30),
            ("bot token", "<BOT_TOKEN_DIBUANG>",
             "url", "https://api.telegram.org/bot123456789:AA" + "B" * 34, "B" * 34),
            ("base58", "<BASE58_DIBUANG>",
             "teks", "s " + "5" * 87 + " s", "5" * 87),
            ("seed", "<MUNGKIN_SEED_DIBUANG>",
             "teks", "seed: alpha bravo charlie delta echo foxtrot golf hotel india juliet kilo lima",
             "juliet kilo lima"),
        ]
        for label, marker, kunci, nilai, rahasia in kasus_pola:
            out = json.dumps(A.redact({kunci: nilai}), ensure_ascii=False)
            if rahasia in out:
                bocor.append(f"pola:{label}(secret-masih-ada)")
            elif marker not in out:
                # Secret hilang, tapi bukan oleh pola yang seharusnya —
                # artinya pola itu mati dan hanya jaring pengaman yang menutupi.
                bocor.append(f"pola:{label}(marker-tidak-muncul)")

        if bocor:
            err(f"redaksi audit_log bocor untuk: {', '.join(bocor)}")
        else:
            print("  · redaksi lapisan kunci: private_key, api_key, mnemonic")
            print("  · redaksi lapisan pola : hex64, sk-, bot token, base58, seed")
    except Exception as exc:
        err(f"gagal menguji redaksi audit_log: {exc}")

    # Setiap profil harus mendaftarkan hook, dengan nama event yang sah.
    # Hermes MENGABAIKAN nama event yang salah dengan satu peringatan, jadi
    # typo di sini menghasilkan log kosong tanpa error apa pun.
    checks += 1
    wajib = {"pre_tool_call", "post_tool_call"}
    for c in sorted((REPO / "config" / "hermes" / "profiles").glob("*/config.yaml")):
        data = yaml.safe_load(c.read_text()) or {}
        name = c.parent.name
        hooks = data.get("hooks") or {}
        if not isinstance(hooks, dict) or not hooks:
            err(f"{name}: tidak punya blok `hooks:` — aktivitasnya tidak akan tercatat")
            continue
        for need in wajib - set(hooks):
            err(f"{name}: hooks tidak mendaftarkan '{need}' — pemanggilan tool tidak tercatat")
        if data.get("hooks_auto_accept") is not True:
            err(f"{name}: hooks_auto_accept bukan true — pada cron/gateway tanpa TTY "
                f"hook diabaikan diam-diam")
        for ev, entries in hooks.items():
            for e in (entries or []):
                cmd = (e or {}).get("command", "")
                if "audit-log.py" not in cmd:
                    err(f"{name}: hooks.{ev} tidak menunjuk audit-log.py")

    # setup.sh harus menyalin hook ke lokasi tetap, karena command hook tidak
    # meng-expand $VAR (hanya expanduser).
    checks += 1
    setup = (REPO / "lib" / "30-hermes.sh").read_text()
    for needle in ("agent-hooks/audit-log.py", "hooks/agentdrop-audit"):
        if needle not in setup:
            err(f"lib/30-hermes.sh tidak memasang {needle} — hook tidak akan "
                f"ditemukan Hermes setelah instalasi")

    # Jalankan audit.py health sebagai smoke test: kalau importnya rusak,
    # seluruh alat triase mati dan log tidak bisa dibaca.
    checks += 1
    proc = subprocess.run([sys.executable, str(REPO / "tools" / "audit.py"), "health"],
                          capture_output=True, text=True, cwd=str(REPO))
    if proc.returncode != 0:
        err(f"tools/audit.py health GAGAL (exit {proc.returncode}):\n"
            f"{(proc.stdout + proc.stderr).strip()[-800:]}")

    # Hasil uji harus bisa sampai ke repo. Log hidup di ~/.agentdrop/logs,
    # DI LUAR repo, jadi git push biasa tidak menyertakannya sama sekali.
    checks += 1
    collect = REPO / "scripts" / "collect-logs.sh"
    if not collect.exists():
        err("scripts/collect-logs.sh tidak ada — hasil uji tidak akan pernah "
            "sampai ke repo untuk dianalisis")
    else:
        ct = collect.read_text()
        # Gerbang secret wajib ada: hasil skrip ini dimaksudkan untuk di-commit.
        if "DIBATALKAN" not in ct or "forbidden_names" not in ct:
            err("collect-logs.sh kehilangan gerbang secret — hasilnya di-commit, "
                "jadi kebocoran di sini masuk ke git")
        if "data/audit" not in ct:
            err("collect-logs.sh tidak menulis ke data/audit/")
        # data/audit harus benar-benar bisa di-commit
        gi = (REPO / ".gitignore").read_text()
        if "!data/audit" not in gi:
            err(".gitignore tidak mengecualikan data/audit/ — hasil uji akan "
                "diabaikan git dan tidak ikut ter-push")

    checks += 1
    if not (REPO / "lib" / "50-verify.sh").exists():
        err("lib/50-verify.sh tidak ada — kegagalan lingkungan baru "
            "ketahuan di akhir run uji")


def main() -> int:
    print("=" * 62)
    print("  AgentDrop — validator statis")
    print("=" * 62)

    print("\n[1] Sumber daftar key")
    maybe_refresh_from_source()

    configs = sorted(REPO.glob("config/hermes/**/config.yaml"))
    print(f"\n[2] config.yaml ({len(configs)} file)")
    for c in configs:
        check_config(c)
        print(f"  · {c.relative_to(REPO)}")

    skills = sorted(REPO.glob("skills/*/SKILL.md"))
    print(f"\n[3] SKILL.md ({len(skills)} file)")
    for s in skills:
        check_skill(s)
        print(f"  · {s.relative_to(REPO)}")

    scripts = sorted(REPO.glob("scripts/*.sh")) + ([REPO / "install.sh"] if (REPO / "install.sh").exists() else [])
    print(f"\n[4] Shell scripts ({len(scripts)} file)")
    for sh in scripts:
        check_shell(sh)
        print(f"  · {sh.relative_to(REPO)}")

    print("\n[5] Akses browser per worker (GUI persisten)")
    check_browser_access(configs)
    for c in configs:
        if "/profiles/" in str(c):
            print(f"  · {c.parent.name}")


    print("\n[7] Aturan verifikasi alamat di skill browser")
    check_url_verification_rule()

    print("\n[8] Arsitektur delegasi (orchestrator -> worker)")
    check_delegation_architecture()
    print("  · worker-orchestrator")

    print("\n[9] Cakupan setup.sh (guard drift)")
    check_setup_coverage()

    print("\n[10] .env.example")
    check_env_example()
    check_telegram_env()
    print("  · .env.example")

    print("\n[11] .gitignore")
    check_gitignore()
    print("  · .gitignore")

    print("\n[12] Adopsi protokol browser di SOUL.md")
    check_browser_protocol_adoption(configs)
    for c in configs:
        if "/profiles/" in str(c):
            print(f"  · {c.parent.name}/SOUL.md")

    print("\n[13] Gating uji burn-in (wallet/sosial butuh flag)")
    check_burnin_gating()
    print("  · scripts/burn-in.sh")


    print("\n[15] Karakter CJK terselip di config/skill/README")
    check_no_stray_cjk()


    print("\n[17] Akses shell dimatikan di semua worker")
    check_shell_disabled(configs)

    print("\n[18] Memory loop + aturan anti prompt-injection")
    check_memory_loop(configs)

    print("\n[19] Log audit")
    check_audit_log()

    print("\n[20] Kontrak tool browser")
    check_browser_tool_contract()

    print("\n" + "=" * 62)
    print(f"  {checks} file diperiksa")
    if warnings:
        print(f"  {len(warnings)} peringatan:")
        for w in warnings:
            print(f"    ! {w}")
    if errors:
        print(f"  {len(errors)} ERROR:")
        for e in errors:
            print(f"    ✗ {e}")
        print("=" * 62)
        return 1
    print("  ✓ SEMUA LOLOS")
    print("=" * 62)
    return 0


if __name__ == "__main__":
    sys.exit(main())
