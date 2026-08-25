#!/usr/bin/env bash
# ============================================================================
# takeover.sh — login VISUAL di GUI browser, lalu agent pakai sesi yang sama
# ============================================================================
# Ini implementasi pola "Take Over" (Manus Cloud Browser) di atas plugin vnc
# camofox-browser:
#
#   1. Buka halaman login di browser Camofox yang PERSISTEN
#   2. Anda login lewat GUI di http://localhost:6080/vnc.html
#      (selesaikan MFA / CAPTCHA / verifikasi apa pun)
#   3. Plugin persistence menyimpan cookies + localStorage + IndexedDB
#   4. Agent melanjutkan dengan sesi yang sudah terautentikasi
#
# KENAPA userId-nya DIHITUNG, BUKAN DIKARANG
# ------------------------------------------
# Hermes menurunkan userId Camofox secara deterministik dari HERMES_HOME
# (tools/browser_camofox_state.py:get_camofox_identity):
#
#   scope_root  = HERMES_HOME/browser_auth/camofox
#   user_id     = "hermes_" + uuid5(NAMESPACE_URL, "camofox-user:"+scope_root).hex[:10]
#   session_key = "task_"   + uuid5(NAMESPACE_URL, "camofox-session:"+scope_root+":"+task).hex[:16]
#
# Kalau skrip ini memakai userId asal-asalan, login Anda akan masuk ke profil
# Firefox yang BERBEDA dari yang dipakai agent — sia-sia. Jadi skrip ini
# mereplikasi formula yang sama persis.
#
# Formula di bawah sudah diuji terhadap fungsi Hermes asli:
#   HERMES_HOME=~/.hermes/profiles/worker-daily
#   -> user_id hermes_68c00ea529, session_key task_8fe86c2102965395  (identik)
# ============================================================================
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HERMES_HOME_DIR="${HERMES_HOME:-$HOME/.hermes}"

log()  { printf '\033[1;34m==>\033[0m %s\n' "$*"; }
ok()   { printf '\033[1;32m  ✓\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m  !\033[0m %s\n' "$*"; }
die()  { printf '\033[1;31m  ✗ %s\033[0m\n' "$*" >&2; exit 1; }

usage() {
  cat <<EOF
Pemakaian:
  $(basename "$0") <profil> <URL-login> [--task <task-id>]

Contoh:
  $(basename "$0") worker-daily  https://app.galxe.com/login
  $(basename "$0") worker-quests https://layer3.xyz/login --task galxe

Profil yang tersedia:
  worker-analyzer  worker-daily  worker-quests  worker-discord  worker-monitor

Catatan:
  Kalau .env menyetel CAMOFOX_USER_ID, nilai itu yang dipakai Hermes untuk
  SEMUA profil (identitas bersama) dan skrip ini mengikutinya.
EOF
}

[[ $# -ge 2 ]] || { usage; exit 1; }

PROFILE="$1"; shift
URL="$1"; shift
TASK="default"
while [[ $# -gt 0 ]]; do
  case "$1" in
    --task) TASK="${2:-}"; shift 2 ;;
    *) die "argumen tidak dikenal: $1" ;;
  esac
done

# Muat .env (CAMOFOX_URL, CAMOFOX_USER_ID, NOVNC_PORT, CAMOFOX_API_KEY)
if [[ -f "$REPO_ROOT/.env" ]]; then
  set -a; # shellcheck disable=SC1091
  source "$REPO_ROOT/.env"; set +a
fi
CAMOFOX_URL="${CAMOFOX_URL:-http://localhost:9377}"
NOVNC_PORT="${NOVNC_PORT:-6080}"

command -v curl >/dev/null 2>&1 || die "butuh curl"
command -v python3 >/dev/null 2>&1 || die "butuh python3 (untuk menghitung userId)"

# ----------------------------------------------------------------------------
# 1. Hitung identitas Camofox yang AKAN dipakai Hermes untuk profil ini
# ----------------------------------------------------------------------------
PROFILE_HOME="$HERMES_HOME_DIR/profiles/$PROFILE"
if [[ -z "${CAMOFOX_USER_ID:-}" ]]; then
  [[ -d "$PROFILE_HOME" ]] || die "profil '$PROFILE' belum terpasang di $PROFILE_HOME. Jalankan scripts/setup.sh."

  log "Menghitung identitas Camofox untuk profil '$PROFILE'"
  IDENTITY="$(HERMES_HOME="$PROFILE_HOME" TASK_ID="$TASK" python3 - <<'PY'
import os, uuid
from pathlib import Path
# Replikasi tools/browser_camofox_state.py:get_camofox_identity
home = os.environ["HERMES_HOME"]
scope_root = str(Path(home) / "browser_auth" / "camofox")
logical = os.environ.get("TASK_ID") or "default"
ud = uuid.uuid5(uuid.NAMESPACE_URL, f"camofox-user:{scope_root}").hex[:10]
sd = uuid.uuid5(uuid.NAMESPACE_URL, f"camofox-session:{scope_root}:{logical}").hex[:16]
print(f"hermes_{ud} task_{sd}")
PY
)"
  USER_ID="$(echo "$IDENTITY" | cut -d' ' -f1)"
  SESSION_KEY="$(echo "$IDENTITY" | cut -d' ' -f2)"
else
  USER_ID="$CAMOFOX_USER_ID"
  SESSION_KEY="${CAMOFOX_SESSION_KEY:-default}"
  warn "CAMOFOX_USER_ID diset di .env -> semua profil berbagi satu identitas browser"
fi

ok "userId    : $USER_ID"
ok "sessionKey: $SESSION_KEY"

# ----------------------------------------------------------------------------
# 2. Cek Camofox hidup
# ----------------------------------------------------------------------------
log "Memeriksa Camofox di $CAMOFOX_URL"
if ! curl -fsS "$CAMOFOX_URL/health" >/dev/null 2>&1; then
  die "Camofox tidak merespons /health. Jalankan scripts/start-browser.sh dulu."
fi
ok "Camofox hidup"

# ----------------------------------------------------------------------------
# 3. Buka halaman login di browser persisten
# ----------------------------------------------------------------------------
log "Membuka $URL"
PAYLOAD="$(python3 -c 'import json,sys; print(json.dumps({"userId":sys.argv[1],"sessionKey":sys.argv[2],"url":sys.argv[3]}))' \
  "$USER_ID" "$SESSION_KEY" "$URL")"

RESP="$(curl -sS -X POST "$CAMOFOX_URL/tabs" \
  -H 'Content-Type: application/json' \
  ${CAMOFOX_ACCESS_KEY:+-H "Authorization: Bearer $CAMOFOX_ACCESS_KEY"} \
  -d "$PAYLOAD")" || die "gagal membuat tab"

TAB_ID="$(echo "$RESP" | python3 -c 'import json,sys
try:
    d=json.load(sys.stdin)
    print(d.get("tabId") or d.get("tab_id") or (d.get("tabs") or [{}])[0].get("tabId",""))
except Exception:
    print("")' 2>/dev/null || true)"

if [[ -n "$TAB_ID" ]]; then
  ok "tab dibuka: $TAB_ID"
else
  warn "respons tidak mengandung tabId yang dikenal; jawaban server:"
  echo "    $RESP"
fi

# ----------------------------------------------------------------------------
# 4. Serahkan ke manusia lewat GUI
# ----------------------------------------------------------------------------
echo
echo "=============================================================="
echo "  GUI BROWSER SIAP — ambil alih sekarang"
echo "=============================================================="
echo
echo "  Buka di browser Anda:"
echo "      http://localhost:${NOVNC_PORT}/vnc.html"
[[ -n "${VNC_PASSWORD:-}" ]] && echo "  Password VNC: (sudah diset di .env)"
echo
echo "  Yang harus Anda lakukan:"
echo "    1. Selesaikan login (username, password, MFA, CAPTCHA)"
echo "    2. Pastikan dashboard sudah terlihat login"
echo "    3. Tekan Enter di sini kalau sudah selesai"
echo
echo "  Agent TIDAK boleh dan TIDAK akan mengerjakan langkah ini."
echo "=============================================================="
echo
read -r -p "  Sudah selesai login? [Enter untuk lanjut] " _

# ----------------------------------------------------------------------------
# 5. Ekspor storage state sebagai cadangan
# ----------------------------------------------------------------------------
if [[ -n "${CAMOFOX_API_KEY:-}" ]]; then
  OUT="$REPO_ROOT/data/campaigns/storage-state-$PROFILE.json"
  mkdir -p "$(dirname "$OUT")"
  log "Mengekspor storage state ke $OUT"
  if curl -fsS "$CAMOFOX_URL/sessions/$USER_ID/storage_state" \
       -H "Authorization: Bearer $CAMOFOX_API_KEY" -o "$OUT"; then
    chmod 600 "$OUT"
    ok "storage state tersimpan (mode 600)"
    warn "File ini berisi COOKIE/SESSION — jangan pernah di-commit."
  else
    warn "gagal mengekspor storage state (endpoint butuh CAMOFOX_API_KEY diset di server)"
  fi
else
  warn "CAMOFOX_API_KEY kosong — lewati ekspor storage state."
  echo "    Plugin persistence tetap menyimpan state ke volume secara otomatis."
fi

echo
ok "Selesai. Worker '$PROFILE' sekarang bisa memakai sesi yang sudah login."
echo
echo "  Uji: hermes --profile $PROFILE chat -q \"Buka $URL dan konfirmasi sudah login\""
