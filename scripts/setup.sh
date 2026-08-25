#!/usr/bin/env bash
# ============================================================================
# setup.sh — pasang config, profil, skill, dan secret Hermes AgentDrop
# ============================================================================
# Aman dijalankan berulang kali (idempotent). Tidak menginstal Hermes itu
# sendiri — itu tugas install.sh.
#
# Yang dilakukan:
#   1. Cek .env ada dan tidak berisi nilai placeholder
#   2. Pasang config.yaml + SOUL.md ke ~/.hermes/
#   3. Buat 5 profil worker di ~/.hermes/profiles/<name>/
#   4. Pasang skill ke ~/.hermes/skills/ DAN ke tiap profil
#      (profil adalah HERMES_HOME terpisah, jadi butuh salinan sendiri)
#   5. Pasang .env ke ~/.hermes/.env dan tiap profil
# ============================================================================
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HERMES_HOME_DIR="${HERMES_HOME:-$HOME/.hermes}"
# worker-orchestrator adalah pintu masuk Telegram; yang lain worker eksekusi.
PROFILES=(worker-orchestrator worker-analyzer worker-daily worker-quests worker-discord worker-monitor)
# airdrop-intake adalah langkah WAJIB pertama: parse + klasifikasi sebelum eksekusi.
# browser-operation = protokol dasar yang dirujuk skill browser lainnya.
SKILLS=(browser-operation browser-burn-in airdrop-intake airdrop-analyzer daily-executor quest-executor discord-engager portfolio-tracker)

log()  { printf '\033[1;34m==>\033[0m %s\n' "$*"; }
ok()   { printf '\033[1;32m  ✓\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m  !\033[0m %s\n' "$*"; }
die()  { printf '\033[1;31m  ✗ %s\033[0m\n' "$*" >&2; exit 1; }

# ----------------------------------------------------------------------------
# 0. Sanity: jangan pernah jalan sebagai root
# ----------------------------------------------------------------------------
if [[ "${EUID:-$(id -u)}" -eq 0 ]]; then
  die "Jangan jalankan sebagai root. Hermes memasang ke \$HOME user biasa."
fi

# ----------------------------------------------------------------------------
# 1. .env
# ----------------------------------------------------------------------------
log "Memeriksa .env"
if [[ ! -f "$REPO_ROOT/.env" ]]; then
  die ".env belum ada. Jalankan: cp .env.example .env  lalu isi API key Anda."
fi

# Tolak kalau API key masih placeholder dari template.
if grep -qE '^(ANTHROPIC_API_KEY|OPENROUTER_API_KEY|OPENAI_API_KEY|GOOGLE_API_KEY|NOUS_API_KEY|CUSTOM_API_KEY)=sk-.*xxx' "$REPO_ROOT/.env"; then
  die ".env masih berisi nilai placeholder 'sk-...xxx'. Ganti dengan API key asli."
fi

# Tolak kalau ada private key / seed — ini bukan tempatnya.
if grep -qiE '^(PRIVATE_KEY|SECRET_KEY|MNEMONIC|SEED_PHRASE)=' "$REPO_ROOT/.env"; then
  die "Ditemukan field private key / seed di .env. Hapus. AgentDrop tidak pernah menyimpan private key."
fi
ok ".env ada"

# ----------------------------------------------------------------------------
# 2. Config utama + SOUL.md
# ----------------------------------------------------------------------------
log "Memasang config utama ke $HERMES_HOME_DIR"
mkdir -p "$HERMES_HOME_DIR"

for f in config.yaml SOUL.md; do
  if [[ -f "$REPO_ROOT/config/hermes/$f" ]]; then
    if [[ -f "$HERMES_HOME_DIR/$f" ]] && ! diff -q "$REPO_ROOT/config/hermes/$f" "$HERMES_HOME_DIR/$f" >/dev/null; then
      cp "$HERMES_HOME_DIR/$f" "$HERMES_HOME_DIR/$f.bak.$(date +%s)"
      warn "$f sudah ada dan berbeda — versi lama dibackup sebagai $f.bak.*"
    fi
    cp "$REPO_ROOT/config/hermes/$f" "$HERMES_HOME_DIR/$f"
    ok "$f"
  fi
done

# ----------------------------------------------------------------------------
# 3. Secret: .env -> ~/.hermes/.env
#    Hermes WAJIB menyimpan secret di .env, bukan di config.yaml.
# ----------------------------------------------------------------------------
log "Memasang secret"
install -m 600 "$REPO_ROOT/.env" "$HERMES_HOME_DIR/.env"
ok "~/.hermes/.env (mode 600)"

# ----------------------------------------------------------------------------
# 4. Profil worker
# ----------------------------------------------------------------------------
log "Memasang profil worker"
for p in "${PROFILES[@]}"; do
  src="$REPO_ROOT/config/hermes/profiles/$p"
  dst="$HERMES_HOME_DIR/profiles/$p"
  [[ -d "$src" ]] || { warn "profile $p tidak ditemukan di repo, dilewati"; continue; }

  mkdir -p "$dst/skills" "$dst/memories" "$dst/logs" "$dst/cron"

  cp "$src/config.yaml" "$dst/config.yaml"
  [[ -f "$src/SOUL.md" ]] && cp "$src/SOUL.md" "$dst/SOUL.md"

  # Tiap profil adalah HERMES_HOME terpisah -> butuh .env sendiri.
  install -m 600 "$REPO_ROOT/.env" "$dst/.env"

  # Skill juga harus ada di tiap profil.
  for s in "${SKILLS[@]}"; do
    if [[ -d "$REPO_ROOT/skills/$s" ]]; then
      mkdir -p "$dst/skills/$s"
      cp -r "$REPO_ROOT/skills/$s/." "$dst/skills/$s/"
    fi
  done

  ok "profil $p"
done

# ----------------------------------------------------------------------------
# 5. Skill di HERMES_HOME utama juga (untuk `hermes` tanpa --profile)
# ----------------------------------------------------------------------------
log "Memasang skill ke HERMES_HOME utama"
mkdir -p "$HERMES_HOME_DIR/skills"
for s in "${SKILLS[@]}"; do
  if [[ -d "$REPO_ROOT/skills/$s" ]]; then
    mkdir -p "$HERMES_HOME_DIR/skills/$s"
    cp -r "$REPO_ROOT/skills/$s/." "$HERMES_HOME_DIR/skills/$s/"
    ok "skill $s"
  fi
done

# ----------------------------------------------------------------------------
# 6. Struktur data
# ----------------------------------------------------------------------------
log "Menyiapkan struktur data"
mkdir -p "$REPO_ROOT/data/campaigns" "$REPO_ROOT/data/logs" "$REPO_ROOT/data/screenshots"
ok "data/{campaigns,logs,screenshots}"

# ----------------------------------------------------------------------------
# 7. Verifikasi
# ----------------------------------------------------------------------------
if command -v hermes >/dev/null 2>&1; then
  log "Menjalankan 'hermes doctor'"
  hermes doctor || warn "hermes doctor mengembalikan error — periksa output di atas"
  log "Profil terpasang:"
  hermes profile list 2>/dev/null || warn "'hermes profile list' gagal (mungkin versi Hermes berbeda)"
else
  warn "'hermes' belum ada di PATH. Jalankan install.sh dulu, atau 'source ~/.bashrc'."
fi

echo
ok "Setup selesai."
echo
echo "Langkah berikutnya:"
echo "  1. ./scripts/start-browser.sh          # nyalakan Camofox"
echo "  2. ./scripts/install-cron.sh           # pasang jadwal cron Hermes"
echo "  3. hermes --profile worker-analyzer chat -q \"Analisis proyek: <URL>\""
