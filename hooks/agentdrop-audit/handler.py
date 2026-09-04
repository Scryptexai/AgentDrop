"""
Gateway hook: merekam siklus hidup agent ke log audit.

Hermes memanggil `handle(event_type, context)` untuk setiap event yang
dideklarasikan di HOOK.yaml. Kesalahan di sini ditangkap Hermes dan tidak
pernah menjatuhkan agent — tapi kita juga tidak boleh melempar, karena hook
yang gagal berulang akan terlihat seperti kerusakan sistem.

Yang direkam di sini adalah sisi PORTAL: pesan masuk dari Telegram, sesi, dan
langkah agent. Sisi TOOL (browser_click dan kawan-kawan) direkam oleh
agent-hooks/audit-log.py. Keduanya bertemu di `session` dan `trace`.
"""

import os
import sys

# ---------------------------------------------------------------------------
# Temukan tools/audit_log.py.
#
# Hook ini dipasang ke ~/.hermes/hooks/agentdrop-audit/, jauh dari repo. setup.sh
# menyalin audit_log.py ke sebelah berkas ini, dan AGENTDROP_ROOT menjadi
# override. Kalau keduanya gagal, pakai penulis minimal di bawah — kehilangan
# detail lebih baik daripada kehilangan log sama sekali.
# ---------------------------------------------------------------------------
_HERE = os.path.dirname(os.path.abspath(__file__))
for _cand in (os.environ.get("AGENTDROP_ROOT", ""), _HERE,
              os.path.join(_HERE, "tools")):
    if _cand and os.path.exists(os.path.join(_cand, "audit_log.py")):
        sys.path.insert(0, _cand)
        break
    if _cand and os.path.exists(os.path.join(_cand, "tools", "audit_log.py")):
        sys.path.insert(0, os.path.join(_cand, "tools"))
        break

try:
    import audit_log
except Exception:  # pragma: no cover - jalur darurat
    import json
    from datetime import datetime, timezone
    from pathlib import Path

    class _Fallback:
        @staticmethod
        def write(component, event, **kw):
            try:
                _p = os.environ.get("AGENTDROP_LOG_DIR", "")
                if not _p:
                    # install.sh menulis path log ke ~/.agentdrop/logdir supaya
                    # log masuk ke DALAM repo dan bisa di-commit. Hook Hermes
                    # dipanggil tanpa environment, jadi env tidak pernah sampai.
                    try:
                        _f = Path.home() / ".agentdrop" / "logdir"
                        if _f.is_file():
                            _p = _f.read_text(encoding="utf-8").strip()
                    except OSError:
                        _p = ""
                d = Path(_p or str(Path.home() / ".agentdrop" / "logs"))
                d.mkdir(parents=True, exist_ok=True)
                rec = {"ts": datetime.now(timezone.utc).isoformat(),
                       "component": component, "event": event, **kw}
                with open(d / "audit-fallback.jsonl", "a") as f:
                    f.write(json.dumps(rec, ensure_ascii=False, default=str) + "\n")
            except Exception:
                pass

    audit_log = _Fallback()


# `agent:start` membawa `message` (dipotong 500 char). Itu teks dari manusia,
# bukan secret, tapi tetap dibatasi supaya log tidak membengkak.
def _clip(s, n=500):
    if not isinstance(s, str):
        return s
    return s if len(s) <= n else s[:n] + "…"


# event -> komponen audit. Pemetaan inilah yang membuat `tools/audit.py errors`
# bisa menunjuk ke bagian yang benar.
_COMPONENT = {
    "gateway:startup": "gateway",
    "session:start": "gateway",
    "session:end": "gateway",
    "session:reset": "gateway",
    "agent:start": "agent",
    "agent:step": "agent",
    "agent:end": "agent",
}


def handle(event_type: str, context: dict):
    """Dipanggil Hermes untuk setiap event. Boleh sync atau async."""
    try:
        ctx = context or {}
        component = _COMPONENT.get(event_type, "gateway")
        session = str(ctx.get("session_id") or ctx.get("session_key") or "")

        # trace: kunci yang menyatukan satu tugas dari Telegram sampai browser.
        # Dipakai session_id sebagai dasar karena itulah yang tersedia di kedua
        # sistem hook (gateway hook dan shell hook).
        trace = str(ctx.get("trace") or session or "")

        detail = {k: v for k, v in ctx.items()
                  if k not in ("session_id", "session_key", "trace")}
        if "message" in detail:
            detail["message"] = _clip(detail["message"])
        if "response" in detail:
            detail["response"] = _clip(detail["response"])

        # Tingkat keparahan: agent:end tanpa response biasanya berarti gagal.
        level = "info"
        msg = ""
        if event_type == "agent:end":
            if not ctx.get("response"):
                level = "warn"
                msg = "agent selesai tanpa response"
        elif event_type == "session:reset":
            msg = "sesi di-reset oleh pengguna"

        audit_log.write(
            component=component,
            event=event_type,
            level=level,
            msg=msg,
            trace=trace,
            session=session,
            actor=str(ctx.get("platform") or ""),
            detail=detail,
        )
    except Exception:
        # Jangan pernah menjatuhkan gateway karena log.
        pass
