#!/usr/bin/env bash
# ============================================================================
# AgentDrop — installer
# ============================================================================
# Memasang AgentDrop ke dalam sistem sebagai framework, mengikuti pola
# installer Hermes (lihat AGENTS.md bagian "Acuan: pola installer Hermes").
#
#   ./install.sh                     pasang penuh
#   ./install.sh --skip-browser      lewati Chrome for Testing + ekstensi
#   ./install.sh --skip-extensions   pasang Chrome, jangan unduh wallet
#   ./install.sh --non-interactive   jangan tanya apa pun
#   ./install.sh --dir PATH          lokasi kode
#   ./install.sh --hermes-home PATH  lokasi data Hermes
#   ./install.sh --verify-only       jalankan pemeriksaan saja
#
# Yang TIDAK dilakukan installer: menyalakan browser, menyalakan gateway,
# memasang cron, mengumpulkan log. Itu semua tugas CLI `agentdrop` yang
# dipasang oleh skrip ini. Installer memasang; aplikasi dijalankan setelahnya.
# ============================================================================
set -euo pipefail

# ---------------------------------------------------------------------------
# GUARD — ditiru dari installer Hermes, dan keduanya beralasan.
#
# PYTHONPATH yang diwarisi dari sesi Python lain bisa membuat pip memasang dari
# checkout yang salah, sehingga instalasi baru terlihat basi atau rusak.
# Sulit didiagnosis kalau tidak diketahui, jadi dibuang di depan.
# ---------------------------------------------------------------------------
if [[ -n "${PYTHONPATH:-}" ]]; then
  echo "  ! Mengabaikan PYTHONPATH warisan agar tidak terjadi module shadowing"
  unset PYTHONPATH
fi
if [[ -n "${PYTHONHOME:-}" ]]; then
  echo "  ! Mengabaikan PYTHONHOME warisan"
  unset PYTHONHOME
fi

# Mode interaktif. Di bawah `curl | bash` stdin bukan terminal, dan `read -p`
# akan gagal dengan EOF sehingga `set -e` mematikan seluruh skrip TANPA PESAN.
# Dideteksi di depan supaya semua tahap tanya-jawab bisa menyesuaikan diri.
if [[ -t 0 ]]; then IS_INTERACTIVE=true; else IS_INTERACTIVE=false; fi

# ---------------------------------------------------------------------------
# Opsi
# ---------------------------------------------------------------------------
SKIP_BROWSER=false
SKIP_EXTENSIONS=false
NON_INTERACTIVE=false
VERIFY_ONLY=false
INSTALL_DIR_ARG=""
HERMES_HOME_ARG=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --skip-browser)     SKIP_BROWSER=true ;;
    --skip-extensions)  SKIP_EXTENSIONS=true ;;
    --non-interactive)  NON_INTERACTIVE=true ;;
    --verify-only)      VERIFY_ONLY=true ;;
    --dir)              INSTALL_DIR_ARG="${2:?butuh nilai}"; shift ;;
    --hermes-home)      HERMES_HOME_ARG="${2:?butuh nilai}"; shift ;;
    -h|--help)          sed -n '2,25p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "opsi tidak dikenal: $1" >&2; exit 1 ;;
  esac
  shift
done

[[ "$NON_INTERACTIVE" == true ]] && IS_INTERACTIVE=false

# ---------------------------------------------------------------------------
# Layout. FHS untuk root (kode di /usr/local/lib, perintah di /usr/local/bin),
# lokasi pengguna untuk non-root. Data selalu di $HOME.
# ---------------------------------------------------------------------------
if [[ -n "$INSTALL_DIR_ARG" ]]; then
  INSTALL_DIR="$INSTALL_DIR_ARG"
elif [[ "$(id -u)" -eq 0 ]]; then
  INSTALL_DIR="/usr/local/lib/agentdrop"
else
  INSTALL_DIR="$HOME/.agentdrop/app"
fi

if [[ -n "$HERMES_HOME_ARG" ]]; then export HERMES_HOME="$HERMES_HOME_ARG"; fi

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Lokasi binari ditentukan di sini, bukan di dalam tahap, karena banner()
# menampilkannya sebelum tahap apa pun berjalan.
if [[ "$(id -u)" -eq 0 ]]; then BIN_DIR="/usr/local/bin"; else BIN_DIR="$HOME/.local/bin"; fi

# shellcheck source=lib/00-common.sh
for m in "$REPO_ROOT"/lib/*.sh; do
  # shellcheck source=/dev/null
  source "$m"
done

# lib/00-common.sh menyetel HERMES_HOME_DIR dari $HERMES_HOME, jadi dibaca
# setelah opsi diproses.
HERMES_HOME_DIR="${HERMES_HOME:-$HOME/.hermes}"
STATE_DIR="$HOME/.agentdrop"

banner() {
  printf '\n\033[1;35m'
  echo "┌───────────────────────────────────────────────────────┐"
  echo "│            AgentDrop — installer                      │"
  echo "├───────────────────────────────────────────────────────┤"
  echo "│  Hermes + Chrome/CDP + wallet resmi + log audit       │"
  echo "└───────────────────────────────────────────────────────┘"
  printf '\033[0m\n'
  echo "  kode      : $INSTALL_DIR"
  echo "  perintah  : $BIN_DIR"
  echo "  data      : $STATE_DIR"
  echo "  hermes    : $HERMES_HOME_DIR"
  echo
}

# ---------------------------------------------------------------------------
# Tahap 1 — dependensi
# ---------------------------------------------------------------------------
stage_deps() { deps_install; }

# ---------------------------------------------------------------------------
# Tahap 2 — pasang kode ke sistem + CLI ke PATH
# ---------------------------------------------------------------------------
stage_install_code() {
  _log "Memasang kode ke $INSTALL_DIR"
  mkdir -p "$INSTALL_DIR"
  # Kode disalin, bukan di-symlink ke repo: repo bisa dipindah atau dihapus,
  # dan instalasi sistem tidak boleh ikut rusak.
  for item in lib tools skills config hooks agent-hooks knowledge memory AGENTS.md; do
    [[ -e "$REPO_ROOT/$item" ]] || continue
    rm -rf "${INSTALL_DIR:?}/$item"
    cp -r "$REPO_ROOT/$item" "$INSTALL_DIR/"
  done
  _ok "kode terpasang"

  _log "Memasang perintah agentdrop"
  mkdir -p "$BIN_DIR"
  install -m 755 "$REPO_ROOT/agentdrop" "$BIN_DIR/agentdrop"
  _ok "$BIN_DIR/agentdrop"

  case ":$PATH:" in
    *":$BIN_DIR:"*) ;;
    *) _warn "$BIN_DIR tidak ada di PATH. Tambahkan ke shell rc Anda:"
       _warn "    export PATH=\"$BIN_DIR:\$PATH\"" ;;
  esac
}

# ---------------------------------------------------------------------------
# Tahap 3 — kredensial
# ---------------------------------------------------------------------------
stage_credentials() {
  if [[ "$IS_INTERACTIVE" == true ]]; then
    credentials_setup
  else
    _log "Kredensial (non-interaktif)"
    mkdir -p "$HERMES_HOME_DIR"
    ENV_FILE="$HERMES_HOME_DIR/.env"
    [[ -f "$ENV_FILE" ]] || cp "$REPO_ROOT/.env.example" "$ENV_FILE"
    chmod 600 "$ENV_FILE"
    _warn "mode non-interaktif: isi $ENV_FILE secara manual"
  fi
}

# ---------------------------------------------------------------------------
# Tahap 4 — config, profil, skill, memory, knowledge, hook
# ---------------------------------------------------------------------------
stage_setup() {
  hermes_install

  _log "Knowledge base"
  # knowledge/ sudah tersalin bersama kode di tahap 2. Yang dipasang di sini
  # adalah salinan KERJA yang bisa ditulis agent, bukan salinan read-only.
  mkdir -p "$STATE_DIR/knowledge"
  cp -rn "$INSTALL_DIR/knowledge/." "$STATE_DIR/knowledge/" 2>/dev/null || true
  _ok "$STATE_DIR/knowledge (agent boleh menulis di sini)"

  _log "Struktur data"
  mkdir -p "$REPO_ROOT/data/campaigns" "$REPO_ROOT/data/screenshots" \
           "$STATE_DIR/logs" "$STATE_DIR/run" "$LOG_DIR"
  _ok "data/, ~/.agentdrop/{logs,run}"

  _log "Log aktivitas ke dalam repo"
  # Hook Hermes dipanggil sebagai perintah polos tanpa environment, jadi
  # AGENTDROP_LOG_DIR tidak pernah sampai ke proses hook. Berkas penanda ini
  # yang dibaca tools/audit_log.py dan hooks/.../handler.py sebagai fallback.
  #
  # Kenapa ke dalam repo, bukan ~/.agentdrop/logs: log harus bisa di-commit dan
  # di-push, supaya kegagalan di mesin operator bisa dibaca dari branch tanpa
  # perlu akses ke mesinnya. Log sudah diredaksi secret oleh audit_log.py.
  mkdir -p "$STATE_DIR"
  printf '%s\n' "$REPO_ROOT/data/logs" > "$STATE_DIR/logdir"
  _ok "$STATE_DIR/logdir -> $REPO_ROOT/data/logs (masuk git)"
}

# ---------------------------------------------------------------------------
# Tahap 5 — browser
# ---------------------------------------------------------------------------
stage_browser() {
  [[ "$SKIP_BROWSER" == true ]] && { _warn "browser dilewati (--skip-browser)"; return 0; }

  _log "Browser"
  local CHROME; CHROME="$(browser_find_chrome || true)"
  if [[ -n "$CHROME" ]]; then
    _ok "Chrome for Testing sudah ada: $CHROME"
  else
    _warn "Chrome for Testing belum ada. Memasang..."
    browser_install_chrome || _warn "gagal memasang — jalankan nanti: agentdrop browser"
  fi

  [[ "$SKIP_EXTENSIONS" == true ]] && { _warn "ekstensi dilewati (--skip-extensions)"; return 0; }
  echo
  _log "Ekstensi wallet"
  echo "  AgentDrop memasang wallet RESMI (MetaMask, OKX, Phantom), bukan"
  echo "  ekstensi bikinan sendiri. Ekstensi non-official terdeteksi sebagai"
  echo "  klien asing, berisiko di-ban proyek, dan ditolak sebagian dApp."
  echo
  echo "  Yang akan diunduh adalah kode pihak ketiga ke dalam browser yang"
  echo "  akan memegang dana Anda. Cocokkan ID di config/extensions.yaml"
  echo "  dengan halaman Chrome Web Store resmi proyeknya sebelum lanjut."
  if [[ "$IS_INTERACTIVE" == true ]]; then
    local j
    read -r -p "  Unduh sekarang? [y/N]: " j
    case "$j" in
      y|Y) browser_install_extensions || _warn "sebagian ekstensi gagal" ;;
      *)   _warn "dilewati — jalankan nanti: agentdrop extensions" ;;
    esac
  else
    _warn "mode non-interaktif: jalankan nanti: agentdrop extensions"
  fi
}

# ---------------------------------------------------------------------------
# Tahap 6 — verifikasi
# ---------------------------------------------------------------------------
# Sebagai tahap akhir instalasi, kegagalan verifikasi TIDAK boleh membatalkan
# instal: kode sudah terpasang dan pengguna tetap butuh pesan penutup.
# Tapi lewat --verify-only, exit code adalah seluruh gunanya — jadi di jalur
# itu kegagalan harus diteruskan, bukan ditelan.
stage_verify() {
  _log "Verifikasi"
  if verify_run; then return 0; fi
  VERIFY_FAILED=1
  return 0
}

# ---------------------------------------------------------------------------
banner
if [[ "$VERIFY_ONLY" == true ]]; then
  stage_verify
  exit "${VERIFY_FAILED:-0}"
fi

# URUTAN INI SENGAJA, DAN ALASANNYA NYATA.
#
# Profil, skill, config, hook, dan memory semuanya murni salin-berkas dari repo:
# tidak butuh jaringan, tidak butuh Hermes, tidak butuh venv. Sedangkan
# stage_deps mengunduh installer Hermes dan memasang PyYAML lewat pip — dua
# langkah yang paling sering gagal (jaringan, proxy, PEP 668, disk penuh).
#
# Ketika stage_deps berjalan LEBIH DULU, tiap kegagalannya memanggil _die yang
# exit 1, jadi stage_setup tidak pernah tercapai. Hasilnya: pengguna melihat
# "install gagal" dan ~/.hermes/profiles/ KOSONG — tidak ada satu pun profil atau
# skill yang terbuat. Persis keluhan yang masuk: "tidak ada profiles agent yang
# dibuat, skill juga tidak di-create".
#
# Karena itu pekerjaan yang pasti berhasil didahulukan. Kalau Hermes gagal
# terpasang, profil dan skill tetap ada di disk, dan menjalankan ulang
# ./install.sh sesudah jaringan pulih akan menyambung dari situ — bukan mengulang
# dari nol.
stage_install_code
stage_credentials
stage_setup
stage_deps
stage_browser
stage_verify

if [[ "${VERIFY_FAILED:-0}" == "1" ]]; then
  printf '\033[1;33m\nPemasangan selesai, tapi pemeriksaan TIDAK lolos.\033[0m\n'
  printf 'Perbaiki yang bertanda ✗ di atas sebelum menjalankan agent.\n'
  printf 'Jalankan ulang kapan saja dengan: ./install.sh --verify-only\n\n'
fi

cat <<'EOF'

============================================================
  Pemasangan selesai
============================================================

  Selanjutnya, berurutan:

    1. agentdrop status        pastikan semuanya hijau
    2. agentdrop browser       nyalakan Chrome for Testing
       -> buat/impor wallet, login Google/Discord/X di jendelanya
          (mesin tanpa layar: lewat noVNC http://localhost:6080/vnc.html)
       -> di console pastikan window.ethereum ADA sebelum lanjut
    3. agentdrop burn-in       uji stabilisasi browser SEBELUM agent dipercaya
    4. agentdrop start         nyalakan gateway Telegram

  Langkah 3 bukan formalitas. Tanpanya kegagalan pertama baru terlihat saat
  agent sedang mengerjakan campaign sungguhan, dan gejalanya akan terlihat
  seperti kesalahan proyek — bukan seperti browser yang belum stabil.

  Perintah lain:

    agentdrop extensions       pasang/perbarui wallet
    agentdrop logs             kumpulkan log untuk dianalisis
    agentdrop audit doctor     diagnosis kalau ada yang rusak
    agentdrop cron             pasang jadwal otomatis
    agentdrop --help           semua perintah

  Dokumentasi: AGENTS.md (konteks build) dan docs/prosedur-uji.md
EOF
