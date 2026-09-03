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

  # GUI browser. Mesin berlayar memakai layarnya langsung, jadi Xvfb/VNC hanya
  # dibutuhkan di mesin tanpa layar (VPS, container). Memperingatkan ketiganya
  # di desktop biasa hanya membuat operator mengira ada yang rusak.
  if [[ -n "$(browser_real_display || true)" ]]; then
    _ok "layar asli terdeteksi (${DISPLAY}) — Chrome for Testing akan muncul sebagai jendela biasa"
  else
    for b in Xvfb x11vnc websockify; do
      if ! command -v "$b" >/dev/null 2>&1; then
        _warn "$b tidak ada — tanpa layar asli, browser butuh ini untuk GUI,"
        _warn "sehingga login Google/Discord/X tidak bisa dilakukan manual."
        _warn "Debian/Ubuntu: sudo apt install xvfb x11vnc novnc"
      fi
    done
  fi

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
  #
  # venv bisa SETENGAH JADI. `python3 -m venv` membuat direktori dan bin/python
  # lebih dulu, baru kemudian menjalankan ensurepip; kalau paket python3-venv
  # belum terpasang (khas Debian/Ubuntu) langkah itu gagal dan bin/pip tidak
  # pernah ada. Pemeriksaan lama hanya melihat bin/python, jadi venv rusak itu
  # dianggap siap, pembuatan ulang dilewati, dan baris install mati dengan
  # "venv/bin/pip: No such file or directory" tanpa penjelasan apa pun.
  local _venv="$STATE_DIR/venv" _vpy="$STATE_DIR/venv/bin/python"

  if [[ ! -x "$_vpy" ]] || ! "$_vpy" -c 'import pip' >/dev/null 2>&1; then
    if [[ -e "$_venv" ]]; then
      _warn "venv $_venv tidak lengkap (python ada, pip tidak) — dibuat ulang"
      rm -rf "$_venv"
    fi
    _log "Membuat venv $_venv"
    python3 -m venv "$_venv" || _die "gagal membuat venv $_venv.
  Di Debian/Ubuntu ini hampir selalu karena paket python3-venv belum terpasang:
      sudo apt install python3-venv
  lalu jalankan ulang ./install.sh"

    # venv bisa jadi tapi pip-nya tidak ada kalau ensurepip dilewati.
    if ! "$_vpy" -c 'import pip' >/dev/null 2>&1; then
      _log "Menyiapkan pip di dalam venv"
      "$_vpy" -m ensurepip --upgrade >/dev/null 2>&1 || _die \
        "venv $_venv dibuat tapi pip tidak tersedia dan ensurepip gagal.
  Pasang python3-venv lalu jalankan ulang:
      sudo apt install python3-venv"
    fi
  fi

  # Lewat `python -m pip`, bukan bin/pip: skrip bin/pip bisa hilang sementara
  # modul pip-nya ada, dan itu persis yang membuat install ini mati sebelumnya.
  "$_vpy" -m pip install -q --upgrade PyYAML eth-account \
    || _die "gagal memasang PyYAML / eth-account"
  _ok "venv: PyYAML + eth-account"
}
