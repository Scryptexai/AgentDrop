"""Tool `browser_act` — aksi browser + snapshot dalam satu panggilan.

MENGAPA ADA
Di Hermes bawaan asimetrinya begini (dibaca dari kode, bukan diperkirakan):

  browser_navigate  1 putaran   tools/browser_tool.py:4478
                  "Auto-take a compact snapshot so the model can act
                   immediately without a separate browser_snapshot call."
  browser_click     2 putaran   tools/browser_tool.py:4608
                  hanya membalas {"success": true, "clicked": ref}

Dan batch dalam satu putaran MUSTAHIL: `_PARALLEL_SAFE_TOOLS`
(agent/tool_dispatch_helpers.py) tidak memuat satu pun tool browser.

PENDEKATAN: TAMBAHAN, BUKAN OVERRIDE.
Hermes mendukung `register_tool(..., override=True)` untuk menimpa tool bawaan,
tapi itu menaruh kode kita di jalur panas setiap klik dan butuh gate
`allow_tool_override: true`. Tool baru tidak butuh gate — gate hanya dipanggil
ketika override=True (hermes_cli/plugins.py:1806) — dan kalau plugin ini gagal
dimuat, agent tetap punya seluruh tool browser aslinya.
"""

from __future__ import annotations

import json
import logging

logger = logging.getLogger(__name__)

TOOLSET = "agentdrop-browser"

_SCHEMA = {
    "name": "browser_act",
    "description": (
        "Klik atau ketik, LALU langsung mengembalikan snapshot halaman. "
        "Pakai ini sebagai pengganti browser_click/browser_type ketika Anda "
        "perlu melihat akibat aksi. Menghemat satu putaran LLM dibanding "
        "memanggil browser_click lalu browser_snapshot terpisah."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["click", "type", "press"],
                "description": "Aksi yang dilakukan pada elemen.",
            },
            "ref": {
                "type": "string",
                "description": "Referensi elemen dari snapshot, mis. '@e5'.",
            },
            "text": {
                "type": "string",
                "description": "Untuk action=type: teks yang diketik.",
            },
            "key": {
                "type": "string",
                "description": "Untuk action=press: nama tombol, mis. 'Enter'.",
            },
            "task_id": {
                "type": "string",
                "description": "Opsional, untuk isolasi sesi.",
            },
        },
        "required": ["action"],
    },
}


def _browser_act(action: str, ref: str = "", text: str = "", key: str = "",
                 task_id: str = "") -> str:
    """Jalankan satu aksi browser lalu kembalikan snapshot-nya.

    Kita memanggil fungsi tool PUBLIK Hermes, bukan internal privat seperti
    `_run_browser_command`. Kalau nama fungsi itu berubah di versi Hermes lain,
    kegagalan muncul di sini sebagai pesan yang jelas, bukan perilaku aneh.
    """
    try:
        from tools.browser_tool import (  # type: ignore
            browser_click,
            browser_press,
            browser_snapshot,
            browser_type,
        )
    except Exception as e:
        return json.dumps({
            "success": False,
            "error": f"tool browser Hermes tidak tersedia: {type(e).__name__}: {e}",
        }, ensure_ascii=False)

    tid = task_id or None
    try:
        if action == "click":
            if not ref:
                return json.dumps({"success": False,
                                   "error": "action=click butuh 'ref'"},
                                  ensure_ascii=False)
            hasil_aksi = browser_click(ref, tid)
        elif action == "type":
            if not ref or not text:
                return json.dumps({"success": False,
                                   "error": "action=type butuh 'ref' dan 'text'"},
                                  ensure_ascii=False)
            hasil_aksi = browser_type(ref, text, tid)
        elif action == "press":
            if not key:
                return json.dumps({"success": False,
                                   "error": "action=press butuh 'key'"},
                                  ensure_ascii=False)
            hasil_aksi = browser_press(key, tid)
        else:
            return json.dumps({
                "success": False,
                "error": f"action tidak dikenal: {action!r}",
            }, ensure_ascii=False)
    except Exception as e:
        return json.dumps({
            "success": False,
            "error": f"aksi gagal: {type(e).__name__}: {e}",
        }, ensure_ascii=False)

    # Aksi gagal -> jangan buang panggilan snapshot. Model perlu tahu aksinya
    # gagal, bukan melihat halaman yang tidak berubah.
    try:
        parsed = json.loads(hasil_aksi)
    except Exception:
        parsed = {}
    if not parsed.get("success", False):
        return hasil_aksi

    try:
        snap = browser_snapshot(task_id=tid)
    except Exception as e:
        # Aksi berhasil tapi snapshot gagal: laporkan aksinya, sebut gagalnya.
        # Jangan membuang keberhasilan aksi hanya karena langkah kedua gagal.
        try:
            base = json.loads(hasil_aksi)
        except Exception:
            base = {"success": True, "raw": hasil_aksi}
        base["snapshot_error"] = f"{type(e).__name__}: {e}"
        return json.dumps(base, ensure_ascii=False)

    try:
        snap_parsed = json.loads(snap)
    except Exception:
        snap_parsed = {"snapshot": snap}
    gabungan = dict(parsed)
    gabungan["snapshot"] = snap_parsed.get("snapshot", snap_parsed)
    return json.dumps(gabungan, ensure_ascii=False)


def register(ctx) -> None:
    """Entry point plugin — kontraknya `def register(ctx)` seperti plugin
    Hermes lainnya (mis. plugins/google_meet/__init__.py:65)."""
    try:
        ctx.register_tool(
            name="browser_act",
            toolset=TOOLSET,
            schema=_SCHEMA,
            handler=_browser_act,
            emoji="🖱️",
        )
        logger.info("agentdrop-browser: browser_act terdaftar di toolset %s",
                    TOOLSET)
    except Exception:
        logger.exception("agentdrop-browser: gagal mendaftarkan browser_act")
        raise
