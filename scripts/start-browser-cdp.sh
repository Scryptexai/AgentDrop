#!/usr/bin/env bash
# ============================================================================
# start-browser-cdp.sh — Chrome for Testing + ekstensi wallet + noVNC
# ============================================================================
# KENAPA BUKAN CAMOUFOX, DAN BUKAN PULA CHROME BIASA
# --------------------------------------------------
# 1. Kebutuhannya adalah EKSTENSI WALLET SUNGGUHAN, bukan provider bikinan.
#    Airdrop farming menyentuh banyak chain baru yang harus didaftarkan dengan
#    RPC + chain ID spesifik (wallet_addEthereumChain). Wallet asli menangani
#    itu; provider bikinan harus mengimplementasikan ulang semuanya.
#
# 2. Hermes mendukung attach ke browser yang sudah jalan:
#      tools/browser_tool.py:2431-2435
#          if cdp_override and not force_local:
#              session_info = _create_cdp_session(task_id, cdp_override)
#    dan baris 2909:
#          backend_args = ["--cdp", session_info["cdp_url"]]
#    Komentarnya tegas: "The rest of the command (--json, command, args) is
#    identical." Artinya SEMUA tool native (browser_navigate, browser_snapshot,
#    browser_click, ...) tetap jalan — hanya transportnya yang berubah.
#
# 3. HARUS Chrome for Testing, BUKAN Google Chrome branded. Mulai Chrome 137
#    build branded menghapus --load-extension:
#      "--load-extension is not allowed in Google Chrome, ignoring."
#    Pengumuman resmi tim Chrome: perubahan ini HANYA untuk build branded;
#    Chromium dan Chrome For Testing tetap mendukungnya.
#
# 4. JANGAN pakai --session bersama --cdp. agent-browser >=0.13 akan membuat
#    browser lokal sendiri dan MENGABAIKAN --cdp tanpa error.
#
# Pemakaian:
#   ./scripts/start-browser-cdp.sh                # jalankan
#   ./scripts/start-browser-cdp.sh --status       # cek status
#   ./scripts/start-browser-cdp.sh --stop         # hentikan
# ============================================================================
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

DISPLAY_NUM="${CDP_DISPLAY:-99}"
RESOLUTION="${CDP_RESOLUTION:-1920x1080x24}"
CDP_PORT="${CDP_PORT:-9222}"
NOVNC_PORT="${NOVNC_PORT:-6080}"
VNC_PORT="${VNC_PORT:-5900}"
PROFILE_DIR="${CDP_PROFILE_DIR:-$HOME/.agentdrop/chrome-profile}"
EXT_DIR="${CDP_EXT_DIR:-$REPO_ROOT/extensions/wallet}"
STATE_DIR="$HOME/.agentdrop"
PID_DIR="$STATE_DIR/run"

die()  { printf '\033[1;31m  ✗ %s\033[0m\n' "$*" >&2; exit 1; }
warn() { printf '\033[1;33m  ! %s\033[0m\n' "$*"; }
ok()   { printf '\033[1;32m  ✓ %s\033[0m\n' "$*"; }
log()  { printf '\033[1;34m==> %s\033[0m\n' "$*"; }

mkdir -p "$STATE_DIR" "$PID_DIR" "$PROFILE_DIR"

# ----------------------------------------------------------------------------
# Lokasi binari Chrome for Testing
# ----------------------------------------------------------------------------
find_chrome() {
  local c
  # 1. Yang dipasang @puppeteer/browsers ke cache-nya
  for c in "$HOME/.cache/puppeteer"/chrome/*/chrome-linux64/chrome \
           "$HOME/.cache/puppeteer"/chrome/*/chrome-linux64/chrome; do
    [[ -x "$c" ]] && { echo "$c"; return 0; }
  done
  # 2. Override eksplisit
  if [[ -n "${CHROME_CFT_PATH:-}" && -x "${CHROME_CFT_PATH}" ]]; then
    echo "${CHROME_CFT_PATH}"; return 0
  fi
  # 3. chrome-for-testing di PATH
  if command -v chrome-for-testing >/dev/null 2>&1; then
    command -v chrome-for-testing; return 0
  fi
  return 1
}

install_chrome() {
  log "Chrome for Testing belum ada — memasang lewat @puppeteer/browsers"
  command -v npx >/dev/null 2>&1 || die "butuh npx (Node.js). Pasang Node dulu."
  # @puppeteer/browsers memasang ke ~/.cache/puppeteer/chrome/<versi>/chrome-linux64/
  npx --yes @puppeteer/browsers install chrome@stable --path "$HOME/.cache/puppeteer" \
    || die "gagal memasang Chrome for Testing"
}

# ----------------------------------------------------------------------------
# Peringatan kalau yang ketemu justru Google Chrome branded
# ----------------------------------------------------------------------------
reject_branded_chrome() {
  local bin="$1"
  case "$(basename "$bin")" in
    google-chrome|google-chrome-stable|chrome)
      # 'chrome' bisa CfT, jadi periksa string versi
      if "$bin" --version 2>/dev/null | grep -qi "google"; then
        warn "Binari ini terdeteksi sebagai Google Chrome branded: $bin"
        warn "Chrome 137+ MENGABAIKAN --load-extension di build branded."
        warn "Ekstensi wallet tidak akan termuat. Pakai Chrome for Testing."
      fi
      ;;
  esac
}

# ----------------------------------------------------------------------------
# CDP endpoint -> websocket URL
# ----------------------------------------------------------------------------
resolve_ws() {
  # Hermes melakukan resolusi ini sendiri lewat /json/version, tapi kita
  # memverifikasinya di sini supaya kegagalan terlihat sekarang, bukan nanti
  # saat agent mencoba bernavigasi.
  curl -fsS "http://127.0.0.1:${CDP_PORT}/json/version" 2>/dev/null \
    | sed -n 's/.*"webSocketDebuggerUrl"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' | head -1
}

cmd_status() {
  echo "=== Status browser CDP ==="
  if curl -fsS "http://127.0.0.1:${CDP_PORT}/json/version" >/dev/null 2>&1; then
    ok "CDP hidup di port ${CDP_PORT}"
    local ws; ws="$(resolve_ws)"
    echo "   webSocketDebuggerUrl: ${ws:-<tidak terbaca>}"
    echo "   tabs terbuka: $(curl -fsS "http://127.0.0.1:${CDP_PORT}/json" 2>/dev/null | grep -c '"type"' || echo 0)"
  else
    warn "CDP tidak menjawab di port ${CDP_PORT}"
  fi
  for svc in Xvfb x11vnc websockify; do
    if pgrep -x "$svc" >/dev/null 2>&1 || pgrep -f "$svc" >/dev/null 2>&1; then
      ok "$svc jalan"
    else
      warn "$svc tidak jalan"
    fi
  done
  echo "   profil    : $PROFILE_DIR"
  echo "   ekstensi  : $EXT_DIR"
  echo
  echo "Set di config.yaml:  browser.cdp_url: \"http://127.0.0.1:${CDP_PORT}\""
}

cmd_stop() {
  log "Menghentikan browser CDP"
  for f in "$PID_DIR"/chrome.pid "$PID_DIR"/novnc.pid "$PID_DIR"/x11vnc.pid "$PID_DIR"/xvfb.pid; do
    [[ -f "$f" ]] || continue
    local pid; pid="$(cat "$f" 2>/dev/null || true)"
    if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; then
      kill "$pid" 2>/dev/null && ok "hentikan $(basename "$f" .pid) (pid $pid)"
    fi
    rm -f "$f"
  done
  ok "selesai"
}

cmd_start() {
  # ---------------------------------------------------------------- binari
  local CHROME
  CHROME="$(find_chrome || true)"
  [[ -n "$CHROME" ]] || { install_chrome; CHROME="$(find_chrome)"; }
  [[ -x "$CHROME" ]] || die "Chrome for Testing tidak ditemukan setelah instalasi."
  reject_branded_chrome "$CHROME"
  ok "Chrome: $CHROME"
  "$CHROME" --version 2>/dev/null | sed 's/^/   /' || true

  # ------------------------------------------------------------- ekstensi
  if [[ -d "$EXT_DIR" && -f "$EXT_DIR/manifest.json" ]]; then
    ok "ekstensi wallet: $EXT_DIR"
  else
    warn "ekstensi wallet tidak ditemukan di $EXT_DIR"
    warn "Chrome tetap jalan, TAPI tanpa wallet. Pasang ekstensi lalu ulangi."
    warn "Set CDP_EXT_DIR=/path/ke/ekstensi-ter-ekstrak (harus berisi manifest.json)."
  fi

  # ---------------------------------------------------------------- Xvfb
  command -v Xvfb >/dev/null 2>&1 || die "butuh Xvfb. Debian/Ubuntu: apt install xvfb"
  if ! pgrep -f "Xvfb :${DISPLAY_NUM}" >/dev/null 2>&1; then
    log "menyalakan Xvfb :${DISPLAY_NUM} ${RESOLUTION}"
    Xvfb ":${DISPLAY_NUM}" -screen 0 "$RESOLUTION" -nolisten tcp >/dev/null 2>&1 &
    echo $! > "$PID_DIR/xvfb.pid"
    sleep 2
  fi
  export DISPLAY=":${DISPLAY_NUM}"
  ok "DISPLAY=$DISPLAY"

  # ------------------------------------------------- GUI: x11vnc + noVNC
  # Chrome di dalam container harus BISA DILIHAT manusia untuk login Google,
  # OAuth, dan CAPTCHA. Tanpa ini agent akan mentok dan tidak ada yang bisa
  # mengambil alih.
  if command -v x11vnc >/dev/null 2>&1; then
    if ! pgrep -f "x11vnc.*:${DISPLAY_NUM}" >/dev/null 2>&1; then
      log "menyalakan x11vnc di port ${VNC_PORT}"
      x11vnc -display ":${DISPLAY_NUM}" -rfbport "$VNC_PORT" -nopw -forever -shared \
        >/dev/null 2>&1 &
      echo $! > "$PID_DIR/x11vnc.pid"
    fi
    if command -v websockify >/dev/null 2>&1; then
      if ! pgrep -f "websockify.*${NOVNC_PORT}" >/dev/null 2>&1; then
        log "menyalakan noVNC di port ${NOVNC_PORT}"
        websockify --web=/usr/share/novnc "$NOVNC_PORT" "127.0.0.1:${VNC_PORT}" \
          >/dev/null 2>&1 &
        echo $! > "$PID_DIR/novnc.pid"
      fi
      ok "noVNC: http://localhost:${NOVNC_PORT}/vnc.html"
    else
      warn "websockify tidak ada — noVNC tidak dinyalakan (VNC tetap di ${VNC_PORT})"
    fi
  else
    warn "x11vnc tidak ada — browser jalan TANPA GUI yang bisa dilihat."
    warn "Login manual tidak akan bisa dilakukan. Pasang: apt install x11vnc novnc"
  fi

  # ------------------------------------------------------------- Chrome
  log "menyalakan Chrome for Testing dengan remote debugging"
  local args=(
    --remote-debugging-port="${CDP_PORT}"
    --remote-debugging-address=127.0.0.1
    --user-data-dir="${PROFILE_DIR}"
    --no-sandbox
    --disable-dev-shm-usage
    --window-size=1920,1080
    --window-position=0,0
    --no-first-run
    --no-default-browser-check
  )
  # --load-extension HANYA kalau ekstensinya ada. Chrome menolak start kalau
  # path-nya tidak valid, dan pesannya tidak jelas.
  if [[ -f "$EXT_DIR/manifest.json" ]]; then
    args+=(--load-extension="${EXT_DIR}")
  fi

  DISPLAY=":${DISPLAY_NUM}" "$CHROME" "${args[@]}" >/dev/null 2>&1 &
  echo $! > "$PID_DIR/chrome.pid"

  # ------------------------------------------------------------ verifikasi
  local ws="" i
  for i in $(seq 1 20); do
    ws="$(resolve_ws)"
    [[ -n "$ws" ]] && break
    sleep 1
  done
  [[ -n "$ws" ]] || die "Chrome tidak membuka port CDP ${CDP_PORT} dalam 20 detik."
  ok "CDP siap: $ws"

  # Buktikan ekstensi benar-benar termuat. Ini yang paling sering gagal
  # diam-diam: Chrome jalan normal, CDP jalan normal, tapi ekstensinya nol.
  if [[ -f "$EXT_DIR/manifest.json" ]]; then
    local n
    n="$(curl -fsS "http://127.0.0.1:${CDP_PORT}/json" 2>/dev/null | grep -c 'chrome-extension://' || echo 0)"
    if [[ "$n" -gt 0 ]]; then
      ok "ekstensi terdeteksi lewat CDP ($n target chrome-extension://)"
    else
      warn "target chrome-extension:// tidak terlihat di /json."
      warn "Itu bisa normal (service worker tidak selalu terdaftar di /json),"
      warn "jadi verifikasi pasti lewat halaman: buka https://example.com lalu"
      warn "cek window.ethereum dari console. Jangan lanjut farming sebelum ini hijau."
    fi
  fi

  cat <<EOF

Selesai. Selanjutnya:

  1. Set di SETIAP config/hermes/profiles/*/config.yaml:
         browser:
           cdp_url: "http://127.0.0.1:${CDP_PORT}"
     dan HAPUS blok browser.camofox — Camofox dan CDP saling eksklusif
     (hermes-agent/tools/browser_cdp_tool.py:466).

  2. JANGAN set BROWSER_CDP_URL ke websocket mentah kalau Anda juga memakai
     --session; agent-browser >=0.13 mengabaikan --cdp secara diam-diam.

  3. Login visual sekali per platform lewat noVNC:
         http://localhost:${NOVNC_PORT}/vnc.html

  4. Uji: ./scripts/burn-in.sh
EOF
}

case "${1:-start}" in
  start)   cmd_start ;;
  --status|status) cmd_status ;;
  --stop|stop)     cmd_stop ;;
  -h|--help)       sed -n '2,40p' "$0" | sed 's/^# \{0,1\}//' ;;
  *)               die "argumen tidak dikenal: $1 (start|status|stop)" ;;
esac
