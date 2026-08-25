#!/usr/bin/env bash
# ============================================================================
# start-gateway.sh — nyalakan bot Telegram (UI utama AgentDrop)
# ============================================================================
# Setelah ini jalan, alurnya sesederhana:
#
#   Anda forward pengumuman airdrop ke bot Telegram
#        ↓
#   worker-orchestrator menerimanya
#        ↓
#   parse + klasifikasi task (skill airdrop-intake)
#        ↓
#   balas dengan rencana: apa yang bisa agent kerjakan, apa yang butuh Anda
#        ↓
#   Anda balas "ya"  →  orchestrator delegate_task ke worker
#
# Dua mode gateway Hermes (hermes_cli/subcommands/gateway.py):
#   `gateway run`   — foreground. Direkomendasikan untuk WSL, Docker, Termux.
#   `gateway start` — service systemd/launchd di background.
# ============================================================================
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HERMES_HOME_DIR="${HERMES_HOME:-$HOME/.hermes}"
PROFILE="worker-orchestrator"
FOREGROUND=0

[[ "${1:-}" == "--foreground" || "${1:-}" == "-f" ]] && FOREGROUND=1

log()  { printf '\033[1;34m==>\033[0m %s\n' "$*"; }
ok()   { printf '\033[1;32m  ✓\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m  !\033[0m %s\n' "$*"; }
die()  { printf '\033[1;31m  ✗ %s\033[0m\n' "$*" >&2; exit 1; }

command -v hermes >/dev/null 2>&1 || die "'hermes' tidak ada di PATH."

PROFILE_DIR="$HERMES_HOME_DIR/profiles/$PROFILE"
[[ -d "$PROFILE_DIR" ]] || die "profil '$PROFILE' belum terpasang. Jalankan scripts/setup.sh."
[[ -f "$PROFILE_DIR/.env" ]] || die "profil '$PROFILE' tidak punya .env. Jalankan scripts/setup.sh."

# ----------------------------------------------------------------------------
# Cek konfigurasi Telegram SEBELUM menyalakan gateway
# ----------------------------------------------------------------------------
log "Memeriksa konfigurasi Telegram"
# shellcheck disable=SC1091
set -a; source "$PROFILE_DIR/.env"; set +a

if [[ -z "${TELEGRAM_BOT_TOKEN:-}" ]]; then
  die "TELEGRAM_BOT_TOKEN kosong. Buat bot di @BotFather, isi di .env, lalu
      ulangi:  bash scripts/setup.sh   (untuk menyebar .env ke semua profil)"
fi
ok "TELEGRAM_BOT_TOKEN terisi"

if [[ -z "${TELEGRAM_ALLOWED_USERS:-}" ]]; then
  warn "TELEGRAM_ALLOWED_USERS KOSONG."
  warn "Bot akan menerima perintah dari SIAPA PUN yang menemukan username-nya."
  warn "Ambil user ID Anda dari @userinfobot, isi di .env, lalu setup ulang."
  echo
  read -r -p "  Lanjutkan tanpa allowlist? [y/N] " j
  [[ "$j" =~ ^[Yy]$ ]] || die "Dibatalkan. Isi TELEGRAM_ALLOWED_USERS dulu."
else
  ok "TELEGRAM_ALLOWED_USERS: $TELEGRAM_ALLOWED_USERS"
fi

# ----------------------------------------------------------------------------
# Nyalakan
# ----------------------------------------------------------------------------
cd "$REPO_ROOT"

if [[ "$FOREGROUND" -eq 1 ]]; then
  log "Menjalankan gateway di foreground (Ctrl-C untuk berhenti)"
  exec hermes --profile "$PROFILE" gateway run
fi

log "Menyalakan gateway sebagai service background"
if hermes --profile "$PROFILE" gateway start 2>/dev/null; then
  ok "gateway jalan di background"
else
  warn "'gateway start' gagal (mungkin systemd/launchd tidak tersedia)."
  warn "Jalankan di foreground saja:  $0 --foreground"
  exit 1
fi

echo
echo "Bot siap. Coba kirim ke bot Anda:"
echo
echo "  🔈 Contoh Airdrop"
echo "  ➖ Register"
echo "  https://contoh.com/register?r=KODE"
echo "  ➖ Connect EVM Wallet"
echo "  ➖ Complete Daily Mission"
echo "  ➖ Done"
echo
echo "Orchestrator akan membalas dengan rencana, lalu menunggu 'ya' dari Anda."
echo
echo "Perintah berguna:"
echo "  hermes --profile $PROFILE gateway stop     # matikan"
echo "  hermes --profile $PROFILE gateway restart  # restart"
echo "  tail -f $PROFILE_DIR/logs/*.log            # lihat log"
