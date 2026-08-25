#!/usr/bin/env bash
# ============================================================================
# start-agent.sh — jalankan Hermes AgentDrop (interaktif atau sekali jalan)
# ============================================================================
# Pemakaian:
#   ./scripts/start-agent.sh                      # chat interaktif, profil default
#   ./scripts/start-agent.sh worker-analyzer      # chat interaktif, profil tertentu
#   ./scripts/start-agent.sh worker-daily "Jalankan check-in harian"   # sekali jalan
#
# CATATAN PENTING soal sintaks:
#   `hermes chat` TIDAK menerima argumen posisional. Ia hanya menerima
#   -q/--query atau --query-file, dan keduanya saling eksklusif
#   (hermes_cli/_parser.py, mutually exclusive group).
#   Karena itu prompt selalu dilewatkan lewat -q di skrip ini.
#
#   `--profile/-p` di-scan sebelum argparse dan di-strip dari argv
#   (hermes_cli/main.py:_apply_profile_override), jadi boleh diletakkan
#   sebelum ATAU sesudah subcommand. Di sini kita taruh di depan.
# ============================================================================
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PROFILE="${1:-}"
PROMPT="${2:-}"

die() { printf '\033[1;31m  ✗ %s\033[0m\n' "$*" >&2; exit 1; }

command -v hermes >/dev/null 2>&1 || die "'hermes' tidak ada di PATH. Jalankan install.sh, lalu 'source ~/.bashrc'."

# Validasi profil terhadap yang benar-benar terpasang.
VALID_PROFILES=(worker-analyzer worker-daily worker-quests worker-discord worker-monitor)
if [[ -n "$PROFILE" ]]; then
  found=0
  for p in "${VALID_PROFILES[@]}"; do
    [[ "$p" == "$PROFILE" ]] && found=1
  done
  [[ "$found" -eq 1 ]] || die "Profil '$PROFILE' tidak dikenal. Yang tersedia: ${VALID_PROFILES[*]}"

  PROFILE_DIR="${HERMES_HOME:-$HOME/.hermes}/profiles/$PROFILE"
  [[ -d "$PROFILE_DIR" ]] || die "Profil '$PROFILE' belum terpasang di $PROFILE_DIR. Jalankan scripts/setup.sh dulu."
  [[ -f "$PROFILE_DIR/.env" ]] || die "Profil '$PROFILE' tidak punya .env. Jalankan scripts/setup.sh dulu."
fi

ARGS=()
[[ -n "$PROFILE" ]] && ARGS+=(--profile "$PROFILE")
ARGS+=(chat)
[[ -n "$PROMPT" ]] && ARGS+=(-q "$PROMPT")

cd "$REPO_ROOT"

echo "Menjalankan: hermes ${ARGS[*]}"
echo
exec hermes "${ARGS[@]}"
