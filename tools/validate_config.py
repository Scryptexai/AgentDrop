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
    # custom_providers sah di root walau tidak ada di DEFAULT_CONFIG:
    # hermes_cli/config.py:2076 memasukkannya ke _EXTRA_KNOWN_ROOT_KEYS
    # ("legacy list form; modern equivalent is providers: {}"). Bentuk list
    # inilah yang ditulis `hermes model` sendiri (main.py:4957), jadi kita
    # pakai bentuk yang sama agar tidak ada dua skema yang bersaing.
    "credential_pool_strategies", "cron", "curator", "custom_providers",
    "dashboard", "database",
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
# Bug ini ditemukan saat config pekerja-koordinator memakai platform_toolsets
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

# 34 id toolset, diturunkan dari toolsets.py:TOOLSETS di sumber Hermes
# (bukan dikarang). Isinya diverifikasi identik dengan sumber, bukan hanya
# jumlahnya. Perhatikan bahwa hermes_cli/tools_config.py punya daftar berbeda
# bernama CONFIGURABLE_TOOLSETS (26 id) — yang dipakai validator adalah
# toolsets.py:TOOLSETS, karena itulah yang menentukan tool apa yang benar-benar
# tersedia bagi sebuah profil. delegate_task BUKAN id toolset — ia adalah NAMA TOOL di
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
        # Rujukan ${VAR} dikecualikan: sesudah model dipindah ke .env, nilai di
        # config adalah "${AGENTDROP_MODEL}" dan slash-nya baru muncul sesudah
        # Hermes meng-expand-nya. Memaksa slash di sini mendorong orang
        # meng-hardcode model lagi, persis cacat yang membuat install ulang
        # menghapus provider custom operator. Bentuknya dijaga [23].
        if isinstance(d, str) and "/" not in d and "${" not in d:
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
        # Komentar yang MENDOKUMENTASIKAN pola ini bukan cacat — sama seperti
        # aturan `grep -c || echo 0` di bawah. Tanpa ini, menulis
        # "hermes chat mengembalikan 0 walau task gagal" di komentar terbaca
        # sebagai pemanggilan yang salah, dan penulis akan tergoda menghapus
        # penjelasannya daripada memperbaiki kodenya.
        if line.lstrip().startswith("#"):
            continue
        if "chat " in line and "-q" not in line and "--query" not in line:
            if re.search(r"hermes.*\bchat\s+['\"]", line) or re.search(r"hermes.*\bchat\s+[A-Za-z]", line):
                err(f"{rel}: kemungkinan pemanggilan 'hermes chat' dengan argumen "
                    f"posisional. `hermes chat` hanya menerima -q/--query atau "
                    f"--query-file (mutually exclusive). Baris: {line.strip()}")

    # `grep -c ... || echo 0` menghasilkan "0\n0", bukan "0": grep -c mencetak
    # 0 DAN keluar dengan status 1 saat tidak ada kecocokan, jadi echo ikut jalan.
    # Nilai itu lalu membuat `[[ "$n" -gt 0 ]]` gagal dengan "syntax error in
    # expression" — bug nyata yang lolos 180 pemeriksaan dan baru ketahuan di
    # mesin operator. Yang benar: `|| true` lalu default `${n:-0}`.
    for i, line in enumerate(text.splitlines(), 1):
        if line.lstrip().startswith("#"):
            continue  # komentar yang MENDOKUMENTASIKAN pola ini bukan cacat
        if re.search(r"grep\s+-c.*\|\|\s*echo\s+0", line):
            err(f"{rel}:{i}: `grep -c ... || echo 0` menghasilkan \"0\\n0\" saat tidak "
                f"ada kecocokan (grep -c mencetak 0 lalu keluar 1), dan itu merusak "
                f"perbandingan numerik. Pakai `|| true` lalu `${{n:-0}}`. "
                f"Baris: {line.strip()}")

    # Direktori yang dijanjikan SOUL.md harus benar-benar dibuat installer.
    # Ketujuh SOUL.md menyuruh agent membaca `memory/lessons/<profil>.md`, tapi
    # dulu tidak ada satu pun stage yang membuat direktori itu di lokasi kerja —
    # jadi langkah pertama setiap agent adalah membaca berkas yang tidak pernah
    # ada. Validator tidak bisa menjalankan install.sh, tapi ia bisa memastikan
    # dua janji installer tetap ada di kode.
    if path.name == "install.sh":
        # Dulu pemeriksaan ini mencari `for item in lib tools ... ; do` dan
        # memastikan "memory" ada di daftar itu. Sesudah daftar allow dibalik
        # menjadi daftar exclude, polanya tidak ada lagi -- dan karena
        # dipagari `if m and ...`, pemeriksaan ini BERHENTI MENYALA tanpa
        # suara apa pun. Lolos bukan berarti benar.
        #
        # Bentuk barunya menguji janji yang sebenarnya: lokasi instal adalah
        # CERMIN repo. Berkas apa pun yang dibaca dari $ROOT harus ikut, jadi
        # yang diperiksa adalah daftar exclude-nya -- tidak boleh ada yang
        # dikecualikan padahal dibutuhkan.
        checks += 1
        if not re.search(r"tar -C \"\$REPO_ROOT\" -cf -", text):
            err(f"{rel}: stage_install_code tidak lagi menyalin repo sebagai "
                f"cermin (tar -C $REPO_ROOT -cf -). Daftar allow manual sudah "
                f"gagal empat kali (memory, lib, scripts, lalu "
                f"install.sh/README/.gitignore/.env.example) -- jangan "
                f"dikembalikan ke bentuk itu.")
        else:
            mexc = re.search(r"kecualikan=\(([^)]*)\)", text, re.S)
            dikecualikan = set()
            if mexc:
                dikecualikan = {x.strip().strip("'\"")
                                for x in mexc.group(1).split()
                                if not x.strip().startswith("#")}
            # Semua entri tingkat atas yang dibaca validator dari REPO. Kalau
            # salah satunya masuk daftar exclude, `agentdrop status` [5] akan
            # mati di mesin operator dengan FileNotFoundError -- persis cacat
            # yang membuat pemeriksaan ini ditulis.
            dibutuhkan = {".env.example", ".gitignore", "README.md", "install.sh",
                          "agent-hooks", "config", "hooks", "knowledge", "lib",
                          "memory", "scripts", "skills", "tools"}
            bocor = sorted(dibutuhkan & dikecualikan)
            if bocor:
                err(f"{rel}: daftar exclude stage_install_code membuang "
                    f"{bocor}, padahal validator membacanya dari lokasi instal. "
                    f"`agentdrop status` akan gagal dengan FileNotFoundError.")
    if path.name == "30-hermes.sh":
        # Harus yang PER-PROFIL ($dst/...), bukan sekadar ada mkdir memory/lessons
        # di mana pun. cwd agent adalah HERMES_HOME profil itu, jadi hanya
        # $dst/memory/lessons yang membuat path relatif di SOUL.md benar.
        # Versi pertama pemeriksaan ini mencari pola umum dan lolos walau
        # mkdir per-profilnya dihapus -- diuji dengan menyuntikkan cacatnya.
        if not re.search(r'mkdir -p[^\n]*\$dst/memory/lessons', text):
            err(f"{rel}: tidak ada mkdir untuk $dst/memory/lessons per profil, "
                f"padahal ketujuh SOUL.md menyuruh agent membaca "
                f"memory/lessons/<profil>.md relatif terhadap HERMES_HOME profil")

    # Assignment dari pipeline yang bisa gagal harus punya `|| true`.
    #
    # Di bawah `set -euo pipefail`, grep/pgrep yang tidak menemukan apa pun
    # keluar dengan 1; pipefail menularkan status itu ke seluruh pipeline, lalu
    # ke assignment-nya, lalu set -e mematikan skrip TANPA pesan.
    #
    # Inilah penyebab install operator berhenti tepat sesudah "==> Model":
    # TELEGRAM_* sudah ada di .env sehingga grep-nya cocok, sedangkan
    # OPENROUTER_API_KEY belum ada sehingga grep-nya gagal. Tiga perbaikan
    # sebelumnya meleset karena semuanya menyasar baris yang tidak pernah
    # dieksekusi.
    # `.*`, bukan `[^"]*`: baris nyata berisi tanda kutip di dalam pipeline
    # (mis. grep -E "^${var}="), dan [^"]* berhenti di sana sehingga \| tidak
    # pernah tercapai. Versi pertama pemeriksaan ini tidak pernah menangkap apa
    # pun karena itu -- diuji dengan menghapus `|| true` dan melihatnya lolos.
    _asg = re.compile(
        r'^\s*(?:local\s+)?[A-Za-z_][A-Za-z0-9_]*="\$\(.*\b(grep|egrep|fgrep|pgrep)\b.*\|')
    for _i, _l in enumerate(text.splitlines(), 1):
        if _asg.match(_l) and "|| true" not in _l:
            err(f"{rel}:{_i}: assignment dari pipeline grep/pgrep tanpa `|| true`. "
                f"Saat polanya tidak cocok, grep keluar 1; dengan pipefail itu "
                f"menular ke assignment dan set -e mematikan skrip tanpa pesan. "
                f"Baris: {_l.strip()[:70]}")

    # Baris TERAKHIR sebuah fungsi tidak boleh `[[ ... ]] && ...`.
    #
    # Kalau ujinya gagal, bentuk && mengembalikan 1, dan karena itu perintah
    # terakhir, fungsi ikut mengembalikan 1. Di bawah `set -euo pipefail`
    # pemanggilnya mati TANPA pesan error. Ini yang membuat install operator
    # berhenti tepat sesudah "==> Model" ketika kunci API dibiarkan kosong --
    # padahal prompt-nya sendiri menulis "atau kosongkan lalu isi di .env".
    # Akibatnya stage_setup tidak pernah jalan dan ~/.hermes/profiles/ kosong.
    #
    # Diuji dengan pty sungguhan: pola && mati sesudah prompt, if/then lanjut.
    _lines = text.splitlines()
    for _i, _l in enumerate(_lines):
        if _l.strip() == "}" and _i > 0:
            _prev = _lines[_i - 1].strip()
            if re.match(r"^\[\[.*\]\]\s*&&", _prev):
                err(f"{rel}:{_i}: baris terakhir fungsi adalah `{_prev[:60]}`. "
                    f"Bentuk && mengembalikan 1 saat ujinya gagal, sehingga fungsi "
                    f"mengembalikan 1 dan set -e mematikan pemanggilnya tanpa pesan. "
                    f"Pakai if/then, atau akhiri dengan `return 0`.")

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
        # KOORDINATOR sengaja TIDAK punya tool browser: ia mendelegasikan, tidak
        # mengeksekusi. Batas itu ditegakkan oleh skema tool, bukan hanya oleh
        # kalimat di SOUL.md. Untuk semua worker lain, browser wajib ada.
        if name == "pekerja-koordinator":
            if "browser" in ts:
                err(f"{rel}: koordinator punya toolset 'browser' — ia tidak boleh "
                    f"mengeksekusi; cabut agar batasnya ditegakkan oleh skema tool")
            if "delegation" not in ts:
                err(f"{rel}: koordinator tidak punya toolset 'delegation' — "
                    f"ia tidak bisa mendelegasikan ke worker mana pun")
        else:
            if "browser" not in ts:
                err(f"{rel}: worker '{name}' tidak punya toolset 'browser' — "
                    f"tidak bisa mengerjakan task GUI airdrop")
            if "delegation" in ts:
                err(f"{rel}: worker '{name}' punya toolset 'delegation' — worker "
                    f"adalah leaf; mencabutnya membuat batas leaf struktural")
        # Entri duplikat lolos dari YAML tanpa error, jadi harus diperiksa di sini.
        # Pernah terjadi: `todo` dan `delegation` terdaftar dua kali karena sebuah
        # suntingan menyisipkan daftar baru di atas baris komentar yang memisahkan
        # entri lama. Tidak merusak, tapi membuat config bohong tentang isinya.
        if len(ts) != len(set(ts)):
            dobel = sorted({x for x in ts if ts.count(x) > 1})
            err(f"{rel}: toolset terdaftar lebih dari sekali: {', '.join(dobel)}")
        # `hermes-cli` memuat seluruh _HERMES_CORE_TOOLS = 53 tool (toolsets.py:478-481),
        # termasuk 14 kanban + 4 Home Assistant yang tak dipakai airdrop farming.
        # Semuanya masuk skema tool di SETIAP putaran.
        if "hermes-cli" in ts:
            err(f"{rel}: '{name}' masih memuat toolset 'hermes-cli' — itu menarik "
                f"53 tool inti (termasuk kanban/homeassistant/tts) ke setiap putaran")

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
    orch = REPO / "config/hermes/profiles/pekerja-koordinator/config.yaml"
    if not orch.exists():
        err("profil pekerja-koordinator tidak ada — tidak ada pintu masuk Telegram")
        return
    data = yaml.safe_load(orch.read_text()) or {}

    ts = data.get("toolsets") or []
    # HANYA "delegation". "delegate_task" adalah NAMA TOOL di dalam toolset itu
    # (toolsets.py: "delegation": {"tools": ["delegate_task"]}), bukan id
    # toolset. Pemeriksaan lama menuntut keduanya, sehingga justru memaksa
    # nilai yang tidak valid masuk ke config.
    if "delegation" not in ts:
        err("pekerja-koordinator: toolset 'delegation' tidak ada — tidak bisa mendelegasikan")
    if "delegate_task" in ts:
        err("pekerja-koordinator: 'delegate_task' dipakai sebagai id toolset. "
            "Id-nya 'delegation'; 'delegate_task' adalah nama tool di dalamnya.")

    # Guard regresi: pintu masuk Telegram adalah satu-satunya jalan operator
    # memberi task. Kalau "delegation" hilang dari platform_toolsets.telegram,
    # orchestrator menerima pesan tapi TIDAK BISA mendelegasikan ke worker mana
    # pun — dan kegagalannya sunyi, karena tool-nya memang tidak pernah ada.
    pt = (data.get("platform_toolsets") or {}).get("telegram")
    if isinstance(pt, list) and "delegation" not in pt:
        err("pekerja-koordinator: platform_toolsets.telegram tanpa 'delegation' — "
            "orchestrator bisa menerima task dari Telegram tapi tidak bisa "
            "mendelegasikannya ke worker")

    d = data.get("delegation")
    if not isinstance(d, dict):
        err("pekerja-koordinator: blok 'delegation' tidak ada")
    else:
        if d.get("orchestrator_enabled") is not True:
            err("pekerja-koordinator: delegation.orchestrator_enabled bukan true")
        depth = d.get("max_spawn_depth")
        if depth != 1:
            warn(f"pekerja-koordinator: delegation.max_spawn_depth={depth}. "
                 f"Nilai >1 mengizinkan delegasi berantai — biaya bisa meledak.")
        if d.get("subagent_auto_approve") is True:
            err("pekerja-koordinator: subagent_auto_approve=true — child bisa "
                "menyetujui aksinya sendiri tanpa manusia")

    # Pintu masuk publik tidak boleh punya shell
    pt = data.get("platform_toolsets") or {}
    tg = pt.get("telegram") or []
    if "terminal" in tg:
        err("pekerja-koordinator: platform_toolsets.telegram memuat 'terminal' — "
            "pintu masuk Telegram tidak boleh punya akses shell")

    # Setiap worker harus disebut di routing orchestrator. Profil yang terpasang
    # tapi tidak pernah dirutekan tidak akan pernah dipakai — pekerja-x sempat
    # lolos dari sini karena ditambahkan ke setup.sh tapi tidak ke SOUL.md.
    soul = REPO / "config/hermes/profiles/pekerja-koordinator/SOUL.md"
    if soul.exists():
        checks += 1
        soul_text = soul.read_text()
        workers = [p.name for p in sorted((REPO / "config/hermes/profiles").iterdir())
                   if p.is_dir() and p.name != "pekerja-koordinator"]
        for w in workers:
            if f"`{w}`" not in soul_text:
                err(f"pekerja-koordinator/SOUL.md tidak merutekan ke '{w}' — "
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
    # Skill boleh terpasang lewat DUA jalur: SKILLS=() (HERMES_HOME utama) atau
    # PROFILE_SKILLS[<profil>] (per worker). Sejak pool global dihapus, sebagian
    # besar skill hanya ada di PROFILE_SKILLS — dan itu memang tujuannya.
    m_map0 = re.search(r"declare -A PROFILE_SKILLS=\((.*?)\n\)", text, re.DOTALL)
    _mapped0 = set()
    if m_map0:
        for _s in re.findall(r"\[([\w-]+)\]=\"([^\"]*)\"", m_map0.group(1)):
            _mapped0.update(_s[1].split())
    for missing in sorted(on_disk_skills - listed_skills - _mapped0):
        err(f"setup.sh: skill '{missing}' ada di disk tapi tidak ada di SKILLS=() "
            f"maupun PROFILE_SKILLS — tidak akan pernah terpasang")
    for ghost in sorted(listed_profiles - on_disk_profiles):
        err(f"setup.sh: PROFILES=() menyebut '{ghost}' tapi direktorinya tidak ada")
    for ghost in sorted(listed_skills - on_disk_skills):
        err(f"setup.sh: SKILLS=() menyebut '{ghost}' tapi direktorinya tidak ada")

    print(f"  · {len(on_disk_profiles)} profil, {len(on_disk_skills)} skill — semuanya tercakup")

    # ---- Pemetaan skill per profil -----------------------------------------
    # Tanpa pemetaan, setup.sh menyalin semua skill ke semua profil dan Hermes
    # tidak membatasi apa yang boleh dipanggil — pekerja-discord bisa
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
        # Koordinator tidak punya tool browser, jadi memberinya prosedur browser
        # hanya menghasilkan halusinasi langkah.
        if p != "pekerja-koordinator" and "browser-operation" not in names:
            err(f"setup.sh: PROFILE_SKILLS[{p}] tidak menyertakan 'browser-operation' "
                f"— protokol browser wajib ada di setiap worker")
    for orphan in sorted(on_disk_skills - mapped_skills - listed_skills):
        err(f"setup.sh: skill '{orphan}' tidak dipetakan ke profil mana pun dan "
            f"tidak ada di SKILLS=() — tidak akan pernah terpasang")

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




def _own_extension_js() -> list:
    """JS ekstensi MILIK KITA, bukan yang diunduh dari toko.

    `extensions/installed/` di-gitignore dan berisi kode pihak ketiga: wallet
    resmi (MetaMask/OKX/Phantom) yang diunduh `agentdrop extensions`. OKX
    misalnya membawa string CJK di bundle minified-nya, dan itu memang milik
    mereka -- bukan cacat kita. Menyisirnya membuat validator melaporkan 5
    error yang tidak bisa diperbaiki siapa pun, dan menutupi error yang nyata.
    """
    akar = REPO / "extensions"
    if not akar.exists():
        return []
    return [f for f in akar.rglob("*.js")
            if "installed" not in f.relative_to(akar).parts]


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
              list(_own_extension_js()) + \
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




# Skill bawaan Hermes yang dilarang AgentDrop. Harus ada di `skills.disabled`
# pada config utama DAN setiap profil: profil adalah HERMES_HOME terpisah yang
# tidak mewarisi config utama, jadi menaruhnya di satu tempat saja tidak
# berpengaruh pada worker mana pun.
#
# Toolset-nya sudah mati (terminal/code_execution/computer_use tidak pernah
# diaktifkan), tapi manifest skill tetap masuk ke konteks agent — jadi agent
# bisa memutuskan mengikuti prosedur yang kita larang, dan 77 dokumen prosedur
# asing yang terbaca adalah permukaan prompt-injection yang tidak perlu.
SKILL_BAWAAN_DILARANG = {
    "computer-use",          # mengendalikan desktop di luar browser
    "xurl",                  # X/Twitter lewat CLI, melewati log audit
    "python-debugpy",        # butuh shell
    "node-inspect-debugger", # butuh shell
    "claude-code",           # delegasi coding, butuh shell
    "codex",                 # delegasi coding, butuh shell
    "opencode",              # delegasi coding, butuh shell
    "himalaya",              # email operator
    "google-workspace",      # akun Google operator
}
# hermes-agent adalah satu-satunya isi ESSENTIAL_SKILLS di Hermes
# (agent/skill_utils.py:443) dan dikurangkan dari daftar disabled apa pun.
SKILL_TIDAK_BOLEH_DIMATIKAN = {"hermes-agent"}


# Provider model yang harus dipakai semua config.
#
# "auto" DILARANG, dan ini bukan selera. hermes_cli/auth.py:2268 hanya memakai
# model.provider kalau nilainya ada di PROVIDER_REGISTRY (37 nama: nous,
# openai-codex, openai-api, copilot, gemini, anthropic, ...). "auto" tidak ada
# di sana, dan "openrouter" pun tidak -- openrouter ditangani early-return
# terpisah di auth.py:2262. Jadi "auto" tidak pernah menyelesaikan ke
# OpenRouter; ia jatuh ke deteksi env/auth.json.
#
# hermes_cli/config.py:2990 menulis bahayanya sendiri: merged model.provider
# default "often `auto`, which runtime resolution treats as authoritative and
# would otherwise route the model through the wrong active provider".
#
# Gejala di mesin operator: model custom tidak termuat, dashboard hanya
# menampilkan model dan provider bawaan Hermes.
MODEL_PROVIDER_WAJIB = "openrouter"
MODEL_PROVIDER_DILARANG = {"auto"}


# browser.backend WAJIB "off" di setiap config.
#
# tools/browser_use_cli.py:216 is_browser_use_cli_mode():
#   backend terisi -> mode = (backend == "browser-use")
#   backend KOSONG -> mode = (_find_cli() is not None)
# Jadi backend kosong berarti "aktifkan Browser Use kalau CLI-nya atau uvx ada
# di mesin". Docstring modul yang sama (baris 3) menulis akibatnya:
#   "When browser.backend is 'browser-use', the model gets browser_exec tool
#    INSTEAD OF default browser tools"
#
# Semua SKILL.md dan SOUL.md AgentDrop menyebut browser_navigate, browser_click,
# browser_type, browser_scroll. Kalau mode Browser Use aktif, tool-tool itu
# tidak terdaftar dan digantikan satu browser_exec -- seluruh prosedur agent
# merujuk tool yang tidak ada.
BROWSER_BACKEND_WAJIB = "off"


# Pola `hermes --profile <p> gateway <verb>` DILARANG di seluruh kode shell.
#
# config/hermes/config.yaml menyalakan gateway.multiplex_profiles: true, jadi
# gateway DEFAULT adalah satu-satunya proses inbound untuk semua profil.
# hermes_cli/gateway.py:6131 menolak gateway per profil dengan
#   "The default gateway is running as a profile multiplexer and already
#    serves profile '<p>'."
# dan komentar di modul itu menyebutnya "always a misconfiguration".
#
# Hermes' own dashboard membuat kesalahan ini (web_server.py:4815
# _gateway_subcommand menyusun _profile_cli_args(profile) + ["gateway", verb]),
# jadi kode kita tidak boleh mengulanginya.
_GATEWAY_PER_PROFIL = re.compile(
    r"hermes\b[^|;&\n]*--profile[^|;&\n]*\bgateway\b"
    r"|\bgateway\b[^|;&\n]*--profile",
)


# `~` DILARANG di dalam command hook config.
#
# agent/shell_hooks.py:555 memang memanggil os.path.expanduser(spec.command),
# tapi expanduser hanya meng-expand `~` di AWAL string. Command hook berbentuk
# `python3 ~/.agentdrop/agent-hooks/audit-log.py` -- `~` ada di token KEDUA,
# jadi ia lolos apa adanya. split_command_line() lalu memakai shlex.split dan
# subprocess dipanggil dengan shell=False (baris 581), jadi tidak ada shell yang
# meng-expand-nya. Python memperlakukannya sebagai path RELATIF terhadap cwd
# agent, dan hasilnya di mesin operator:
#
#   python3: can't open file '/home/<user>/AgentDrop/~/.agentdrop/agent-hooks/
#   audit-log.py': [Errno 2] No such file or directory
#
# Hook yang gagal membuat SEMUA tool browser ikut gagal. Karena repo tidak bisa
# hardcode /home/<user> (config di-commit untuk semua orang), installer merender
# placeholder __AGENTDROP_HOOK__ menjadi path absolut.
_HOOK_TILDE = re.compile(r'command:\s*["\']?[^"\'\n]*\s~/')


# snapshot_threshold TIDAK BOLEH di atas default Hermes tanpa alasan.
#
# browser_tool.py:290 DEFAULT_SNAPSHOT_THRESHOLD = 15000, dan komentar di
# browser_tool.py:285-289 menjelaskan bahwa angka ini adalah "per-page budget"
# yang masuk ke KONTEKS MODEL di setiap snapshot. Satu task browser melakukan
# banyak snapshot, dan tiap snapshot dikirim ulang di setiap putaran LLM
# sesudahnya -- jadi menaikkannya dibayar berkali-kali.
#
# Repo ini pernah menaikkannya ke 20000 dengan alasan "halaman dashboard
# airdrop panjang", tanpa mengukur apa pun. Operator kemudian melaporkan
# semuanya terasa lambat. Snapshot yang terpotong tetap disimpan utuh ke
# cache/web dan bisa dibaca lewat read_file, jadi menaikkan threshold hampir
# tidak pernah jawabannya.
SNAPSHOT_THRESHOLD_MAX = 15000


def check_custom_providers_block(configs: list[Path]) -> None:
    """Setiap config harus punya blok custom_providers yang bisa dirender.

    `hermes model` menulis custom_providers ke config profil DEFAULT:
    hermes_cli/main.py:4957 memanggil save_config(cfg), dan save_config
    menulis ~/.hermes/config.yaml (config.py:4023). Profil worker punya
    config.yaml sendiri, jadi tanpa blok ini setelan provider custom operator
    TIDAK PERNAH sampai ke worker mana pun — worker tetap ke provider lama.

    Itu sudah terjadi: operator menyetel DeepSeek lewat `hermes model`, lalu
    pekerja-daftar tetap meminta anthropic/claude-sonnet-4 ke OpenRouter.
    """
    global checks
    print("\n[30] Blok custom_providers")
    for cfg in configs:
        if not cfg.exists():
            continue
        checks += 1
        nama = ("config utama" if cfg.parent.name == "hermes" else cfg.parent.name)
        txt = cfg.read_text()
        if "custom_providers:" not in txt:
            err(f"{nama}: tidak punya blok custom_providers. `hermes model` "
                f"hanya menulis ke config profil default "
                f"(hermes_cli/main.py:4957 -> config.py:4023), jadi tanpa blok "
                f"ini provider custom tidak pernah sampai ke worker.")
            continue
        # Blok harus punya field yang dibaca Hermes.
        kurang = [k for k in ("base_url", "key_env", "api_mode", "models")
                  if k not in txt.split("custom_providers:", 1)[1][:600]]
        if kurang:
            err(f"{nama}: blok custom_providers kurang field {kurang}. Hermes "
                f"membaca name/base_url/key_env/api_mode/models "
                f"(config.py:1458-1577).")
        else:
            print(f"  · {nama}: blok lengkap")

    # install.sh harus membuang blok itu saat provider bukan custom.
    lib = REPO / "lib" / "30-hermes.sh"
    if lib.exists():
        checks += 1
        isi = lib.read_text()
        # Mencari kata "custom" saja tidak cukup — SUNTIK B membuktikan itu:
        # mengganti kondisi `[[ "$_prov" != "custom" ]]` dengan `false` tetap
        # lolos karena kedua kata masih ada di berkas. Yang harus ada adalah
        # PERBANDINGAN yang benar-benar memutuskan, dan kode yang membuang
        # bloknya.
        bandingkan = re.search(r'\[\[ "\$_prov" != "custom" \]\]', isi)
        buang = re.search(r'/\^custom_providers:/', isi)
        if not bandingkan or not buang:
            err("lib/30-hermes.sh tidak membuang blok custom_providers saat "
                "provider bukan 'custom'. Harus ada perbandingan "
                '[[ "$_prov" != "custom" ]] dan kode awk yang menghapus blok '
                "itu. Tanpa itu config berisi provider hantu dengan base_url "
                "kosong dan Hermes bisa merutekan permintaan ke sana.")
        else:
            print("  · install membuang blok saat provider bukan custom")


def check_render_config() -> None:
    """install.sh harus merender ${AGENTDROP_*} menjadi nilai konkret.

    Runtime Hermes meng-expand ${VAR} (config.py:2723 _expand_env_vars), jadi
    agent tetap jalan walau config berisi rujukan. TAPI jalur TAMPILAN memakai
    read_user_config_raw(), yang dokumen Hermes sendiri nyatakan tidak
    melakukan ekspansi:

        "No DEFAULT_CONFIG merge, no managed-scope overlay, no ${ENV_VAR}
         expansion"        (hermes_cli/config.py:3366-3372)

    profiles.py:756 _read_config_model() memakainya, sehingga `hermes profile
    list` dan dashboard menampilkan "${AGENTDROP_MODEL_PEKERJA_X}" apa adanya.
    doctor.py juga memakainya di beberapa tempat (1507, 1747, 1795, 3217).

    Karena itu config TERPASANG harus berisi nilai konkret, dan satu-satunya
    tempat yang bisa melakukannya adalah install.sh.
    """
    global checks
    print("\n[29] Render config saat install")

    lib = REPO / "lib" / "30-hermes.sh"
    if not lib.exists():
        warn("lib/30-hermes.sh tidak ada")
        return
    isi = lib.read_text()

    checks += 1
    if "_render_config()" not in isi:
        err("lib/30-hermes.sh tidak punya fungsi _render_config. Tanpa itu "
            "config terpasang berisi ${AGENTDROP_*} mentah dan Hermes "
            "menampilkannya apa adanya di `hermes profile list` maupun "
            "dashboard, karena jalur tampilan memakai read_user_config_raw() "
            "yang tidak meng-expand ${VAR} (config.py:3366-3372).")
    else:
        print("  · fungsi _render_config ada")

    # Kedua jalur harus memakainya: config utama DAN tiap profil.
    checks += 1
    pakai = len(re.findall(r'^\s*_render_config "', isi, re.M))
    if pakai < 2:
        err(f"_render_config hanya dipanggil {pakai} kali. Harus dua: config "
            f"utama (~/.hermes/config.yaml) dan tiap profil "
            f"(~/.hermes/profiles/*/config.yaml). Kalau hanya satu, sisi yang "
            f"lain tetap tampil sebagai ${{AGENTDROP_*}} di dashboard.")
    else:
        print(f"  · dipanggil {pakai}x (config utama + profil)")

    # cp mentah ke config.yaml tidak boleh tersisa.
    checks += 1
    if re.search(r'cp "\$REPO_ROOT/config/hermes/config\.yaml"', isi):
        err("lib/30-hermes.sh masih menyalin config utama dengan `cp` mentah. "
            "Gunakan _render_config supaya ${AGENTDROP_*} menjadi nilai "
            "konkret.")
    else:
        print("  · tidak ada `cp` mentah untuk config.yaml")


def check_custom_base_url_trap() -> None:
    """CUSTOM_BASE_URL tidak dibaca Hermes; jangan biarkan dokumen menyuruh memakainya.

    Jebakan ini nyata dan sudah menimpa operator: .env.example dulu berkata
    "Set model.base_url in config.yaml to the same origin", jadi operator
    mengisi CUSTOM_BASE_URL dan endpoint-nya tidak pernah dipakai.

    Dari sumber:
      - hermes_cli/models.py:4080   api_key diambil dari CUSTOM_API_KEY
      - hermes_cli/models.py:2836   _get_custom_base_url() membaca
                                    model_cfg.get("base_url") dari config.yaml
    Jadi CUSTOM_API_KEY berpengaruh, CUSTOM_BASE_URL tidak. base_url harus
    masuk lewat AGENTDROP_BASE_URL karena model.base_url merujuk variabel itu.
    """
    global checks
    print("\n[28] Jebakan CUSTOM_BASE_URL")

    envx = REPO / ".env.example"
    if envx.exists():
        checks += 1
        txt = envx.read_text()
        # Dokumen tidak boleh menyuruh menyetel base_url di config.yaml,
        # karena config.yaml sekarang hanya merujuk .env.
        buruk = re.search(
            r"^\s*#.*Set model\.base_url in config\.yaml", txt, re.M)
        if buruk:
            err(".env.example masih menyuruh menyetel model.base_url di "
                "config.yaml. Sejak model dipindah ke .env, config.yaml hanya "
                "merujuk ${AGENTDROP_BASE_URL*}; instruksi itu membuat operator "
                "mengisi tempat yang tidak dibaca apa pun.")
        if "CUSTOM_BASE_URL=" in txt and "TIDAK" not in txt.split(
                "CUSTOM_BASE_URL=")[0][-2000:]:
            err(".env.example menyediakan CUSTOM_BASE_URL tanpa menjelaskan "
                "bahwa Hermes tidak membacanya (models.py:2836 mengambil "
                "base_url dari config.yaml, bukan dari variabel ini).")
        if not buruk:
            print("  · .env.example tidak menyuruh mengubah config.yaml")

    # install.sh harus memperingatkan operator yang sudah terjebak.
    cred = REPO / "lib" / "20-credentials.sh"
    if cred.exists():
        checks += 1
        isi = cred.read_text()
        # Mencari nama variabelnya saja tidak cukup -- SUNTIK B membuktikan itu:
        # menghapus baris peringatannya tetap lolos karena "CUSTOM_BASE_URL"
        # masih muncul di komentar penjelas. Yang harus ada adalah KODE yang
        # benar-benar membaca variabel itu dan memperingatkan operator.
        baca = re.search(r'grep -E "\^CUSTOM_BASE_URL=', isi)
        peringatkan = re.search(r"Hermes TIDAK membaca CUSTOM_BASE_URL", isi)
        if not baca or not peringatkan:
            err("lib/20-credentials.sh tidak memperingatkan operator yang "
                "mengisi CUSTOM_BASE_URL. Tanpa peringatan, endpoint custom "
                "tidak pernah terpakai dan gejalanya adalah model bawaan yang "
                "tetap dipakai tanpa penjelasan. Harus ada kode yang membaca "
                "variabel itu (grep ^CUSTOM_BASE_URL=) dan mencetak "
                "peringatannya.")
        else:
            print("  · install memperingatkan CUSTOM_BASE_URL yang tidak terpakai")


def check_snapshot_budget(configs: list[Path]) -> None:
    """snapshot_threshold tidak boleh melampaui default Hermes."""
    global checks
    print("\n[27] Budget snapshot")
    for cfg in configs:
        if not cfg.exists():
            continue
        checks += 1
        try:
            data = yaml.safe_load(cfg.read_text()) or {}
        except Exception as exc:
            err(f"{cfg.relative_to(REPO)}: YAML tidak bisa dibaca: {exc}")
            continue
        br = data.get("browser")
        if not isinstance(br, dict) or "snapshot_threshold" not in br:
            continue
        nama = ("config.yaml utama" if cfg.parent.name == "hermes"
                else cfg.parent.name)
        try:
            n = int(br["snapshot_threshold"])
        except (TypeError, ValueError):
            err(f"{nama}: snapshot_threshold = {br['snapshot_threshold']!r} "
                f"bukan angka.")
            continue
        if n > SNAPSHOT_THRESHOLD_MAX:
            err(f"{nama}: snapshot_threshold = {n}, di atas default Hermes "
                f"{SNAPSHOT_THRESHOLD_MAX} (browser_tool.py:290). Angka ini "
                f"masuk ke konteks model di SETIAP snapshot, dan satu task "
                f"browser melakukan banyak snapshot -- kenaikannya dibayar "
                f"berkali-kali. Snapshot terpotong tetap utuh di cache/web dan "
                f"bisa dibaca lewat read_file.")
        else:
            print(f"  · {nama}: {n} karakter")


def check_hook_paths() -> None:
    """Command hook tidak boleh memakai `~`; placeholder harus ada."""
    global checks
    print("\n[26] Path hook audit")
    cfgs = sorted(REPO.glob("config/hermes/**/config.yaml"))
    tilde = placeholder = 0
    for cfg in cfgs:
        checks += 1
        for i, line in enumerate(cfg.read_text().splitlines(), 1):
            s = line.strip()
            if s.startswith("#"):
                continue
            if _HOOK_TILDE.search(line):
                err(f"{cfg.relative_to(REPO)}:{i}: command hook memakai `~`. "
                    f"os.path.expanduser (agent/shell_hooks.py:555) hanya "
                    f"meng-expand `~` di awal string, dan subprocess dijalankan "
                    f"dengan shell=False, jadi `~` di tengah command menjadi "
                    f"path relatif terhadap cwd agent dan hook gagal -- "
                    f"memblokir semua tool browser. Pakai placeholder "
                    f"__AGENTDROP_HOOK__ yang dirender install.sh jadi absolut.")
                tilde += 1
            if "__AGENTDROP_HOOK__" in line:
                placeholder += 1
    # Placeholder harus benar-benar dirender installer, bukan dibiarkan.
    checks += 1
    sh = (REPO / "lib" / "30-hermes.sh")
    body = sh.read_text() if sh.exists() else ""
    if placeholder and "__AGENTDROP_HOOK__" not in body:
        err(f"lib/30-hermes.sh tidak merender __AGENTDROP_HOOK__, padahal "
            f"{placeholder} baris config memakainya. Hook akan memanggil path "
            f"bernama harfiah '__AGENTDROP_HOOK__' dan gagal.")
    elif placeholder:
        print(f"  · {placeholder} baris hook memakai placeholder, dirender "
              f"oleh lib/30-hermes.sh")
    if tilde == 0 and placeholder == 0:
        print("  · tidak ada command hook")


def check_no_profile_gateway() -> None:
    """Tidak boleh ada `hermes --profile X gateway ...` di kode shell."""
    global checks
    print("\n[25] Gateway per profil")
    shell = sorted(REPO.glob("scripts/*.sh")) + sorted(REPO.glob("lib/*.sh"))
    for extra in ("install.sh", "agentdrop"):
        f = REPO / extra
        if f.exists():
            shell.append(f)
    kena = 0
    for f in shell:
        checks += 1
        for i, line in enumerate(f.read_text().splitlines(), 1):
            s = line.strip()
            if s.startswith("#"):
                continue          # komentar yang MELARANG pola ini justru bagus
            if _GATEWAY_PER_PROFIL.search(line):
                err(f"{f.relative_to(REPO)}:{i}: menjalankan gateway dengan "
                    f"--profile. gateway.multiplex_profiles: true membuat "
                    f"gateway default satu-satunya proses inbound; Hermes "
                    f"menolak gateway per profil (gateway.py:6131). Pakai "
                    f"`hermes gateway restart` tanpa --profile. Baris: {s}")
                kena += 1
    if kena == 0:
        print("  · tidak ada pemanggilan gateway per profil")


def check_browser_backend(configs: list[Path]) -> None:
    """browser.backend harus 'off' eksplisit, bukan kosong."""
    global checks
    print("\n[24] Backend browser")
    for cfg in configs:
        if not cfg.exists():
            continue
        checks += 1
        try:
            data = yaml.safe_load(cfg.read_text()) or {}
        except Exception as exc:
            err(f"{cfg.relative_to(REPO)}: YAML tidak bisa dibaca: {exc}")
            continue
        br = data.get("browser")
        nama = ("config.yaml utama" if cfg.parent.name == "hermes"
                else cfg.parent.name)
        if not isinstance(br, dict):
            err(f"{nama}: tidak ada blok `browser:` -- worker tidak punya "
                f"akses browser sama sekali.")
            continue
        if "backend" not in br:
            err(f"{nama}: browser.backend tidak diset. Kosong berarti Hermes "
                f"memutuskan sendiri (tools/browser_use_cli.py:216): kalau CLI "
                f"browser-use atau uvx terpasang, browser_* digantikan satu "
                f"browser_exec dan semua SKILL.md kita merujuk tool yang tidak "
                f"ada. Set backend: \"{BROWSER_BACKEND_WAJIB}\".")
            continue
        be = br["backend"]
        # YAML 1.1 mem-parse `off` tanpa kutip sebagai False -- justru itu yang
        # dimaksud BACKEND_DISABLED di browser_use_cli.py:181, jadi False sah.
        if be is False:
            be = "off"
        if str(be).strip().lower() != BROWSER_BACKEND_WAJIB:
            err(f"{nama}: browser.backend = {be!r}, diharapkan "
                f"\"{BROWSER_BACKEND_WAJIB}\". Nilai lain mengganti tool "
                f"browser_* yang dipakai semua SKILL.md kita.")
        else:
            cdp = str(br.get("cdp_url") or "")
            if not cdp.startswith("http://127.0.0.1"):
                err(f"{nama}: browser.cdp_url = {cdp!r} bukan loopback. CDP "
                    f"adalah remote control penuh atas browser yang memegang "
                    f"wallet.")
            else:
                print(f"  · {nama}: backend=off, cdp_url={cdp}")


def check_model_provider(configs: list[Path]) -> None:
    """model.provider harus eksplisit, bukan 'auto', di setiap config."""
    global checks
    print("\n[23] Provider model")
    for cfg in configs:
        if not cfg.exists():
            continue
        checks += 1
        try:
            data = yaml.safe_load(cfg.read_text()) or {}
        except Exception as exc:
            err(f"{cfg.relative_to(REPO)}: YAML tidak bisa dibaca: {exc}")
            continue
        model = data.get("model")
        nama = ("config.yaml utama" if cfg.parent.name == "hermes"
                else cfg.parent.name)
        if not isinstance(model, dict):
            err(f"{nama}: tidak ada blok `model:` berbentuk mapping -- model "
                f"worker tidak akan termuat dari config ini.")
            continue
        prov = str(model.get("provider") or "").strip()
        # Sesudah model dipindah ke .env, nilai di config adalah rujukan
        # ${AGENTDROP_*}, bukan literal. Yang harus diperiksa berubah: bukan
        # "provider-nya openrouter", tapi "rujukannya benar dan .env mengisinya".
        # Memaksa literal di sini akan mengunci operator ke satu provider dan
        # mengembalikan cacat lama: install ulang menghapus setelan custom.
        # Rujukan per worker: ${AGENTDROP_PROVIDER_PEKERJA_X}. Bentuk umumnya
        # ${AGENTDROP_PROVIDER} atau ${AGENTDROP_PROVIDER_<WORKER>}.
        _m_prov = re.fullmatch(r"\$\{AGENTDROP_PROVIDER(?:_([A-Z0-9_]+))?\}", prov)
        if _m_prov:
            _suf = f"_{_m_prov.group(1)}" if _m_prov.group(1) else ""
            _label = _m_prov.group(1) or "global"
            dflt = str(model.get("default") or "").strip()
            base = str(model.get("base_url") or "").strip()
            mtok = str(model.get("max_tokens") or "").strip()
            if dflt != "${AGENTDROP_MODEL" + _suf + "}":
                err(f"{nama}: model.provider merujuk "
                    f"${{AGENTDROP_PROVIDER{_suf}}} tapi model.default = "
                    f"{dflt!r}, bukan ${{AGENTDROP_MODEL{_suf}}}. Provider dan "
                    f"model harus berasal dari tingkat yang sama (global atau "
                    f"worker ini), kalau tidak worker memakai provider lain "
                    f"dari yang dikonfigurasi untuknya.")
            elif base != "${AGENTDROP_BASE_URL" + _suf + "}":
                err(f"{nama}: model.provider merujuk ${{AGENTDROP_PROVIDER}} "
                    f"tapi model.base_url = {base!r}, bukan "
                    f"${{AGENTDROP_BASE_URL{_suf}}}. base_url yang di-hardcode "
                    f"akan mengarahkan provider custom ke endpoint yang salah.")
            elif mtok != "${AGENTDROP_MAX_TOKENS" + _suf + "}":
                err(f"{nama}: model.max_tokens = {mtok!r}, bukan "
                    f"${{AGENTDROP_MAX_TOKENS{_suf}}}. Tanpa nilai ini Hermes "
                    f"memakai ceiling native model -- claude-sonnet-4 bernilai "
                    f"64.000 (agent/anthropic_adapter.py:175) -- dan OpenRouter "
                    f"menolaknya dengan HTTP 402 pada akun ber-kredit terbatas. "
                    f"Agent gagal di panggilan PERTAMA, bukan lambat.")
            else:
                envx = (REPO / ".env.example").read_text()
                kurang = [v for v in ("AGENTDROP_MODEL", "AGENTDROP_PROVIDER",
                                      "AGENTDROP_BASE_URL", "AGENTDROP_MAX_TOKENS")
                          if not re.search(rf"^{v}=.+", envx, re.M)]
                if kurang:
                    err(f".env.example tidak memberi default untuk {kurang}. "
                        f"Hermes membiarkan variabel yang tidak ada VERBATIM "
                        f"(hermes_cli/config.py:2767), jadi model.default akan "
                        f"jadi string '${{AGENTDROP_MODEL}}' apa adanya dan "
                        f"setiap worker gagal.")
                else:
                    print(f"  · {nama}: model dari .env "
                          f"(${{AGENTDROP_MODEL{_suf}}} / "
                          f"${{AGENTDROP_MAX_TOKENS{_suf}}}) [{_label}]")
            continue
        if prov in MODEL_PROVIDER_DILARANG:
            err(f"{nama}: model.provider = \"{prov}\". Nilai itu tidak pernah "
                f"menyelesaikan ke OpenRouter (hermes_cli/auth.py:2268 hanya "
                f"menerima nama yang ada di PROVIDER_REGISTRY, dan \"{prov}\" "
                f"tidak ada di sana), jadi model custom tidak termuat dan UI "
                f"hanya menampilkan model bawaan Hermes. Pakai "
                f"\"{MODEL_PROVIDER_WAJIB}\".")
        elif prov != MODEL_PROVIDER_WAJIB:
            err(f"{nama}: model.provider = \"{prov or '<kosong>'}\", diharapkan "
                f"\"{MODEL_PROVIDER_WAJIB}\". base_url kita menunjuk "
                f"https://openrouter.ai/api/v1, jadi provider lain akan "
                f"merutekan permintaan ke tempat yang salah.")
        else:
            dflt = str(model.get("default") or "").strip()
            if "/" not in dflt:
                err(f"{nama}: model.default = \"{dflt}\" tidak berbentuk "
                    f"provider/model. OpenRouter menolak slug tanpa prefix.")
            else:
                print(f"  · {nama}: {dflt} lewat {prov}")


def check_skills_disabled(configs: list[Path]) -> None:
    """Setiap config harus mematikan skill bawaan Hermes yang kita larang."""
    global checks
    print("\n[22] Skill bawaan Hermes yang dilarang")
    # `configs` dari main() sudah memuat config/hermes/config.yaml (glob
    # `config/hermes/**/config.yaml`), jadi tidak perlu ditambahkan lagi —
    # versi pertama fungsi ini melakukannya dan mencetak config utama dua kali.
    for cfg in configs:
        if not cfg.exists():
            continue
        checks += 1
        try:
            data = yaml.safe_load(cfg.read_text()) or {}
        except Exception as exc:
            err(f"{cfg.relative_to(REPO)}: YAML tidak bisa dibaca: {exc}")
            continue
        mati = set((data.get("skills") or {}).get("disabled") or [])
        nama = ("config.yaml utama" if cfg.parent.name == "hermes"
                else cfg.parent.name)
        kurang = sorted(SKILL_BAWAAN_DILARANG - mati)
        if kurang:
            err(f"{nama}: skills.disabled tidak memuat {kurang}. Skill bawaan "
                f"Hermes ini tetap muncul di manifest agent walau toolsetnya "
                f"mati — agent bisa mencoba mengikuti prosedurnya.")
        salah = sorted(mati & SKILL_TIDAK_BOLEH_DIMATIKAN)
        if salah:
            err(f"{nama}: {salah} ada di skills.disabled, padahal itu "
                f"ESSENTIAL_SKILLS Hermes — Hermes mengabaikannya, jadi "
                f"barisnya hanya memberi rasa aman palsu.")
        if not kurang and not salah:
            print(f"  · {nama}: {len(mati)} skill bawaan dimatikan")


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


def check_knowledge_references() -> None:
    """Rujukan ke knowledge/*.md harus menunjuk berkas yang benar-benar ada.

    Ini kelas bug yang sama dengan SOUL.md yang menyuruh agent menjalankan
    tools/signing_policy.py yang sudah dihapus: agent membaca "lihat
    knowledge/patterns/x.md", berkasnya tidak ada, lalu agent berimprovisasi
    tanpa pengetahuan yang seharusnya memandunya.
    """
    global checks
    akar = REPO / "knowledge"
    pola = re.compile(r"knowledge/[A-Za-z0-9_./-]+\.md")

    sumber = sorted(
        list((REPO / "config" / "hermes").rglob("SOUL.md")) +
        list((REPO / "skills").rglob("SKILL.md")) +
        list(akar.rglob("*.md"))
    )
    for f in sumber:
        checks += 1
        for m in pola.finditer(f.read_text()):
            if not (REPO / m.group(0)).exists():
                err(f"{f.relative_to(REPO)}: merujuk {m.group(0)} yang tidak ada")

    # knowledge/ tidak boleh kosong: workflow agent membacanya di langkah awal.
    # Kalau isinya cuma kerangka, agent melangkah tanpa pengetahuan apa pun.
    checks += 1
    isi = [x for x in akar.rglob("*.md") if x.name != "README.md"]
    if len(isi) < 4:
        err(f"knowledge/ hanya punya {len(isi)} berkas isi — workflow agent "
            f"merujuk format-task, siklus, dan tanda-bahaya di langkah awal")


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
                  # Sesudah placeholder diperkenalkan (lihat check_hook_paths),
                  # nama berkas tidak lagi muncul di config repo: yang ada
                  # adalah __AGENTDROP_HOOK__, dirender lib/30-hermes.sh menjadi
                  # path absolut saat install. Jadi yang sah ada dua bentuk.
                  if "audit-log.py" not in cmd and "__AGENTDROP_HOOK__" not in cmd:
                      err(f"{name}: hooks.{ev} tidak menunjuk audit-log.py "
                          f"maupun placeholder __AGENTDROP_HOOK__: {cmd!r}")

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


def check_model_vars_and_delegation(configs: list[Path]) -> None:
    global checks
    print("\n[31] Tidak ada variabel model per-worker")
    # Keputusan operator: lapisan per-worker DIHAPUS. Alasannya spesifik dan
    # sudah terjadi di mesin operator:
    #
    # config.yaml tiap profil merujuk ${AGENTDROP_MODEL_WORKER_X}. Variabel itu
    # TIDAK PERNAH ada di .env.example -- hanya dibuat saat install. Kalau satu
    # langkah install terlewat, Hermes membiarkan rujukan itu verbatim
    # (config.py:2767: "missing vars stay verbatim"), jadi model.default menjadi
    # string "${AGENTDROP_MODEL_WORKER_X}" apa adanya. Endpoint custom terpasang
    # di config tapi tidak pernah dipakai, tanpa error yang jelas.
    #
    # Satu variabel global tidak punya cara gagal seperti itu.
    for cfg in configs:
        if not cfg.exists():
            continue
        checks += 1
        isi = cfg.read_text()
        m = re.search(r"\$\{AGENTDROP_(?:MODEL|PROVIDER|BASE_URL|MAX_TOKENS|API_MODE)_PEKERJA_[A-Z_]+\}", isi)
        if m:
            # Potong "${" (2 karakter) dan buang "_PEKERJA_<NAMA>" untuk
            # menampilkan bentuk global yang seharusnya dipakai.
            _global = "${" + m.group(0)[2:].split("_PEKERJA_")[0] + "}"
            err(f"{cfg.relative_to(REPO)}: masih merujuk variabel per-worker "
                f"{m.group(0)}. Semua profil harus memakai variabel global "
                f"{_global}. Variabel per-worker tidak ada di .env.example, "
                f"jadi kalau install terlewat rujukannya tetap verbatim "
                f"(config.py:2767) dan endpoint tidak pernah dipakai.")

    print("\n[33] K14 — signing otomatis, tidak ada kelas human:wallet")
    # Keputusan operator 2026-08-29 (K14). Aturan ini ada karena batas lama
    # tersebar di 4 SOUL.md dan 4 SKILL.md; mengubah sebagian saja akan
    # meninggalkan pekerja yang berhenti di popup sementara yang lain tidak,
    # dan itu tidak terlihat dari luar sampai operator menemukan campaign yang
    # macet di tengah.
    #
    # Yang dicari adalah POLA YANG BERTINDAK, bukan nama kelasnya: kalimat yang
    # menyuruh agent berhenti di popup, atau yang menugaskan operator menekan
    # Confirm. Mencari string "human:wallet" saja tidak cukup — kelas itu bisa
    # dihapus dari tabel sementara kalimat "berhenti di situ" tetap ada.
    POLA_LARANGAN = [
        (r"berhenti di situ", "menyuruh agent berhenti di popup"),
        (r"stop di situ", "menyuruh agent berhenti di popup"),
        (r"operator yang menekan", "menugaskan operator menekan Confirm"),
        (r"operator yang menandatangani", "menugaskan operator menandatangani"),
        (r"manusia tanda tangan", "menugaskan manusia menandatangani"),
        (r"berhenti dan menyerahkan", "menyuruh agent menyerahkan di popup"),
        (r"tidak pernah menandatangani", "melarang agent menandatangani"),
    ]
    sasaran = sorted((REPO / "config" / "hermes" / "profiles").glob("*/SOUL.md"))
    sasaran += sorted((REPO / "skills").glob("*/SKILL.md"))
    for f in sasaran:
        checks += 1
        for pola, sebab in POLA_LARANGAN:
            if re.search(pola, f.read_text()):
                err(f"{f.relative_to(REPO)}: masih {sebab}. K14 — signing "
                    f"otomatis untuk semua pekerja; kelas human:wallet dihapus. "
                    f"Yang tetap human hanya CAPTCHA, 2FA, OTP, KYC.")

    print("\n[37] Setiap worker punya SATU skill yang tidak dimiliki worker lain")
    # Operator meminta batas cakupan yang tegas: "setiap agent punya spesifikasi
    # dan scope tugasnya masing-masing, tidak boleh bercampur". Pemetaan skill
    # adalah salah satu dari dua penegak batas itu (satunya lagi toolset).
    #
    # Tanpa aturan ini dua profil sempat berbagi seluruh isi skill-nya:
    # pekerja-riset hanya punya airdrop-analyzer (yang juga dipegang koordinator)
    # dan pekerja-daftar hanya punya airdrop-intake (sama). Keduanya tidak punya
    # satu pun prosedur yang khusus miliknya, jadi tidak ada yang membedakan
    # pekerjaan mereka selain kalimat di SOUL.md.
    checks += 1
    _p30 = REPO / "lib" / "30-hermes.sh"
    isi_lib = _p30.read_text() if _p30.exists() else ""
    m_pmap = re.search(r"declare -A PROFILE_SKILLS=\((.*?)^\)", isi_lib, re.M | re.S)
    if not m_pmap:
        err("lib/30-hermes.sh: PROFILE_SKILLS tidak ditemukan")
    else:
        peta = {k: set(v.split())
                for k, v in re.findall(r'\[([\w-]+)\]="([^"]*)"', m_pmap.group(1))}
        for prof, punya in sorted(peta.items()):
            if prof == "pekerja-koordinator":
                continue          # koordinator memang memegang pintasan delegasi
            lain = set().union(*[v for k, v in peta.items() if k != prof]) if len(peta) > 1 else set()
            khusus = punya - lain
            if not khusus:
                err(f"lib/30-hermes.sh: '{prof}' tidak punya satu pun skill khusus — "
                    f"seluruh skill-nya dimiliki profil lain, jadi tidak ada yang "
                    f"membedakan cakupan kerjanya")
            else:
                checks += 1

    print("\n[38] Skill bawaan Hermes ditolak di home utama dan setiap profil")
    # Hermes mengirim 58 skill bawaan (13 kategori di hermes-agent/skills/), dan
    # sync_skills() menyuntikkannya ke HERMES_HOME saat install, `hermes update`,
    # maupun sync langsung. Tanpa penolakan, worker yang tadinya membawa 3 skill
    # bisa berakhir membawa 61 -- dan manifest skill masuk system prompt di
    # SETIAP putaran.
    #
    # Mekanismenya resmi: berkas `.no-bundled-skills` di root HERMES_HOME membuat
    # sync_skills() hanya men-seed ESSENTIAL_SKILLS
    # (tools/skills_sync.py:99-105, :728; agent/skill_utils.py:443).
    checks += 1
    if '.no-bundled-skills' not in isi_lib:
        err("lib/30-hermes.sh tidak pernah menulis `.no-bundled-skills`. Hermes "
            "akan menyuntikkan 58 skill bawaannya ke home utama dan ke setiap "
            "profil pada install/update berikutnya.")
    else:
        # harus ditulis untuk PROFIL (di dalam loop) dan untuk HOME UTAMA
        checks += 1
        if not re.search(r'>\s*"\$dst/\.no-bundled-skills"', isi_lib):
            err("lib/30-hermes.sh tidak menulis `.no-bundled-skills` ke direktori "
                "profil ($dst) — hanya home utama yang terlindungi")
        checks += 1
        if not re.search(r'>\s*"\$HERMES_HOME_DIR/\.no-bundled-skills"', isi_lib):
            err("lib/30-hermes.sh tidak menulis `.no-bundled-skills` ke HERMES_HOME "
                "utama — padahal home utama adalah profil default yang memegang "
                "TELEGRAM_BOT_TOKEN (profiles.py:1105)")

    print("\n[39] SOUL tidak merujuk skill yang tidak terpasang di profilnya")
    # SOUL.md adalah system prompt. Kalau ia menyuruh agent mengikuti sebuah
    # skill yang tidak disalin ke profil itu, agent memanggil skill_view untuk
    # berkas yang tidak ada -- lalu entah berhenti, entah mengarang isinya.
    #
    # Polanya sengaja sempit: hanya `<S|s>kill \`nama\`` yang dihitung sebagai
    # arahan. Versi yang mencocokkan SEMUA nama skill dalam backtick menembak
    # sebutan biasa ("`daily-executor` membaca berkas itu") yang bukan arahan
    # sama sekali.
    checks += 1
    semua_skill = {q.name for q in (REPO / "skills").iterdir() if q.is_dir()}
    for _f in sorted((REPO / "config/hermes/profiles").glob("*/SOUL.md")):
        _prof = _f.parent.name
        _punya = set(peta.get(_prof, set()))
        for _i, _b in enumerate(_f.read_text().splitlines(), 1):
            for _r in re.findall(r"[Ss]kill\s+`([a-z][a-z0-9-]+)`", _b):
                if _r in semua_skill and _r not in _punya:
                    err(f"{_f.relative_to(REPO)}:{_i} menyuruh mengikuti skill "
                        f"'{_r}' yang tidak dipetakan ke {_prof} — agent akan "
                        f"memanggil skill yang tidak ada")

    print("\n[40] Setiap SOUL menyatakan apa yang TIDAK ia kerjakan")
    # Operator: "setiap agent punya spesifikasi dan scope tugasnya masing-masing
    # khusus, tidak boleh agent a kerjakan tugas agent b". Toolset dan pemetaan
    # skill menegakkan batas itu secara struktural; SOUL menegakkannya di kepala
    # model. Tanpa keduanya agent mengambil pekerjaan worker lain dan
    # menghasilkan dua pekerjaan setengah jadi yang saling menimpa.
    #
    # Pernah terjadi: pekerja-quest dan pekerja-riset tidak punya satu pun
    # pernyataan batas, padahal keduanya paling rawan tumpang tindih.
    checks += 1
    POLA_BATAS = re.compile(
        r"(?i)(bukan (?:tugas|urusan|peran|pekerjaan) saya"
        r"|yang tidak saya lakukan|TIDAK saya kerjakan"
        r"|saya tidak (?:mengerjakan|mengeksekusi)"
        r"|TIDAK punya tool|bukan saya)")
    for _f in sorted((REPO / "config/hermes/profiles").glob("*/SOUL.md")):
        if not POLA_BATAS.search(_f.read_text()):
            err(f"{_f.relative_to(REPO)} tidak menyatakan apa yang TIDAK ia "
                f"kerjakan. Tanpa batas eksplisit, worker ini bisa mengambil "
                f"pekerjaan worker lain.")

    print("\n[41] Delapan profil seragam pada kunci yang tidak boleh berbeda")
    # Kunci-kunci ini bukan selera per worker; kalau berbeda, itu drift.
    # Pernah terjadi: pekerja-riset tidak punya `browser.record_sessions: false`
    # (jadi merekam video WebM per sesi dan menyimpannya 72 jam sementara tujuh
    # worker lain tidak), `hard_stop_enabled: false` tanpa satu pun komentar
    # penjelas, dan `warn_after` hilang di empat profil sehingga mereka memakai
    # default Hermes yang belum tentu sama.
    checks += 1
    WAJIB_SAMA = {
        ("browser", "record_sessions"): False,
        ("tool_loop_guardrails", "warnings_enabled"): True,
        ("tool_loop_guardrails", "hard_stop_enabled"): True,
        ("tool_loop_guardrails", "warn_after", "exact_failure"): 2,
        ("tool_loop_guardrails", "warn_after", "same_tool_failure"): 3,
        ("tool_loop_guardrails", "warn_after", "idempotent_no_progress"): 2,
        ("browser", "inactivity_timeout"): 1800,
        ("browser", "snapshot_threshold"): 15000,
        ("browser", "backend"): "off",
        ("agent", "disabled_toolsets"): ["terminal", "code_execution"],
    }
    for _c in sorted((REPO / "config/hermes/profiles").glob("*/config.yaml")):
        _d = yaml.safe_load(_c.read_text()) or {}
        for _jalan, _harap in WAJIB_SAMA.items():
            _simpul = _d
            for _k in _jalan:
                _simpul = (_simpul or {}).get(_k) if isinstance(_simpul, dict) else None
            if _simpul != _harap:
                err(f"{_c.relative_to(REPO)}: {'.'.join(_jalan)} = {_simpul!r}, "
                    f"seharusnya {_harap!r} di SEMUA profil")

    print("\n[36] Login dan OAuth BUKAN kelas `human`")
    # Bug yang membuat operator melaporkan "agent menentang instruksi, bilang
    # tidak bisa login / connect wallet". Akun yang dipakai agent memang dibuat
    # untuk agent dan kredensialnya tersedia, jadi login/signup/OAuth adalah
    # pekerjaannya. Yang tetap milik manusia hanya CAPTCHA, 2FA, OTP, dan
    # KYC/verifikasi identitas (keputusan Arc 28 `keep_human`).
    #
    # `login` pernah tercatat sebagai `human` di sembilan tempat berbeda, jadi
    # setiap worker menolak masuk ke akun apa pun.
    #
    # Dua pemeriksaan, dan keduanya disengaja:
    #
    #   POSITIF — setiap SOUL.md harus menyatakan secara eksplisit bahwa login
    #     adalah tugas agent. Model jauh lebih patuh pada pernyataan tegas
    #     daripada pada tidak-adanya larangan.
    #   NEGATIF — hanya pola yang TIDAK AMBIGU. Versi pertama aturan ini mencari
    #     "login" berdekatan dengan CAPTCHA/2FA/OTP/KYC, dan itu menembak lima
    #     baris yang tidak melarang apa pun: enum status, catatan tentang tab,
    #     dan bahkan baris yang justru menulis "Login BUKAN human". False
    #     failure sama berbahayanya dengan false pass, jadi keduanya harus nol.
    checks += 1
    PERNYATAAN = "Login, signup, dan OAuth"
    for f in sorted((REPO / "config/hermes/profiles").glob("*/SOUL.md")):
        if PERNYATAAN not in f.read_text():
            err(f"{f.relative_to(REPO)} tidak menyatakan bahwa login/signup/OAuth "
                f"adalah tugas agent. Tanpa pernyataan tegas, model kembali "
                f"menganggap login sebagai tugas manusia.")
    POLA_LOGIN = [
        (re.compile(r"human:oauth", re.I), "kelas `human:oauth` sudah dihapus"),
        (re.compile(r"[Jj]angan[^.\n]{0,35}login sendiri"),
         "agent dilarang login sendiri"),
        (re.compile(r"operator login", re.I), "login diserahkan ke operator"),
        (re.compile(r"OAuth[^.\n]{0,25}(?:→|->)\s*operator"),
         "OAuth diserahkan ke operator"),
        (re.compile(r"approval wallet[^.\n]{0,45}(?:manusia|human|operator)", re.I),
         "approval wallet masih diserahkan ke manusia -- melanggar K14"),
        (re.compile(r"sesi (?:login )?mati[^.\n]{0,45}hentikan", re.I),
         "sesi login mati disuruh menghentikan campaign -- padahal agent login sendiri"),
    ]
    # scripts/install-cron.sh ikut dipindai: prompt cron adalah instruksi yang
    # benar-benar dikirim ke agent, jadi ia tunduk pada aturan yang sama.
    # Sempat lolos: prompt job 09:00 masih menulis "sesi mati -> hentikan
    # campaign" padahal Arc 32 sudah menjadikan login pekerjaan agent. Aturan
    # ini hanya memindai SOUL.md dan SKILL.md, jadi kontradiksi itu tidak
    # pernah terlihat.
    berkas_prompt = sorted(
        (REPO / "config/hermes/profiles").glob("*/SOUL.md")
    ) + sorted((REPO / "skills").glob("*/SKILL.md"))
    _cron = REPO / "scripts" / "install-cron.sh"
    if _cron.exists():
        berkas_prompt = berkas_prompt + [_cron]
    for f in berkas_prompt:
        for i, baris in enumerate(f.read_text().splitlines(), 1):
            for pola, sebab in POLA_LOGIN:
                if pola.search(baris):
                    err(f"{f.relative_to(REPO)}:{i} — {sebab}: {baris.strip()[:78]}")
                    break

    print("\n[35] Peringatan restart gateway setelah install")
    # Hermes memindai skill menjadi perintah /nama-skill, tapi cache-nya hanya
    # di-refresh kalau platform atau HERMES_HOME berubah
    # (agent/skill_commands.py:565-568) -- bukan kalau isi folder skill berubah.
    #
    # Sudah dibuktikan: skill yang ditambahkan saat proses hidup tetap tidak
    # ter-resolve. Gateway yang sudah berjalan tidak akan pernah melihat skill
    # baru, jadi /riset dan /quest dibalas "Unknown command" walau skill-nya ada
    # di disk. Persis keluhan operator: "semua command unknown di telegram".
    #
    # Karena itu install.sh wajib menyuruh operator me-restart gateway, dan
    # `agentdrop status` wajib memeriksa kondisi itu. Tanpa keduanya operator
    # tidak punya cara membedakan "skill belum terpasang" dari "gateway belum
    # di-restart" -- keduanya terlihat identik di Telegram.
    inst = REPO / "install.sh"
    if inst.exists():
        checks += 1
        isi_inst = inst.read_text()
        if "agentdrop stop && agentdrop start" not in isi_inst:
            err("install.sh tidak menyuruh me-restart gateway. Skill baru tidak "
                "terlihat oleh gateway yang sudah hidup (cache di "
                "skill_commands.py:565-568 tidak di-refresh oleh perubahan "
                "folder), jadi perintah /riset dst akan dibalas Unknown command.")
    ver = REPO / "lib" / "50-verify.sh"
    if ver.exists():
        checks += 1
        isi_ver = ver.read_text()
        if "Pintasan Telegram" not in isi_ver:
            err("lib/50-verify.sh tidak memeriksa pintasan Telegram. Tanpa ini "
                "operator tidak bisa membedakan 'skill belum terpasang' dari "
                "'gateway belum di-restart' -- keduanya terlihat identik.")
        checks += 1
        # `stat -c %Y /proc/<pid>` memberi waktu AKSES, bukan waktu mulai proses,
        # dan sudah pernah membuat pemeriksaan ini selalu lolos. Yang benar
        # `ps -o lstart=`. Aturan ini ada karena cacat itu lolos satu putaran uji.
        if "stat -c %Y \"/proc/" in isi_ver:
            err("lib/50-verify.sh memakai `stat -c %Y /proc/<pid>` untuk waktu "
                "mulai proses. Itu waktu AKSES, bukan waktu mulai, dan membuat "
                "pemeriksaan selalu menyimpulkan 'gateway hidup setelah skill "
                "terpasang'. Pakai `ps -o lstart=`.")

    print("\n[34] Pintasan Telegram terdaftar sebagai skill perintah")
    # Hermes tidak punya perintah Telegram untuk berpindah profil:
    #   - /profile hanya MELIHAT (gateway/slash_commands.py:355)
    #   - gateway.profile_routes dibaca saat gateway start, bukan runtime
    #   - /p/<profile>/ hanya untuk HTTP API (platforms/api_server.py:35-36)
    #   - / yang tidak dikenal tidak diteruskan ke model (run.py:18847)
    #
    # Yang dipakai adalah mekanisme resmi: skill terdaftar sebagai perintah
    # /nama-skill (agent/skill_commands.py, dipanggil run.py:18749). Aturan ini
    # memastikan pintasan yang dijanjikan ke operator benar-benar ada sebagai
    # skill, terdaftar di SKILLS, dan dipetakan ke profil yang menghadap
    # Telegram -- tanpa ketiganya perintah itu tidak akan pernah muncul.
    PINTASAN = ["panggil-pekerja", "riset", "harian", "quest", "daftar",
                "x", "discord", "pantau"]
    lib = REPO / "lib" / "30-hermes.sh"
    isi_lib = lib.read_text() if lib.exists() else ""
    for nama in PINTASAN:
        checks += 1
        if not (REPO / "skills" / nama / "SKILL.md").exists():
            err(f"skills/{nama}/SKILL.md tidak ada. Pintasan Telegram /{nama} "
                f"tidak akan terdaftar sebagai perintah.")
            continue
        # Ambil SELURUH isi array SKILLS=( ... ) lalu pecah jadi token.
        # Mencocokkan per baris salah: array bash boleh terpecah beberapa baris,
        # dan versi pertama aturan ini melaporkan positif palsu untuk semua
        # pintasan yang kebetulan tidak berada di awal baris.
        m_arr = re.search(r"^SKILLS=\(([^)]*)\)", isi_lib, re.M | re.S)
        daftar_skills = m_arr.group(1).split() if m_arr else []
        if nama not in daftar_skills:
            err(f"skills/{nama} tidak terdaftar di SKILLS (lib/30-hermes.sh) -- "
                f"tidak akan tersalin saat install, jadi /{nama} tidak muncul.")
        m = re.search(r'\[pekerja-koordinator\]="([^"]+)"', isi_lib)
        checks += 1
        if not m or nama not in m.group(1).split():
            err(f"skills/{nama} tidak dipetakan ke pekerja-koordinator di "
                f"PROFILE_SKILLS. Koordinator adalah profil yang menghadap "
                f"Telegram, jadi tanpa pemetaan ini /{nama} tidak tersedia "
                f"di chat.")

    print("\n[32] Profil default bisa mendelegasikan")
    # Keluhan operator: "telegram juga worker nya masih default agent hermes
    # bukan worker yang di buat yg tersambung ke situ".
    #
    # Penyebabnya terverifikasi di repo: gateway multiplex melayani profil
    # DEFAULT lebih dulu (hermes_cli/profiles.py:1105 profiles_to_serve
    # (multiplex=True) -- "the default profile is always served"), jadi profil
    # default-lah yang memegang TELEGRAM_BOT_TOKEN dan menjawab pesan Telegram.
    # Tanpa toolset `delegation` di config utama, tidak ada jalan dari Telegram
    # ke pekerja mana pun.
    root = REPO / "config" / "hermes" / "config.yaml"
    if root.exists():
        checks += 1
        data = yaml.safe_load(root.read_text()) or {}
        ts = data.get("toolsets") or []
        if "delegation" not in ts:
            err("config/hermes/config.yaml: toolset 'delegation' tidak ada. "
                "Gateway multiplex melayani profil default lebih dulu "
                "(profiles.py:1105), jadi profil default yang menjawab Telegram. "
                "Tanpa delegate_task di sana, tidak ada jalan dari Telegram ke "
                "pekerja mana pun.")
        checks += 1
        # terminal di root config bertentangan dengan penolakan CodeAct: semua
        # pekerja mematikannya, jadi menaruhnya di root berarti satu profil --
        # justru yang paling sering dipakai lewat Telegram -- punya kemampuan
        # yang operator larang.
        if "terminal" in ts:
            err("config/hermes/config.yaml: toolset 'terminal' masih ada di "
                "profil default padahal semua pekerja mematikannya "
                "(disabled_toolsets: [terminal, code_execution]). Profil "
                "default adalah yang menjawab Telegram.")
        checks += 1
        agent = data.get("agent") or {}
        dis = agent.get("disabled_toolsets") or []
        if "terminal" not in dis or "code_execution" not in dis:
            err(f"config/hermes/config.yaml: agent.disabled_toolsets={dis} "
                f"harus memuat terminal dan code_execution. CodeAct ditolak "
                f"operator dan berlaku di semua profil termasuk default.")


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

    # lib/*.sh dan `agentdrop` WAJIB ikut. Sebelumnya daftar ini hanya
    # scripts/*.sh + install.sh, jadi 6 berkas di lib/ dan CLI utamanya tidak
    # pernah diperiksa sama sekali -- padahal di situlah mayoritas logika
    # installer berada. Akibatnya nyata: bug `grep -c || echo 0` di
    # lib/40-browser.sh dan mkdir memory/lessons yang hilang di
    # lib/30-hermes.sh lolos 180 pemeriksaan, dan pemeriksaan baru untuk
    # memory/lessons tidak pernah berjalan karena berkasnya tidak diserahkan.
    # `agentdrop` tidak berekstensi .sh, jadi glob tidak akan menemukannya.
    scripts = sorted(REPO.glob("scripts/*.sh")) + sorted(REPO.glob("lib/*.sh"))
    for extra in ("install.sh", "agentdrop"):
        if (REPO / extra).exists():
            scripts.append(REPO / extra)
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
    print("  · pekerja-koordinator")

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
    check_skills_disabled(configs)
    check_model_provider(configs)
    check_browser_backend(configs)
    check_no_profile_gateway()
    check_hook_paths()
    check_snapshot_budget(configs)
    check_custom_base_url_trap()
    check_render_config()
    check_custom_providers_block(configs)

    print("\n[18] Memory loop + aturan anti prompt-injection")
    check_memory_loop(configs)

    print("\n[19] Log audit")
    check_audit_log()

    print("\n[20] Kontrak tool browser")
    check_browser_tool_contract()

    print("\n[21] Rujukan knowledge")
    check_knowledge_references()

    print("\n" + "=" * 62)
    check_model_vars_and_delegation(configs)

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
