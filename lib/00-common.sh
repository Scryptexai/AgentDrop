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
SIGNER_PORT="${AGENTDROP_SIGNER_PORT:-9721}"

_log()  { printf '\033[1;34m==> %s\033[0m\n' "$*"; }
_ok()   { printf '\033[1;32m  ✓\033[0m %s\n' "$*"; }
_warn() { printf '\033[1;33m  !\033[0m %s\n' "$*"; }
_err()  { printf '\033[1;31m  ✗ %s\033[0m\n' "$*" >&2; }
_die()  { _err "$*"; exit 1; }

_pyu() {  # python yang punya PyYAML: venv proyek kalau ada, kalau tidak python3
  if [[ -x "$STATE_DIR/venv/bin/python" ]]; then echo "$STATE_DIR/venv/bin/python"
  else echo python3; fi
}
