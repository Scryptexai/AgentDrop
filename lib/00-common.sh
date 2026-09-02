# lib/00-common.sh — helper bersama. Di-source, tidak dijalankan langsung.
# Jangan panggil berkas di direktori ini sendiri; lewat ./install.sh atau ./agentdrop.

# shellcheck disable=SC2034
LIB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC2034
REPO_ROOT="$(cd "$LIB_DIR/.." && pwd)"

HERMES_HOME_DIR="${HERMES_HOME:-$HOME/.hermes}"
STATE_DIR="$HOME/.agentdrop"
LOG_DIR="${AGENTDROP_LOG_DIR:-$STATE_DIR/logs}"
PROFILE_DIR="${CDP_PROFILE_DIR:-$STATE_DIR/chrome-profile}"
EXT_ROOT="${CDP_EXT_ROOT:-$REPO_ROOT/extensions/installed}"
CDP_PORT="${CDP_PORT:-9222}"
NOVNC_PORT="${NOVNC_PORT:-6080}"
VNC_PORT="${VNC_PORT:-5900}"
DISPLAY_NUM="${CDP_DISPLAY:-99}"
RESOLUTION="${CDP_RESOLUTION:-1920x1080x24}"

_log()  { printf '\033[1;34m==> %s\033[0m\n' "$*"; }
_ok()   { printf '\033[1;32m  ✓\033[0m %s\n' "$*"; }
_warn() { printf '\033[1;33m  !\033[0m %s\n' "$*"; }
_err()  { printf '\033[1;31m  ✗ %s\033[0m\n' "$*" >&2; }
_die()  { _err "$*"; exit 1; }

_pyu() {  # python yang punya PyYAML: venv proyek kalau ada, kalau tidak python3
  if [[ -x "$STATE_DIR/venv/bin/python" ]]; then echo "$STATE_DIR/venv/bin/python"
  else echo python3; fi
}

# Interpreter Python milik Hermes.
#
# Kenapa tidak python3 sistem: jembatan harus bisa `import run_agent`, dan modul
# itu hanya ada di lingkungan Hermes. Kita tidak bisa menebak lokasi pemasangannya
# (installer upstream tidak bisa dibaca dari sandbox), jadi kita BACA shebang
# binari `hermes` -- console_script pip selalu menunjuk persis ke interpreter
# lingkungannya sendiri.
#
# Gagal diam-diam di sini berarti REPL jalan dengan python3 sistem lalu mati
# dengan ImportError yang membingungkan. Jadi kegagalannya dibuat jelas.
python_hermes() {
  local _bin _py _line _cand
  for _bin in hermes hermes-agent; do
    command -v "$_bin" >/dev/null 2>&1 || continue
    _bin="$(command -v "$_bin")"
    _line="$(head -1 "$_bin" 2>/dev/null || true)"
    [[ "$_line" == '#!'* ]] || continue
    _py="${_line#\#!}"; _py="${_py##* }"          # ambil token terakhir
    [[ "$_py" == *python* ]] || continue
    if [[ "$_py" == /* && -x "$_py" ]]; then echo "$_py"; return 0; fi
    _cand="$(command -v "$_py" 2>/dev/null || true)"
    [[ -n "$_cand" ]] && { echo "$_cand"; return 0; }
  done
  return 1
}
