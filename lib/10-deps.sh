# lib/10-deps.sh — ketergantungan sistem. Di-source oleh install.sh.

deps_install() {
  _log "Memeriksa ketergantungan"

  command -v python3 >/dev/null 2>&1 || _die "butuh python3"
  command -v curl    >/dev/null 2>&1 || _die "butuh curl"
  _ok "python3, curl"

  # Node dibutuhkan karena Hermes menjalankan browser lewat `npx agent-browser`.
  if command -v node >/dev/null 2>&1; then
    _ok "node $(node --version)"
  else
    _warn "node tidak ada — Hermes menjalankan browser lewat npx agent-browser."
    _warn "Pasang Node.js 18+ sebelum menjalankan browser."
  fi

  # GUI browser butuh X server + VNC supaya manusia bisa login manual.
  for b in Xvfb x11vnc websockify; do
    if ! command -v "$b" >/dev/null 2>&1; then
      _warn "$b tidak ada — browser akan jalan tanpa GUI yang bisa dilihat,"
      _warn "sehingga login Google/Discord/X tidak bisa dilakukan manual."
      _warn "Debian/Ubuntu: sudo apt install xvfb x11vnc novnc"
    fi
  done

  # Hermes sendiri. Dipasang di sini, bukan disuruh pasang manual: installer ini
  # index-nya (K8), jadi "satu perintah" harus benar-benar satu perintah.
  # Kalau sudah ada di mesin, DILEWATI — tidak ditimpa, tidak di-upgrade.
  if command -v hermes >/dev/null 2>&1; then
    _ok "hermes sudah ada: $(hermes --version 2>/dev/null | head -1) — dilewati"
  else
    _log "Memasang Hermes (installer resmi NousResearch)"
    _warn "Ini mengunduh dan menjalankan skrip dari hermes-agent.nousresearch.com."
    if [[ "${IS_INTERACTIVE:-false}" == true ]]; then
      local j
      read -r -p "  Lanjutkan? [Y/n]: " j
      case "$j" in
        n|N) _die "Hermes tidak dipasang. Pasang manual lalu ulangi:
  curl -fsSL https://hermes-agent.nousresearch.com/install.sh | bash" ;;
      esac
    fi
    # Installer Hermes sendiri membaca stdin untuk tanya-jawab. Di bawah
    # `curl | bash` stdin bukan TTY, jadi ia harus diberi /dev/null supaya
    # tidak EOF dan mematikan seluruh rantai dengan set -e.
    if curl -fsSL https://hermes-agent.nousresearch.com/install.sh -o /tmp/agentdrop-hermes-install.sh; then
      bash /tmp/agentdrop-hermes-install.sh < /dev/null || _die "installer Hermes gagal"
      rm -f /tmp/agentdrop-hermes-install.sh
    else
      _die "gagal mengunduh installer Hermes. Periksa jaringan, atau pasang manual:
  curl -fsSL https://hermes-agent.nousresearch.com/install.sh | bash"
    fi
    # Installer menaruh binari di ~/.local/bin atau ~/.hermes/bin, yang mungkin
    # belum ada di PATH proses ini.
    export PATH="$HOME/.local/bin:$HOME/.hermes/bin:$PATH"
    command -v hermes >/dev/null 2>&1 \
      && _ok "hermes terpasang: $(hermes --version 2>/dev/null | head -1)" \
      || _die "hermes terpasang tapi tidak ditemukan di PATH. Buka shell baru, atau:
  export PATH=\"$HOME/.local/bin:$PATH\""
  fi

  # PyYAML + eth-account di venv tersendiri (PEP 668 memblokir pip system).
  if [[ ! -x "$STATE_DIR/venv/bin/python" ]]; then
    _log "Membuat venv $STATE_DIR/venv"
    python3 -m venv "$STATE_DIR/venv" || _die "gagal membuat venv"
  fi
  "$STATE_DIR/venv/bin/pip" install -q --upgrade PyYAML eth-account \
    || _die "gagal memasang PyYAML / eth-account"
  _ok "venv: PyYAML + eth-account"
}
