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

  # Hermes sendiri.
  if command -v hermes >/dev/null 2>&1; then
    _ok "hermes $(hermes --version 2>/dev/null | head -1)"
  else
    _die "hermes tidak ada. Pasang lebih dulu: lihat README bagian prasyarat."
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
