#!/usr/bin/env bash
# ============================================================================
# install.sh — One-click installer untuk Hermes Airdrop Agent (AgentDrop)
# ============================================================================
# Pemakaian:
#   curl -fsSL https://raw.githubusercontent.com/<user>/AgentDrop/main/install.sh | bash
#
# Atau, lebih aman (dan yang kami rekomendasikan) — unduh, baca, baru jalankan:
#   curl -fsSL https://raw.githubusercontent.com/<user>/AgentDrop/main/install.sh -o install.sh
#   less install.sh
#   bash install.sh
#
# Skrip ini TIDAK mem-pipe curl langsung ke bash untuk komponen apa pun.
# Installer Hermes diunduh ke file dulu supaya bisa Anda periksa.
# ============================================================================
set -euo pipefail

REPO_URL="${AGENTDROP_REPO:-https://github.com/Scryptexai/AgentDrop.git}"
INSTALL_DIR="${AGENTDROP_DIR:-$HOME/AgentDrop}"
HERMES_INSTALLER="https://hermes-agent.nousresearch.com/install.sh"
HERMES_INSTALLER_ALT="https://raw.githubusercontent.com/NousResearch/hermes-agent/main/scripts/install.sh"

log()  { printf '\033[1;34m==>\033[0m %s\n' "$*"; }
ok()   { printf '\033[1;32m  ✓\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m  !\033[0m %s\n' "$*"; }
die()  { printf '\033[1;31m  ✗ %s\033[0m\n' "$*" >&2; exit 1; }

echo "======================================================"
echo "  Hermes Airdrop Agent (AgentDrop) — Installer"
echo "======================================================"
echo

# ----------------------------------------------------------------------------
# 0. Jangan root
# ----------------------------------------------------------------------------
if [[ "${EUID:-$(id -u)}" -eq 0 ]]; then
  die "Jangan jalankan sebagai root/sudo. Hermes memasang ke \$HOME user biasa."
fi

# ----------------------------------------------------------------------------
# 1. Deteksi OS
# ----------------------------------------------------------------------------
log "Mendeteksi sistem"
case "$(uname -s)" in
  Linux*)  OS=linux ;;
  Darwin*) OS=macos ;;
  MINGW*|MSYS*|CYGWIN*) die "Windows native belum didukung skrip ini. Pakai WSL2." ;;
  *)       die "OS tidak dikenal: $(uname -s)" ;;
esac
ok "$OS ($(uname -m))"

# ----------------------------------------------------------------------------
# 2. Dependency dasar
# ----------------------------------------------------------------------------
log "Memeriksa dependency dasar"
missing=()
for c in git curl; do
  command -v "$c" >/dev/null 2>&1 || missing+=("$c")
done

if [[ ${#missing[@]} -gt 0 ]]; then
  log "Menginstal: ${missing[*]}"
  if [[ "$OS" == "linux" ]]; then
    if command -v apt-get >/dev/null 2>&1; then
      sudo apt-get update -y && sudo apt-get install -y "${missing[@]}" ca-certificates
    elif command -v dnf >/dev/null 2>&1; then
      sudo dnf install -y "${missing[@]}" ca-certificates
    elif command -v pacman >/dev/null 2>&1; then
      sudo pacman -Sy --noconfirm "${missing[@]}"
    else
      die "Tidak tahu package manager untuk menginstal ${missing[*]}. Instal manual dulu."
    fi
  else
    command -v brew >/dev/null 2>&1 || die "Butuh Homebrew di macOS: https://brew.sh"
    brew install "${missing[@]}"
  fi
fi
ok "git + curl tersedia"

# ----------------------------------------------------------------------------
# 2b. Docker — WAJIB untuk Camofox (browser GUI)
# ----------------------------------------------------------------------------
if command -v docker >/dev/null 2>&1; then
  ok "docker sudah ada: $(docker --version 2>/dev/null | head -1)"
else
  log "Menginstal Docker (dibutuhkan untuk browser Camofox)"
  if [[ "$OS" == "linux" ]]; then
    # get.docker.com adalah jalur resmi yang direkomendasikan Docker.
    # Unduh ke file dulu supaya bisa diperiksa, konsisten dengan installer Hermes.
    tmp_docker="$(mktemp /tmp/get-docker.XXXXXX.sh)"
    curl -fsSL https://get.docker.com -o "$tmp_docker" || die "gagal mengunduh installer Docker"
    sudo sh "$tmp_docker"
    rm -f "$tmp_docker"
    # Izinkan user biasa memakai docker tanpa sudo.
    sudo usermod -aG docker "$USER" 2>/dev/null || true
    ok "docker terinstal"
    warn "Anda baru ditambahkan ke grup 'docker'. Logout-login dulu, atau jalankan:"
    warn "    newgrp docker"
  else
    die "Di macOS, instal Docker Desktop manual: https://docs.docker.com/get-docker/"
  fi
fi

# docker compose v2 (plugin) atau v1 (binary)
if docker compose version >/dev/null 2>&1 || command -v docker-compose >/dev/null 2>&1; then
  ok "docker compose tersedia"
else
  warn "docker compose tidak ada. Di Linux: sudo apt-get install -y docker-compose-plugin"
fi

# ----------------------------------------------------------------------------
# 2c. Python + PyYAML — dibutuhkan tools/validate_config.py
# ----------------------------------------------------------------------------
if command -v python3 >/dev/null 2>&1; then
  ok "python3 ada"
  if python3 -c "import yaml" >/dev/null 2>&1; then
    ok "PyYAML ada"
  else
    log "Menginstal PyYAML (dibutuhkan validator)"
    # PEP 668: banyak distro menandai Python sebagai externally-managed.
    # Coba pip biasa dulu, fallback ke --user, terakhir --break-system-packages.
    python3 -m pip install --quiet pyyaml 2>/dev/null \
      || python3 -m pip install --quiet --user pyyaml 2>/dev/null \
      || python3 -m pip install --quiet --break-system-packages pyyaml 2>/dev/null \
      || warn "gagal menginstal PyYAML. Validator akan dilewati."
    python3 -c "import yaml" >/dev/null 2>&1 && ok "PyYAML terpasang"
  fi
else
  warn "python3 tidak ada — validator akan dilewati."
fi

# ----------------------------------------------------------------------------
# 3. Instal Hermes Agent
# ----------------------------------------------------------------------------
if command -v hermes >/dev/null 2>&1; then
  ok "Hermes sudah terinstal: $(command -v hermes)"
else
  log "Mengunduh installer Hermes untuk diperiksa (tidak di-pipe langsung ke bash)"
  tmp_installer="$(mktemp /tmp/hermes-install.XXXXXX.sh)"
  if ! curl -fsSL "$HERMES_INSTALLER" -o "$tmp_installer" 2>/dev/null; then
    warn "URL utama gagal, coba mirror GitHub resmi..."
    curl -fsSL "$HERMES_INSTALLER_ALT" -o "$tmp_installer" || die "Gagal mengunduh installer Hermes dari kedua URL."
  fi
  ok "Installer tersimpan di $tmp_installer"

  echo
  echo "  Installer Hermes akan dijalankan. Ini memasang uv, Python 3.11,"
  echo "  Node.js, ripgrep, ffmpeg ke ~/.hermes."
  echo "  Tekan Ctrl-C sekarang kalau Anda mau membacanya dulu: less $tmp_installer"
  echo
  read -r -p "  Lanjutkan? [y/N] " jawab
  [[ "$jawab" =~ ^[Yy]$ ]] || die "Dibatalkan oleh user."

  bash "$tmp_installer"
  rm -f "$tmp_installer"

  # Installer menambahkan launcher ke shell rc; muat supaya `hermes` ada di PATH.
  # shellcheck disable=SC1090,SC1091
  [[ -f "$HOME/.bashrc" ]] && source "$HOME/.bashrc" 2>/dev/null || true
  # shellcheck disable=SC1090,SC1091
  [[ -f "$HOME/.zshrc" ]] && source "$HOME/.zshrc" 2>/dev/null || true
fi

# ----------------------------------------------------------------------------
# 4. Clone repo AgentDrop
# ----------------------------------------------------------------------------
if [[ -d "$INSTALL_DIR/.git" ]]; then
  log "Repo sudah ada di $INSTALL_DIR — git pull"
  git -C "$INSTALL_DIR" pull --ff-only
else
  log "Clone AgentDrop ke $INSTALL_DIR"
  git clone "$REPO_URL" "$INSTALL_DIR"
fi
ok "$INSTALL_DIR"

cd "$INSTALL_DIR"

# ----------------------------------------------------------------------------
# 5. .env
# ----------------------------------------------------------------------------
if [[ ! -f "$INSTALL_DIR/.env" ]]; then
  cp .env.example .env
  chmod 600 .env
  ok ".env dibuat dari .env.example (mode 600)"
  warn "EDIT $INSTALL_DIR/.env — isi API key Anda sebelum lanjut."
else
  ok ".env sudah ada, tidak ditimpa"
fi

# ----------------------------------------------------------------------------
# 6. Setup config + profil + skill
# ----------------------------------------------------------------------------
log "Menjalankan scripts/setup.sh"
chmod +x scripts/*.sh
bash scripts/setup.sh

# ----------------------------------------------------------------------------
# 7. Validasi statis
# ----------------------------------------------------------------------------
log "Menjalankan validator"
if python3 -c "import yaml" >/dev/null 2>&1; then
  python3 tools/validate_config.py || warn "Validator menemukan masalah — lihat output di atas."
else
  warn "PyYAML tidak tersedia, validator dilewati."
fi

# ----------------------------------------------------------------------------
# 8. Telegram (UI utama) — opsional tapi ini cara pakai yang direkomendasikan
# ----------------------------------------------------------------------------
echo
log "Menyiapkan Telegram sebagai UI"
echo "  Alur yang direkomendasikan: Anda forward pengumuman airdrop ke bot,"
echo "  orchestrator menganalisis & mengklasifikasi task, lalu mendelegasikan."
echo
set -a; # shellcheck disable=SC1091
source "$INSTALL_DIR/.env" 2>/dev/null || true; set +a

if [[ -n "${TELEGRAM_BOT_TOKEN:-}" ]]; then
  ok "TELEGRAM_BOT_TOKEN sudah terisi"
  [[ -z "${TELEGRAM_ALLOWED_USERS:-}" ]] && warn "TELEGRAM_ALLOWED_USERS masih kosong — bot terbuka untuk siapa pun!"
else
  warn "TELEGRAM_BOT_TOKEN kosong."
  echo "    1. Buka @BotFather di Telegram -> /newbot -> salin token"
  echo "    2. Isi di $INSTALL_DIR/.env"
  echo "    3. Ambil user ID Anda dari @userinfobot -> isi TELEGRAM_ALLOWED_USERS"
  echo "    4. Ulangi:  bash $INSTALL_DIR/scripts/setup.sh"
fi

# ----------------------------------------------------------------------------
# 9. Selesai
# ----------------------------------------------------------------------------
echo
echo "======================================================"
ok "Instalasi selesai."
echo "======================================================"
echo
echo "LANGKAH BERURUT:"
echo
echo "  1. Isi API key + Telegram:"
echo "       \$EDITOR $INSTALL_DIR/.env"
echo "     Lalu sebar ke semua profil:"
echo "       bash $INSTALL_DIR/scripts/setup.sh"
echo
echo "  2. Pilih model:"
echo "       hermes model"
echo
echo "  3. Nyalakan browser GUI (Camofox + noVNC):"
echo "       bash $INSTALL_DIR/scripts/start-browser.sh"
echo
echo "  4. Login VISUAL sekali per platform (agent tidak boleh mengerjakan ini):"
echo "       bash $INSTALL_DIR/scripts/takeover.sh worker-orchestrator https://x.com/login"
echo "     GUI-nya di: http://localhost:6080/vnc.html"
echo
echo "  5. BURN-IN dulu — jangan dilewati (stabilkan browser sebelum kerja):"
echo "       bash $INSTALL_DIR/scripts/burn-in.sh"
echo "     Uji 1-4 saja; Uji 5 (wallet) dan 6 (sosial) butuh flag eksplisit."
echo "     Tonton lewat noVNC saat berjalan — jangan cuma baca lognya."
echo
echo "  6. Nyalakan bot Telegram:"
echo "       bash $INSTALL_DIR/scripts/start-gateway.sh"
echo
echo "  7. Pakai. Kirim ke bot Anda:"
echo "       🔈 NamaAirdrop"
echo "       ➖ Register"
echo "       https://contoh.com/register?r=KODE"
echo "       ➖ Connect EVM Wallet"
echo "       ➖ Complete Daily Mission"
echo "       ➖ Done"
echo
echo "  8. Jadwalkan daily mission:"
echo "       bash $INSTALL_DIR/scripts/install-cron.sh"
echo
echo "Dokumentasi lengkap: $INSTALL_DIR/README.md"
