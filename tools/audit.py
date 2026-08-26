#!/usr/bin/env python3
"""
audit.py — baca dan triase log audit AgentDrop.

TUJUAN
------
Ketika sesuatu rusak, Anda tidak seharusnya membaca seluruh alur. Alat ini
menjawab tiga pertanyaan:

    Apa yang rusak?      audit.py errors
    Di bagian mana?      audit.py doctor
    Bagaimana runtutannya? audit.py trace <id>

Semua keluaran menunjuk ke KOMPONEN dan ke berkas yang harus dibuka, karena
log tanpa penunjuk tetap membuat Anda membaca semuanya.

Pemakaian:
    python3 tools/audit.py health              ringkasan sistem
    python3 tools/audit.py errors [--limit 30] kesalahan terbaru
    python3 tools/audit.py doctor              diagnosis otomatis + berkas terkait
    python3 tools/audit.py trace <id>          runtutan satu tugas, ujung ke ujung
    python3 tools/audit.py component browser   semua dari satu komponen
    python3 tools/audit.py stuck               tool yang mulai tapi tidak selesai
    python3 tools/audit.py tail [-n 40]        baris terakhir
"""

from __future__ import annotations

import argparse
import os
import sys
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import audit_log  # noqa: E402

# Warna, dimatikan otomatis kalau bukan TTY atau NO_COLOR disetel.
_TTY = sys.stdout.isatty() and not os.environ.get("NO_COLOR")
def _c(code, s):
    return f"\033[{code}m{s}\033[0m" if _TTY else s
RED    = lambda s: _c("1;31", s)
GREEN  = lambda s: _c("1;32", s)
YELLOW = lambda s: _c("1;33", s)
BLUE   = lambda s: _c("1;34", s)
DIM    = lambda s: _c("2", s)
BOLD   = lambda s: _c("1", s)

LEVEL_COLOR = {"error": RED, "warn": YELLOW, "info": GREEN, "debug": DIM}

# ---------------------------------------------------------------------------
# Peta diagnosis.
#
# Ini inti dari "perbaiki bagian yang tepat". Setiap pola mencocokkan gejala di
# log dengan komponen yang bertanggung jawab dan berkas yang harus dibuka.
# Urutan penting: yang pertama cocok menang, jadi taruh yang paling spesifik
# di atas.
# ---------------------------------------------------------------------------
PLAYBOOK = [
    {
        "match": lambda r: r.get("component") == "browser" and r.get("ok") is False,
        "cause": "Tool browser gagal",
        "fix": "agentdrop browser-status",
        "where": [
            "config/hermes/profiles/*/config.yaml  (browser.cdp_url harus loopback:9222)",
            "agentdrop browser                     (Chrome for Testing + ekstensi)",
        ],
        "hint": "Kalau pesannya menyebut CDP/websocket, browser-nya belum jalan "
                "atau --session dipakai bersama --cdp (agent-browser >=0.13 "
                "mengabaikan --cdp secara diam-diam).",
    },
    {
        "match": lambda r: r.get("component") == "signing" and r.get("level") == "error",
        "cause": "Approval wallet bermasalah",
        "fix": "agentdrop browser-status",
        "where": [
            "config/extensions.yaml                          (wallet yang dipasang)",
            "config/hermes/profiles/worker-orchestrator/SOUL.md  (aturan approval)",
        ],
        "hint": "Wallet resmi dipegang manusia: approval ditandatangani lewat "
                "noVNC, bukan oleh agent. Kalau popup tidak muncul, ekstensi "
                "wallet kemungkinan tidak termuat.",
    },
    {
        "match": lambda r: r.get("component") == "delegation" and r.get("level") == "error",
        "cause": "Delegasi ke worker gagal",
        "fix": "python3 tools/validate_config.py",
        "where": [
            "config/hermes/profiles/worker-orchestrator/SOUL.md  (tabel routing)",
            "config/hermes/profiles/*/config.yaml                (delegation)",
        ],
        "hint": "Pastikan profil tujuan ada di tabel routing orchestrator dan "
                "muncul sebagai `nama` di SOUL.md.",
    },
    {
        "match": lambda r: r.get("component") == "gateway" and r.get("level") == "error",
        "cause": "Masalah di portal (Telegram)",
        "fix": "hermes gateway status",
        "where": [
            "config/hermes/profiles/worker-orchestrator/config.yaml  (platform.telegram)",
            ".env                                                     (TELEGRAM_*)",
        ],
        "hint": "Task masuk lewat orchestrator. Kalau tidak ada baris "
                "`agent:start` setelah pesan masuk, gateway tidak meneruskannya.",
    },
    {
        "match": lambda r: r.get("component") == "agent" and "api_request_error" in str(r.get("event")),
        "cause": "Panggilan API model gagal",
        "fix": "cek kuota/kunci provider",
        "where": [
            ".env                                        (kunci provider)",
            "config/hermes/profiles/*/config.yaml        (model.provider)",
        ],
        "hint": "Hermes membaca kredensial provider dari env yang dimuat dari "
                "~/.hermes/.env dengan override=True.",
    },
    {
        "match": lambda r: r.get("phase") == "install" and r.get("level") == "error",
        "cause": "Kegagalan saat instalasi",
        "fix": "bash install.sh",
        "where": ["install.sh", "./install.sh"],
        "hint": "Jalankan ulang install.sh; ia idempoten dan melanjutkan dari "
                "yang sudah berhasil.",
    },
    {
        "match": lambda r: r.get("component") == "browser" and r.get("level") == "error"
                           and "extension" in str(r.get("detail", "")).lower(),
        "cause": "Ekstensi wallet tidak berfungsi",
        "fix": "agentdrop extensions",
        "where": [
            "config/extensions.yaml           (manifest ekstensi)",
            "agentdrop extensions                  (unduh + ekstrak)",
        ],
        "hint": "Chrome 137+ branded mengabaikan --load-extension. Harus Chrome "
                "for Testing.",
    },
]


def _load(limit=None):
    recs = list(audit_log.read_all())
    recs.sort(key=lambda r: r.get("ts", ""))
    return recs[-limit:] if limit else recs


def _fmt(r, verbose=False):
    lvl = r.get("level", "info")
    col = LEVEL_COLOR.get(lvl, DIM)
    ts = r.get("ts", "?")[11:23]
    comp = r.get("component", "?")
    ev = r.get("event", "?")
    tool = r.get("tool")
    ms = r.get("ms")
    parts = [DIM(ts), col(f"{lvl:<5}"), BLUE(f"{comp:<10}"), ev]
    if tool:
        parts.append(f"tool={tool}")
    if ms is not None:
        parts.append(DIM(f"{ms}ms"))
    if r.get("ok") is False:
        parts.append(RED("ok=False"))
    if r.get("msg"):
        parts.append(r["msg"])
    line = "  ".join(parts)
    if verbose and r.get("detail"):
        line += "\n" + DIM(f"      detail: {str(r['detail'])[:400]}")
    return line


# ---------------------------------------------------------------------------
# Sub-perintah
# ---------------------------------------------------------------------------
def cmd_health(args):
    recs = _load()
    if not recs:
        print(YELLOW("Log kosong."))
        print(f"Direktori log: {audit_log.log_dir()}")
        print("Jalankan install.sh, atau set AGENTDROP_LOG_DIR.")
        return 0

    by_comp = Counter(r.get("component", "?") for r in recs)
    by_lvl = Counter(r.get("level", "?") for r in recs)
    spans = (recs[0].get("ts", ""), recs[-1].get("ts", ""))

    print(BOLD("=== Kesehatan log audit ==="))
    print(f"  berkas     : {audit_log.log_dir()}")
    print(f"  rentang    : {spans[0]}  →  {spans[1]}")
    print(f"  total baris: {len(recs)}")
    print()
    print(BOLD("  per komponen"))
    for k, v in by_comp.most_common():
        print(f"    {k:<12} {v}")
    print()
    print(BOLD("  per tingkat"))
    for k, v in by_lvl.most_common():
        col = LEVEL_COLOR.get(k, DIM)
        print(f"    {col(k):<20} {v}")

    # Tool paling lambat — antrean pertama untuk menyelidiki "kok lama".
    slow = sorted((r for r in recs if isinstance(r.get("ms"), (int, float))),
                  key=lambda r: r["ms"], reverse=True)[:5]
    if slow:
        print()
        print(BOLD("  lima pemanggilan paling lambat"))
        for r in slow:
            print(f"    {r['ms']:>8} ms  {r.get('tool') or r.get('event')}")

    errs = sum(1 for r in recs if r.get("level") == "error")
    print()
    if errs:
        print(RED(f"  {errs} baris error — jalankan: audit.py doctor"))
    else:
        print(GREEN("  tidak ada error"))
    return 0


def cmd_errors(args):
    recs = [r for r in _load() if r.get("level") in ("error", "warn")]
    if not recs:
        print(GREEN("Tidak ada error atau peringatan."))
        return 0
    print(BOLD(f"=== {len(recs)} error/peringatan terbaru ==="))
    for r in recs[-args.limit:]:
        print(_fmt(r, verbose=args.verbose))
    return 0


def cmd_doctor(args):
    """Cocokkan gejala dengan playbook dan tunjuk berkas yang harus dibuka."""
    recs = _load()
    if not recs:
        print(YELLOW("Log kosong — belum ada yang bisa didiagnosis."))
        return 0

    bad = [r for r in recs if r.get("level") == "error" or r.get("ok") is False]
    if not bad:
        print(GREEN("Tidak ada error di log. Tidak ada yang perlu diperbaiki."))
        return 0

    hits = []
    for entry in PLAYBOOK:
        matched = [r for r in bad if _safe(entry["match"], r)]
        if matched:
            hits.append((entry, matched))

    # Tool yang menggantung: ada pre tanpa post.
    hang = _find_hanging(recs)

    print(BOLD(f"=== Diagnosis: {len(bad)} baris bermasalah ===\n"))
    if not hits and not hang:
        print(YELLOW("Ada error, tapi tidak cocok dengan pola yang dikenal."))
        print("Lihat mentahnya: audit.py errors --verbose\n")
        for r in bad[-10:]:
            print("  " + _fmt(r))
        return 1

    for entry, matched in hits:
        print(RED(f"● {entry['cause']}") + DIM(f"  ({len(matched)} kejadian)"))
        contoh = matched[-1]
        print(f"    terakhir : {contoh.get('ts')}  {contoh.get('event')} "
              f"{contoh.get('tool') or ''}".rstrip())
        d = contoh.get("detail")
        if d:
            print(DIM(f"    detail   : {str(d)[:300]}"))
        print(f"    {BOLD('periksa')}  : {entry['fix']}")
        for w in entry["where"]:
            print(f"    berkas   : {w}")
        print(DIM(f"    catatan  : {entry['hint']}"))
        print()

    if hang:
        print(YELLOW(f"● {len(hang)} tool mulai tapi tidak pernah selesai"))
        for r in hang[-5:]:
            print(f"    {r.get('ts')}  {r.get('tool')}  session={r.get('session','')[:20]}")
        print(f"    {BOLD('periksa')}  : apakah browser masih hidup? "
              f"agentdrop browser-status")
        print()

    print(DIM("Untuk runtutan lengkap satu tugas: audit.py trace <session/trace>"))
    return 1


def _safe(fn, r):
    try:
        return bool(fn(r))
    except Exception:
        return False


def _find_hanging(recs):
    """pre_tool_call tanpa post_tool_call yang cocok."""
    open_calls = {}
    hanging = []
    for r in recs:
        if r.get("event") != "pre_tool_call":
            if r.get("event") == "post_tool_call":
                key = (r.get("session"), r.get("tool"),
                       (r.get("detail") or {}).get("tool_call_id"))
                open_calls.pop(key, None)
            continue
        key = (r.get("session"), r.get("tool"),
               (r.get("detail") or {}).get("tool_call_id"))
        open_calls[key] = r
    hanging = list(open_calls.values())
    hanging.sort(key=lambda r: r.get("ts", ""))
    return hanging


def cmd_trace(args):
    """Runtutan satu tugas dari ujung ke ujung."""
    recs = _load()
    ident = args.id
    chain = audit_log.trace_ids_for(recs, ident)
    chain.add(ident)

    picked = [r for r in recs
              if ident in (r.get("trace"), r.get("session"), r.get("task"))
              or r.get("session") in chain or r.get("task") in chain]
    if not picked:
        print(YELLOW(f"Tidak ada baris untuk '{ident}'."))
        print("Coba: audit.py tail -n 40   untuk melihat id yang tersedia.")
        return 1

    picked.sort(key=lambda r: r.get("ts", ""))
    print(BOLD(f"=== Runtutan '{ident}' — {len(picked)} langkah ===\n"))

    t0 = None
    for r in picked:
        ts = r.get("ts", "")
        delta = ""
        try:
            from datetime import datetime
            t = datetime.strptime(ts, "%Y-%m-%dT%H:%M:%S.%fZ")
            if t0 is None:
                t0 = t
            delta = f"+{(t - t0).total_seconds():6.2f}s"
        except Exception:
            delta = " " * 9
        mark = ""
        if r.get("level") == "error" or r.get("ok") is False:
            mark = RED("  <-- MASALAH")
        print(f"{delta}  {_fmt(r)}{mark}")

    errs = [r for r in picked if r.get("level") == "error" or r.get("ok") is False]
    print()
    if errs:
        print(RED(f"{len(errs)} langkah gagal dalam runtutan ini."))
        comp = Counter(r.get("component") for r in errs)
        print("Komponen yang terlibat: " + ", ".join(f"{k} ({v})" for k, v in comp.items()))
        print("Jalankan: audit.py doctor")
    else:
        print(GREEN("Runtutan ini selesai tanpa error."))
    return 0


def cmd_component(args):
    recs = [r for r in _load() if r.get("component") == args.name]
    if not recs:
        ada = sorted({r.get("component", "?") for r in _load()})
        print(YELLOW(f"Tidak ada baris untuk komponen '{args.name}'."))
        print("Komponen yang ada: " + ", ".join(ada))
        return 1
    print(BOLD(f"=== komponen '{args.name}' — {len(recs)} baris ==="))
    for r in recs[-args.limit:]:
        print(_fmt(r, verbose=args.verbose))
    return 0


def cmd_stuck(args):
    hang = _find_hanging(_load())
    if not hang:
        print(GREEN("Tidak ada tool yang menggantung."))
        return 0
    print(YELLOW(f"=== {len(hang)} tool mulai tanpa selesai ==="))
    for r in hang[-args.limit:]:
        print(f"  {r.get('ts')}  {r.get('tool'):<22} session={r.get('session','')}")
    print()
    print("Tool yang menggantung hampir selalu berarti browsernya mati atau")
    print("CDP terputus. Periksa: agentdrop browser-status")
    return 1


def cmd_tail(args):
    recs = _load()
    for r in recs[-args.n:]:
        print(_fmt(r, verbose=args.verbose))
    if not recs:
        print(YELLOW("Log kosong."))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("health", help="ringkasan sistem").set_defaults(fn=cmd_health)

    p = sub.add_parser("errors", help="kesalahan terbaru")
    p.add_argument("--limit", type=int, default=30)
    p.add_argument("--verbose", "-v", action="store_true")
    p.set_defaults(fn=cmd_errors)

    sub.add_parser("doctor", help="diagnosis otomatis + berkas terkait").set_defaults(fn=cmd_doctor)

    p = sub.add_parser("trace", help="runtutan satu tugas")
    p.add_argument("id")
    p.set_defaults(fn=cmd_trace)

    p = sub.add_parser("component", help="semua baris satu komponen")
    p.add_argument("name")
    p.add_argument("--limit", type=int, default=100)
    p.add_argument("--verbose", "-v", action="store_true")
    p.set_defaults(fn=cmd_component)

    p = sub.add_parser("stuck", help="tool yang mulai tanpa selesai")
    p.add_argument("--limit", type=int, default=20)
    p.set_defaults(fn=cmd_stuck)

    p = sub.add_parser("tail", help="baris terakhir")
    p.add_argument("-n", type=int, default=40)
    p.add_argument("--verbose", "-v", action="store_true")
    p.set_defaults(fn=cmd_tail)

    args = ap.parse_args()
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
