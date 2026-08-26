#!/usr/bin/env python3
"""
Shell hook: merekam setiap pemanggilan tool ke log audit.

Dipanggil Hermes sebagai subprocess untuk event yang didaftarkan di blok
`hooks:` pada config.yaml. Protokolnya (lihat
hermes-agent/website/docs/user-guide/features/hooks.md):

    stdin  -> JSON payload
    stdout -> JSON (kosong = tidak mengubah apa pun)

Payload yang kita terima:
    {
      "hook_event_name": "post_tool_call",
      "tool_name":       "browser_click",
      "tool_input":      {...},
      "session_id":      "sess_abc123",
      "cwd":             "/home/user/project",
      "extra":           {"task_id": "...", "tool_call_id": "...", "duration_ms": 812}
    }

`tool_name` dan `tool_input` bernilai null untuk event non-tool
(subagent_stop, on_session_start, dst).

CATATAN KINERJA
---------------
Hook ini jalan untuk SETIAP pemanggilan tool, sebagai proses baru. Karena itu
ia harus cepat dan tidak boleh melakukan I/O jaringan. Kalau ia lambat, setiap
langkah agent ikut lambat.

Hook ini juga TIDAK PERNAH memblokir. `fail_closed` sengaja tidak disetel di
config: logger yang bisa menggagalkan tool call akan dimatikan orang, dan log
yang dimatikan tidak ada gunanya.
"""

import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.environ.get("AGENTDROP_ROOT", "")
for _cand in (os.path.join(_ROOT, "tools") if _ROOT else "",
              os.path.join(os.path.dirname(_HERE), "tools"),
              os.path.join(_HERE, "tools")):
    if _cand and os.path.exists(os.path.join(_cand, "audit_log.py")):
        sys.path.insert(0, _cand)
        break

try:
    import audit_log
except Exception:
    audit_log = None


# Tool browser dipisahkan ke komponen sendiri. Alasannya spesifik: keluhan
# paling sering adalah "browser salah", dan kalau baris browser tercampur
# dengan ribuan baris tool lain, menemukan titik rusaknya berarti membaca
# seluruh alur — persis yang ingin dihindari sistem ini.
_BROWSER_TOOLS = {
    "browser_navigate", "browser_snapshot", "browser_click", "browser_type",
    "browser_scroll", "browser_back", "browser_press", "browser_get_images",
    "browser_vision", "browser_console", "browser_cdp", "browser_dialog",
    "browser_exec",
}

_COMPONENT = {
    "pre_tool_call": "tool",
    "post_tool_call": "tool",
    "subagent_start": "delegation",
    "subagent_stop": "delegation",
    "on_session_start": "gateway",
    "on_session_end": "gateway",
    "on_session_reset": "gateway",
    "on_session_finalize": "gateway",
    "pre_llm_call": "agent",
    "post_llm_call": "agent",
    "pre_api_request": "agent",
    "post_api_request": "agent",
    "api_request_error": "agent",
    "pre_approval_request": "signing",
    "post_approval_response": "signing",
    "on_skill_lifecycle": "tool",
    "pre_gateway_dispatch": "gateway",
}


def main() -> None:
    try:
        raw = sys.stdin.read()
        payload = json.loads(raw) if raw.strip() else {}
    except Exception:
        payload = {}

    if audit_log is None:
        # Tanpa pustaka penulis kita tetap harus mengembalikan JSON valid,
        # kalau tidak Hermes menganggap hook ini rusak.
        sys.stdout.write("{}")
        return

    event = str(payload.get("hook_event_name") or "")
    if not event:
        # Payload kosong atau rusak. Menulis baris "unknown" hanya menambah
        # noise yang harus disaring nanti — lebih baik tidak mencatat apa pun.
        sys.stdout.write("{}")
        return
    tool = payload.get("tool_name") or ""
    extra = payload.get("extra") or {}
    session = str(payload.get("session_id") or "")

    component = _COMPONENT.get(event, "tool")
    if tool in _BROWSER_TOOLS:
        component = "browser"

    # `pre_tool_call` hanya penanda mulai; yang bernilai diagnostik adalah
    # `post_tool_call` karena membawa hasil dan durasi. pre tetap dicatat
    # (level debug) supaya tool yang menggantung terlihat: ada pre tanpa post.
    level = "info"
    ok = None
    ms = extra.get("duration_ms")

    result = extra.get("tool_result")
    if isinstance(result, dict):
        if result.get("success") is False or result.get("error"):
            ok = False
            level = "error"
        else:
            ok = True
    if event == "api_request_error":
        level = "error"
        ok = False

    detail = {"tool_input": payload.get("tool_input")}
    for k in ("task_id", "tool_call_id", "child_role", "error", "iteration"):
        if k in extra:
            detail[k] = extra[k]
    if isinstance(result, dict):
        # Hasil tool bisa sangat besar (snapshot DOM). Ambil ringkasannya saja.
        detail["error"] = result.get("error")
        detail["success"] = result.get("success")
        detail["keys"] = sorted(result.keys())[:20]

    audit_log.write(
        component=component,
        event=event,
        level="debug" if event == "pre_tool_call" else level,
        trace=str(extra.get("trace") or session),
        session=session,
        task=str(extra.get("task_id") or ""),
        tool=str(tool),
        ok=ok,
        ms=ms,
        detail=detail,
    )

    # Kosong = jangan ubah apa pun.
    sys.stdout.write("{}")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        try:
            sys.stdout.write("{}")
        except Exception:
            pass
