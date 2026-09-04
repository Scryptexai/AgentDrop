#!/usr/bin/env python3
"""
Pustaka bersama untuk log audit AgentDrop.

Dipakai oleh:
  - hooks/agentdrop-audit/handler.py   (gateway hook: agent:start/step/end)
  - agent-hooks/audit-log.py           (shell hook: pre/post_tool_call, dst)
  - install.sh / ./install.sh      (fase instalasi)
  - tools/audit.py                     (pembaca)

DESAIN
------
JSONL, satu objek per baris. Alasannya: bisa ditambahkan tanpa merusak berkas
yang sedang dibaca, bisa di-grep, dan bisa dibaca sebagian tanpa memuat
seluruhnya.

`component` adalah field yang paling penting. Tujuan sistem ini adalah
memperbaiki BAGIAN yang salah tanpa membaca seluruh alur, jadi setiap baris
harus bisa diarahkan ke satu komponen:

    install    instalasi / setup
    gateway    pesan masuk dari Telegram dsb
    agent      loop agent (mulai, langkah, selesai)
    delegation pemanggilan worker lain
    tool       pemanggilan tool apa pun
    browser    pemanggilan tool browser_* secara khusus
    signing    keputusan signing daemon
    config     pemuatan konfigurasi

`trace` menghubungkan satu tugas dari ujung ke ujung: pesan Telegram → agent →
tool → browser. Tanpa itu, log hanya jadi tumpukan baris.

KEAMANAN
--------
Log ini merekam `tool_input`, yang bisa berisi apa saja. Karena itu redaksi
berjalan di sini, di satu tempat, bukan diserahkan ke tiap pemanggil.
"""

from __future__ import annotations

import fcntl
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# Lokasi
# ---------------------------------------------------------------------------
def _marker_log_dir() -> str:
    """Path log yang ditulis install.sh, supaya log masuk ke DALAM repo.

    Hook Hermes dipanggil sebagai perintah polos tanpa environment, jadi
    AGENTDROP_LOG_DIR tidak pernah sampai ke proses ini. install.sh menulis
    path yang benar ke ~/.agentdrop/logdir dan berkas itu yang dibaca di sini.
    Tanpa ini log selalu jatuh ke ~/.agentdrop/logs — di luar repo, sehingga
    tidak mungkin di-commit dan tidak bisa dipakai mendiagnosis dari branch.
    """
    try:
        f = Path.home() / ".agentdrop" / "logdir"
        if f.is_file():
            v = f.read_text(encoding="utf-8").strip()
            if v:
                return v
    except OSError:
        pass
    return ""


def log_dir() -> Path:
    p = (os.environ.get("AGENTDROP_LOG_DIR")
         or _marker_log_dir()
         or str(Path.home() / ".agentdrop" / "logs"))
    d = Path(p)
    try:
        d.mkdir(parents=True, exist_ok=True)
    except OSError:
        # Fallback terakhir: /tmp. Kehilangan log lebih buruk daripada
        # menaruhnya di tempat yang kurang ideal, tapi jangan sampai kegagalan
        # mkdir mematikan agent.
        d = Path("/tmp/agentdrop-logs")
        d.mkdir(parents=True, exist_ok=True)
    return d


MAX_BYTES = int(os.environ.get("AGENTDROP_LOG_MAX_BYTES", 20 * 1024 * 1024))  # 20 MB
KEEP_FILES = int(os.environ.get("AGENTDROP_LOG_KEEP_FILES", 14))


# ---------------------------------------------------------------------------
# Redaksi
# ---------------------------------------------------------------------------
# Kunci yang isinya selalu dibuang apa pun bentuknya.
_SECRET_KEYS = {
    "private_key", "privatekey", "privkey", "secret", "secret_key", "seed",
    "seed_phrase", "mnemonic", "password", "passwd", "token", "access_token",
    "api_key", "apikey", "bot_token", "cookie", "cookies", "authorization",
    "auth", "session_storage", "keystore", "passphrase",
}

# Pola nilai yang berbahaya meski kuncinya tidak mencurigakan.
_SECRET_PATTERNS = [
    (re.compile(r"\b0x[a-fA-F0-9]{64}\b"), "<HEX64_DIBUANG>"),          # private key EVM
    (re.compile(r"\b[1-9A-HJ-NP-Za-km-z]{87,88}\b"), "<BASE58_DIBUANG>"),  # Solana secret
    (re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"), "<SK_DIBUANG>"),
    # TANPA \b di depan. Bentuk bot token yang paling sering masuk log ada di
    # dalam URL: https://api.telegram.org/bot123456789:AAxxxx/sendMessage
    # Di situ karakter sebelum angka adalah huruf 't', sehingga \b tidak cocok
    # dan token lolos. Penambat ":AA" sesudah 8-10 digit sudah cukup khas.
    (re.compile(r"\d{8,10}:AA[A-Za-z0-9_-]{30,}"), "<BOT_TOKEN_DIBUANG>"),
    (re.compile(r"\b[A-Za-z0-9+/]{40,}={0,2}\b"), "<B64PANJANG_DIBUANG>"),
]

# Frasa seed: 12/24 kata berurutan. Heuristik — lebih baik over-redact.
_MNEMONIC = re.compile(r"\b(?:[a-z]{3,8}\s+){11,23}[a-z]{3,8}\b")


def redact(value, depth: int = 0):
    """Bersihkan struktur apa pun secara rekursif. Tidak pernah melempar."""
    if depth > 12:
        return "<TERLALU_DALAM>"
    try:
        if value is None or isinstance(value, bool) or isinstance(value, (int, float)):
            return value
        if isinstance(value, str):
            return _redact_str(value)
        if isinstance(value, dict):
            out = {}
            for k, v in value.items():
                if isinstance(k, str) and k.lower() in _SECRET_KEYS:
                    out[k] = "<DIBUANG>"
                else:
                    out[k] = redact(v, depth + 1)
            return out
        if isinstance(value, (list, tuple)):
            return [redact(v, depth + 1) for v in list(value)[:200]]
        return str(value)[:500]
    except Exception:
        return "<GAGAL_MEREDAKSI>"


def _redact_str(s: str) -> str:
    for pat, repl in _SECRET_PATTERNS:
        s = pat.sub(repl, s)
    if _MNEMONIC.search(s):
        s = _MNEMONIC.sub("<MUNGKIN_SEED_DIBUANG>", s)
    return s[:4000]


# ---------------------------------------------------------------------------
# Penulisan
# ---------------------------------------------------------------------------
def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def _path(d: Path) -> Path:
    return d / (datetime.now(timezone.utc).strftime("audit-%Y%m%d") + ".jsonl")


def _rotate(d: Path, p: Path) -> None:
    """Rotasi kalau berkas hari ini melewati batas, lalu pangkas jumlah berkas."""
    try:
        if p.exists() and p.stat().st_size > MAX_BYTES:
            stamp = datetime.now(timezone.utc).strftime("%H%M%S")
            p.rename(p.with_suffix(f".{stamp}.jsonl"))
    except OSError:
        pass
    try:
        files = sorted(d.glob("audit-*.jsonl"), key=lambda x: x.stat().st_mtime)
        for old in files[: max(0, len(files) - KEEP_FILES)]:
            old.unlink()
    except OSError:
        pass


def write(component: str, event: str, *, level: str = "info", msg: str = "",
          trace: str = "", session: str = "", task: str = "", actor: str = "",
          tool: str = "", ok=None, ms=None, detail=None, phase: str = "run",
          redact_detail: bool = True) -> None:
    """Tulis satu baris audit. Tidak pernah melempar ke pemanggil.

    Aturan ini penting: logger yang bisa menjatuhkan agent akan dimatikan
    orang, dan log yang dimatikan tidak berguna sama sekali.
    """
    try:
        d = log_dir()
        rec = {
            "ts": _now(),
            "phase": phase,
            "component": component,
            "level": level,
            "event": event,
        }
        if msg:
            rec["msg"] = msg
        if trace:
            rec["trace"] = trace
        if session:
            rec["session"] = session
        if task:
            rec["task"] = task
        if actor:
            rec["actor"] = actor
        if tool:
            rec["tool"] = tool
        if ok is not None:
            rec["ok"] = bool(ok)
        if ms is not None:
            try:
                rec["ms"] = round(float(ms), 1)
            except (TypeError, ValueError):
                pass
        if detail:
            rec["detail"] = redact(detail) if redact_detail else detail
        line = json.dumps(rec, ensure_ascii=False, separators=(",", ":"))

        p = _path(d)
        _rotate(d, p)
        # flock: beberapa proses (gateway, worker, daemon) menulis bersamaan.
        # Tanpa ini baris bisa saling tertimpa dan menghasilkan JSON rusak.
        with open(p, "a", encoding="utf-8") as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)
            try:
                f.write(line + "\n")
                f.flush()
            finally:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)
    except Exception:
        # Diam-diam. Lihat docstring.
        pass


def read_all(days: int = 7):
    """Baca semua baris dari `days` hari terakhir. Melewati baris rusak."""
    d = log_dir()
    files = sorted(d.glob("audit-*.jsonl"))
    for p in files:
        try:
            with open(p, "r", encoding="utf-8", errors="replace") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        yield json.loads(line)
                    except json.JSONDecodeError:
                        continue
        except OSError:
            continue


def trace_ids_for(records, trace: str) -> set:
    """Kumpulkan session_id yang berbagi trace, supaya satu query bisa menarik
    seluruh rantai meski tiap baris hanya menyimpan salah satunya."""
    sessions, tasks = set(), set()
    for r in records:
        if r.get("trace") == trace:
            if r.get("session"):
                sessions.add(r["session"])
            if r.get("task"):
                tasks.add(r["task"])
    return sessions | tasks
