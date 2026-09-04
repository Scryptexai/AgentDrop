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

# ---------------------------------------------------------------------------
# hentikan_pola_proses <pola> [<pola> ...]
#
# Mematikan proses yang baris perintahnya cocok dengan salah satu pola:
# SIGTERM, tunggu, lalu SIGKILL untuk yang masih hidup. Mengembalikan jumlah
# proses yang berhasil di-SIGTERM.
#
# Kenapa tidak `pkill -f` saja: `pgrep`/`pkill -f` mencocokkan SUBSTRING di
# baris perintah proses apa pun. Pola "hermes .*gateway" ikut mencocokkan
# shell yang sedang menjalankan perintah grep itu sendiri. Dalam pengujian,
# KELIMA pola penghentian cocok ke shell penguji sekaligus hanya karena teks
# polanya ada di baris perintahnya. Jadi setiap kandidat disaring dulu.
# ---------------------------------------------------------------------------
_pid_layak_dimatikan() {  # _pid_layak_dimatikan <pid>
  [[ "$1" =~ ^[0-9]+$ ]] || return 1
  case " $$ ${PPID:-0} " in *" $1 "*) return 1 ;; esac
  # Satu grup proses dengan kita = shell yang menjalankan skrip ini, atau
  # saudaranya. Service yang asli selalu di grupnya sendiri.
  local _g _grup
  _grup="$(ps -o pgid= -p $$ 2>/dev/null | tr -d ' ')"
  _g="$(ps -o pgid= -p "$1" 2>/dev/null | tr -d ' ')"
  [[ -n "$_g" && -n "$_grup" && "$_g" == "$_grup" ]] && return 1
  # Shell sebaris (`bash -c ...`, `sh -c ...`) dicoret: itu cara pola ini
  # biasanya ikut cocok. Gateway/Chrome/Xvfb/x11vnc/websockify yang asli
  # bukan shell sebaris.
  local _c
  _c="$(tr '\0' ' ' < "/proc/$1/cmdline" 2>/dev/null)"
  case "$_c" in
    */bash\ -c*|*/sh\ -c*|bash\ -c*|sh\ -c*) return 1 ;;
  esac
  return 0
}

hentikan_pola_proses() {  # hentikan_pola_proses <pola>...
  local _pola _pid _mati=0 _calon=""
  _kandidat_proses() {
    local _p
    for _p in "$@"; do pgrep -f -- "$_p" 2>/dev/null; done
  }
  for _pid in $(_kandidat_proses "$@"); do
    _pid_layak_dimatikan "$_pid" || continue
    case " $_calon " in *" $_pid "*) continue ;; esac
    _calon="$_calon $_pid"
  done
  for _pid in $_calon; do
    kill "$_pid" 2>/dev/null && _mati=$((_mati + 1))
  done
  [[ -n "${_calon// /}" ]] && sleep 2
  for _pid in $_calon; do
    kill -0 "$_pid" 2>/dev/null && kill -9 "$_pid" 2>/dev/null
  done
  echo "$_mati"
}
