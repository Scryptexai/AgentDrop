#!/usr/bin/env bash
# ============================================================================
# install-cron.sh — pasang jadwal otomatis pakai CRON INTERNAL Hermes
# ============================================================================
# KENAPA BUKAN SYSTEM CRONTAB
# ---------------------------
# Hermes punya scheduler sendiri: ticker in-process 60 detik
# (cron/scheduler.py), dengan job disimpan di tabel SQLite milik Hermes dan
# dikelola lewat `hermes cron ...`. Job cron Hermes dapat:
#   - preflight validation (cek API key + skill + delivery SEBELUM jalan)
#   - model_drift_guard (fail-closed kalau model global berubah)
#   - --skill / --workdir / --deliver / --reasoning-effort per job
#   - pencatatan run history via `hermes cron runs`
#
# System crontab tidak memberi semua itu, dan job-nya tidak terlihat oleh
# `hermes cron list`. Jadi kita pakai scheduler Hermes.
#
# SINTAKS TERVERIFIKASI (hermes_cli/subcommands/cron.py):
#   hermes cron create <schedule> [prompt] \
#     [--name N] [--deliver T] [--skill S] [--workdir W] \
#     [--model M] [--reasoning-effort L] [--continuity]
#
#   schedule: '30m' | 'every 2h' | '0 9 * * *'
#
# Job bersifat PER-PROFIL (cron disimpan di HERMES_HOME profil), jadi tiap
# job dibuat dengan --profile yang sesuai.
# ============================================================================
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HERMES_HOME_DIR="${HERMES_HOME:-$HOME/.hermes}"

log()  { printf '\033[1;34m==>\033[0m %s\n' "$*"; }
ok()   { printf '\033[1;32m  ✓\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m  !\033[0m %s\n' "$*"; }
die()  { printf '\033[1;31m  ✗ %s\033[0m\n' "$*" >&2; exit 1; }

command -v hermes >/dev/null 2>&1 || die "'hermes' tidak ada di PATH."

# Zona waktu: cron Hermes mengikuti waktu sistem. Tampilkan supaya operator
# tahu jam berapa job-nya benar-benar jalan.
log "Zona waktu sistem: $(date +%Z) ($(date '+%Y-%m-%d %H:%M'))"
warn "Jadwal di bawah memakai waktu sistem. Kalau Anda mau 09:00 WIB, pastikan sistem di WIB."

# ----------------------------------------------------------------------------
# Ke mana laporan dikirim.
# Default telegram: alur sistem ini berpusat di Telegram, jadi laporan harian
# dan mingguan harus sampai ke sana, bukan mengendap di data/logs/.
# Ganti lewat env kalau perlu:  CRON_DELIVER=local bash scripts/install-cron.sh
# ----------------------------------------------------------------------------
DELIVER="${CRON_DELIVER:-telegram}"

if [[ "$DELIVER" == "telegram" ]]; then
  if [[ -z "${TELEGRAM_BOT_TOKEN:-}" ]] && ! grep -qE '^TELEGRAM_BOT_TOKEN=.+' "$REPO_ROOT/.env" 2>/dev/null; then
    warn "TELEGRAM_BOT_TOKEN belum diisi — laporan tidak akan terkirim."
    warn "Isi .env dulu, atau pakai:  CRON_DELIVER=local bash $0"
  fi
fi
log "Laporan cron akan dikirim ke: $DELIVER"

# ----------------------------------------------------------------------------
# Helper: buat job hanya kalau belum ada (idempotent)
# ----------------------------------------------------------------------------
create_job() {
  local profile="$1" schedule="$2" prompt="$3" name="$4" skill="$5" reasoning="$6"

  local profile_dir="$HERMES_HOME_DIR/profiles/$profile"
  [[ -d "$profile_dir" ]] || { warn "profil $profile belum terpasang — lewati $name"; return 0; }

  # Cek apakah job dengan nama ini sudah ada.
  if hermes --profile "$profile" cron list 2>/dev/null | grep -qF "$name"; then
    ok "$name sudah ada — dilewati"
    return 0
  fi

  log "Membuat job: $name (profil $profile, '$schedule')"
  hermes --profile "$profile" cron create "$schedule" "$prompt" \
    --name "$name" \
    --skill "$skill" \
    --workdir "$REPO_ROOT" \
    --reasoning-effort "$reasoning" \
    --deliver "$DELIVER" \
    && ok "$name" \
    || warn "gagal membuat $name"
}

# ----------------------------------------------------------------------------
# JADWAL
# ----------------------------------------------------------------------------
# 09:00 — daily check-in semua campaign
create_job worker-daily "0 9 * * *" \
  "Jalankan daily check-in untuk semua campaign aktif. Baca data/campaigns/ dulu, verifikasi status login sebelum aksi, ambil screenshot bukti, lalu update progress.json. Kalau ketemu CAPTCHA atau sesi mati, hentikan campaign itu dan catat." \
  "airdrop-daily-checkin" "daily-executor" "medium"

# 13:00 — verifikasi tengah hari
create_job worker-monitor "0 13 * * *" \
  "Verifikasi semua aksi pagi ini benar-benar tercatat. Cocokkan progress.json dengan screenshot yang ada. Klaim tanpa bukti harus dilaporkan sebagai temuan, bukan diterima diam-diam." \
  "airdrop-midday-verify" "portfolio-tracker" "medium"

# 20:00 — laporan harian
create_job worker-monitor "0 20 * * *" \
  "Buat laporan progres harian. Sebutkan apa yang jalan, apa yang gagal, dan apa yang butuh tindakan manusia. Tulis ke data/logs/. Jangan mengarang angka — kalau data kurang, katakan data kurang." \
  "airdrop-daily-report" "portfolio-tracker" "medium"

# Minggu 21:00 — ringkasan mingguan + rekomendasi lanjut/berhenti
create_job worker-monitor "0 21 * * 0" \
  "Buat ringkasan mingguan semua campaign: hari aktif, total poin, tren, dan rekomendasi LANJUT / EVALUASI / BERHENTI beserta alasannya. Strategi kita fokus 3-5 proyek, jadi jangan ragu merekomendasikan berhenti untuk campaign yang tidak produktif." \
  "airdrop-weekly-summary" "portfolio-tracker" "high"

# ----------------------------------------------------------------------------
# Verifikasi
# ----------------------------------------------------------------------------
echo
log "Job terpasang per profil:"
for p in worker-daily worker-monitor; do
  echo "  --- $p ---"
  hermes --profile "$p" cron list 2>/dev/null || warn "  (tidak bisa membaca cron list untuk $p)"
done

echo
log "Status scheduler:"
for p in worker-daily worker-monitor; do
  hermes --profile "$p" cron status 2>/dev/null || true
done

echo
ok "Selesai."
echo
echo "Catatan: scheduler Hermes berjalan in-process. Agar job benar-benar"
echo "tereksekusi saat Anda tidak sedang chat, jalankan gateway:"
echo "  agentdrop start"
echo
echo "Jangan jalankan gateway per profil. Config menyalakan"
echo "gateway.multiplex_profiles: true, jadi gateway default yang melayani"
echo "semua profil dan menjalankan cron job tiap profil. Tanpa flag itu ticker"
echo "hanya membaca HERMES_HOME default, dan job di profil lain tidak pernah"
echo "jalan meski next_run_at-nya terisi (gateway/run.py:31774)."
