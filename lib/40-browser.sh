# lib/40-browser.sh — Chrome for Testing, ekstensi wallet, dan GUI noVNC.
# Di-source oleh install.sh dan ./agentdrop.

# ---------------------------------------------------------------------------
# Lokasi binari Chrome for Testing
# ---------------------------------------------------------------------------
browser_find_chrome() {
  local c
  for c in "$HOME/.cache/puppeteer"/chrome/*/chrome-linux64/chrome; do
    [[ -x "$c" ]] && { echo "$c"; return 0; }
  done
  [[ -n "${CHROME_CFT_PATH:-}" && -x "${CHROME_CFT_PATH}" ]] && { echo "$CHROME_CFT_PATH"; return 0; }
  command -v chrome-for-testing >/dev/null 2>&1 && { command -v chrome-for-testing; return 0; }
  return 1
}

browser_install_chrome() {
  _log "Memasang Chrome for Testing"
  command -v npx >/dev/null 2>&1 || _die "butuh npx (Node.js)"
  npx --yes @puppeteer/browsers install chrome@stable --path "$HOME/.cache/puppeteer" \
    || _die "gagal memasang Chrome for Testing"
}

# ---------------------------------------------------------------------------
# Ekstensi. Manifestnya config/extensions.yaml.
#
# KENAPA DIUNDUH, BUKAN DIBUAT SENDIRI
# ------------------------------------
# Ekstensi bikinan sendiri adalah provider non-official. Akibatnya nyata:
#   - terdeteksi sebagai klien tidak dikenal -> risiko di-ban proyek
#   - sebagian dApp memeriksa nama/ID provider dan menolak yang bukan
#     MetaMask/OKX/Phantom
#   - chain baru yang butuh wallet_addEthereumChain dengan RPC + chain ID
#     spesifik sudah ditangani wallet resmi, bukan oleh shim
# Karena itu AgentDrop memasang wallet RESMI, dan manusia yang memegang kuncinya.
# ---------------------------------------------------------------------------
_extract_crx() {  # _extract_crx <berkas> <tujuan>
  python3 - "$1" "$2" <<'PY'
import struct, sys, zipfile, io, os, json
src, dst = sys.argv[1], sys.argv[2]
raw = open(src, 'rb').read()
# CRX3 = "Cr24" + versi(4) + panjang header(4) + header + ZIP.
# unzip biasa gagal karena header itu, jadi ZIP-nya dipotong lebih dulu.
blob = raw[12 + struct.unpack('<I', raw[8:12])[0]:] if raw[:4] == b'Cr24' else raw
try:
    zf = zipfile.ZipFile(io.BytesIO(blob))
except Exception as e:
    print(f"BUKAN_ZIP: {e}"); sys.exit(1)
os.makedirs(dst, exist_ok=True)
zf.extractall(dst)
mf = os.path.join(dst, 'manifest.json')
if not os.path.exists(mf):
    print("TANPA_MANIFEST"); sys.exit(1)
m = json.load(open(mf))
print(f"OK\t{m.get('name','?')}\t{m.get('version','?')}\tMV{m.get('manifest_version','?')}")
PY
}

browser_list_extensions() {
  python3 - "$REPO_ROOT/config/extensions.yaml" "$EXT_ROOT" <<'PY'
import yaml, sys, os
m = yaml.safe_load(open(sys.argv[1])) or {}
dest = sys.argv[2]
print(f"{'NAMA':<12} {'WAJIB':<6} {'KATEGORI':<14} {'STATUS':<11} LABEL")
print('-' * 76)
for e in (m.get('extensions') or []) + (m.get('extra') or []):
    ada = 'terpasang' if os.path.exists(os.path.join(dest, e['folder'], 'manifest.json')) else 'BELUM'
    print(f"{e['name']:<12} {('ya' if e.get('required') else '-'):<6} "
          f"{e.get('category','-'):<14} {ada:<11} {e.get('label','')}")
PY
}

browser_install_extensions() {  # [--all | --only a,b]
  local mode="required" only=""
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --all) mode="all" ;;
      --only) mode="only"; only="${2:-}"; shift ;;
      *) _die "argumen tidak dikenal: $1" ;;
    esac; shift
  done
  [[ -f "$REPO_ROOT/config/extensions.yaml" ]] || _die "config/extensions.yaml tidak ada"
  command -v curl >/dev/null 2>&1 || _die "butuh curl"
  python3 -c 'import yaml' 2>/dev/null || _die "butuh PyYAML"
  mkdir -p "$EXT_ROOT"

  local jobs
  jobs="$(_MODE="$mode" _ONLY="$only" python3 - "$REPO_ROOT/config/extensions.yaml" <<'PY'
import yaml, os, sys
m = yaml.safe_load(open(sys.argv[1])) or {}
mode, only = os.environ['_MODE'], os.environ.get('_ONLY','')
want = {x.strip() for x in only.split(',') if x.strip()}
for e in (m.get('extensions') or []) + (m.get('extra') or []):
    if mode == 'required' and not e.get('required'): continue
    if mode == 'only' and e['name'] not in want: continue
    print('\t'.join([e['name'], e.get('id',''), e['folder'], e.get('source','')]))
PY
)"
  [[ -n "$jobs" ]] || { _warn "tidak ada entri yang cocok"; return 0; }

  local gagal=0 n id fo src tmp f out
  while IFS=$'\t' read -r n id fo src; do
    [[ -n "$n" ]] || continue
    _log "memasang $n"
    tmp="$(mktemp -d)"
    if [[ -n "$src" ]]; then
      curl -fsSL "$src" -o "$tmp/ext.bin" || { _warn "gagal unduh $src"; rm -rf "$tmp"; gagal=$((gagal+1)); continue; }
    else
      local url="https://clients2.google.com/service/update2/crx?response=redirect&prodversion=${CHROME_PROD_VERSION:-131.0.0.0}&acceptformat=crx2,crx3&x=id%3D${id}%26uc"
      curl -fsSL "$url" -o "$tmp/ext.crx" || { _warn "gagal unduh id=$id"; rm -rf "$tmp"; gagal=$((gagal+1)); continue; }
      # Endpoint mengembalikan XML, bukan CRX, kalau id-nya salah.
      if head -c 64 "$tmp/ext.crx" | grep -q '<?xml'; then
        _warn "endpoint mengembalikan XML — id '$id' kemungkinan salah"
        rm -rf "$tmp"; gagal=$((gagal+1)); continue
      fi
    fi
    f="$(ls "$tmp"/*.crx "$tmp"/*.bin 2>/dev/null | head -1)"
    [[ -n "$f" ]] || { _warn "tidak ada berkas terunduh untuk $n"; rm -rf "$tmp"; gagal=$((gagal+1)); continue; }
    rm -rf "$EXT_ROOT/$fo"
    if out="$(_extract_crx "$f" "$EXT_ROOT/$fo")" && [[ "$out" == OK* ]]; then
      IFS=$'\t' read -r _ nm ver mv <<< "$out"
      _ok "$n → $nm v$ver ($mv)"
      [[ "$mv" == "MV2" ]] && _warn "$n adalah MV2; Chrome sudah menghapus dukungan MV2"
    else
      _warn "ekstraksi gagal untuk $n: $out"; gagal=$((gagal+1))
    fi
    rm -rf "$tmp"
  done <<< "$jobs"

  [[ "$gagal" -gt 0 ]] && _warn "$gagal ekstensi gagal"
  echo
  _warn "Setelah terpasang, buka Chrome lewat noVNC SEKALI untuk membuat atau"
  _warn "mengimpor wallet tiap ekstensi. Agent tidak boleh melakukan itu sendiri."
  return $(( gagal > 0 ? 1 : 0 ))
}

# ---------------------------------------------------------------------------
# Nyala / mati / status
# ---------------------------------------------------------------------------
browser_ws() {
  curl -fsS "http://127.0.0.1:${CDP_PORT}/json/version" 2>/dev/null \
    | sed -n 's/.*"webSocketDebuggerUrl"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' | head -1
}

browser_start() {
  local CHROME; CHROME="$(browser_find_chrome || true)"
  [[ -n "$CHROME" ]] || { browser_install_chrome; CHROME="$(browser_find_chrome)"; }
  [[ -x "$CHROME" ]] || _die "Chrome for Testing tidak ditemukan setelah instalasi"

  # Chrome branded mengabaikan --load-extension sejak 137. Ini penyebab
  # "ekstensi tidak termuat" yang paling sering dan paling membingungkan.
  case "$(basename "$CHROME")" in
    google-chrome|google-chrome-stable)
      _die "ini Google Chrome branded — --load-extension diabaikan sejak Chrome 137. Pakai Chrome for Testing." ;;
  esac
  _ok "Chrome: $CHROME"; "$CHROME" --version 2>/dev/null | sed 's/^/   /'

  # Banyak ekstensi sekaligus, dipisah koma dalam SATU --load-extension.
  local list="" count=0 d
  if [[ -d "$EXT_ROOT" ]]; then
    for d in "$EXT_ROOT"/*/; do
      [[ -d "$d" && -f "${d}manifest.json" ]] || continue
      d="${d%/}"
      [[ -n "$list" ]] && list="$list,$d" || list="$d"
      count=$((count+1)); printf '  \033[1;32m✓\033[0m %s\n' "$(basename "$d")"
    done
  fi
  [[ "$count" -gt 0 ]] && _ok "$count ekstensi dari $EXT_ROOT" \
    || _warn "tidak ada ekstensi di $EXT_ROOT — jalankan: ./agentdrop extensions"

  command -v Xvfb >/dev/null 2>&1 || _die "butuh Xvfb. Debian/Ubuntu: apt install xvfb"
  mkdir -p "$STATE_DIR/run" "$PROFILE_DIR"
  if ! pgrep -f "Xvfb :${DISPLAY_NUM}" >/dev/null 2>&1; then
    _log "Xvfb :${DISPLAY_NUM} ${RESOLUTION}"
    Xvfb ":${DISPLAY_NUM}" -screen 0 "$RESOLUTION" -nolisten tcp >/dev/null 2>&1 &
    echo $! > "$STATE_DIR/run/xvfb.pid"; sleep 2
  fi
  export DISPLAY=":${DISPLAY_NUM}"

  # GUI WAJIB ada: login Google/Discord/X, OAuth, pembuatan wallet, dan CAPTCHA
  # semuanya dikerjakan manusia lewat layar ini. Tanpa VNC, Chrome berjalan
  # headless-secara-efektif dan operator tidak punya cara masuk — jadi ini
  # berhenti keras, bukan lanjut diam-diam. Kegagalan yang muncul nanti akan
  # terlihat seperti "login tidak bisa", jauh dari penyebabnya.
  local kurang=()
  command -v x11vnc      >/dev/null 2>&1 || kurang+=(x11vnc)
  command -v websockify  >/dev/null 2>&1 || kurang+=(websockify)
  if [[ ${#kurang[@]} -gt 0 ]]; then
    _err "GUI tidak bisa dinyalakan, kurang: ${kurang[*]}"
    _err "Debian/Ubuntu: sudo apt install x11vnc novnc"
    _die "Login manual butuh layar. Pasang dulu, lalu ulangi: agentdrop browser"
  fi

  if ! pgrep -f "x11vnc.*:${DISPLAY_NUM}" >/dev/null 2>&1; then
    _log "x11vnc :${VNC_PORT}"
    x11vnc -display ":${DISPLAY_NUM}" -rfbport "$VNC_PORT" -nopw -forever -shared >/dev/null 2>&1 &
    echo $! > "$STATE_DIR/run/x11vnc.pid"
    sleep 1
    pgrep -f "x11vnc.*:${DISPLAY_NUM}" >/dev/null 2>&1 \
      || _die "x11vnc gagal hidup di display :${DISPLAY_NUM}"
  fi
  if ! pgrep -f "websockify.*${NOVNC_PORT}" >/dev/null 2>&1; then
    _log "noVNC :${NOVNC_PORT}"
    # --web dicari, bukan dihardcode: lokasi novnc berbeda antar distro, dan
    # path yang salah membuat websockify jalan tapi halamannya 404.
    local novnc_web="" c
    for c in /usr/share/novnc /usr/share/webapps/novnc /opt/novnc; do
      [[ -d "$c" ]] && { novnc_web="$c"; break; }
    done
    if [[ -n "$novnc_web" ]]; then
      websockify --web="$novnc_web" "$NOVNC_PORT" "127.0.0.1:${VNC_PORT}" >/dev/null 2>&1 &
    else
      _warn "direktori novnc tidak ditemukan — VNC tetap jalan di port ${VNC_PORT},"
      _warn "tapi tanpa halaman web. Pakai VNC viewer ke 127.0.0.1:${VNC_PORT}."
      websockify "$NOVNC_PORT" "127.0.0.1:${VNC_PORT}" >/dev/null 2>&1 &
    fi
    echo $! > "$STATE_DIR/run/novnc.pid"
  fi

  _log "Chrome for Testing + remote debugging"
  local args=(--remote-debugging-port="${CDP_PORT}" --remote-debugging-address=127.0.0.1
              --user-data-dir="${PROFILE_DIR}" --no-sandbox --disable-dev-shm-usage
              --window-size=1920,1080 --window-position=0,0
              --no-first-run --no-default-browser-check)
  # --load-extension hanya kalau ada ekstensi valid: Chrome gagal start kalau
  # path-nya tidak ada, dan pesannya tidak menjelaskan apa-apa.
  [[ -n "$list" ]] && args+=(--load-extension="${list}")
  DISPLAY=":${DISPLAY_NUM}" "$CHROME" "${args[@]}" >/dev/null 2>&1 &
  echo $! > "$STATE_DIR/run/chrome.pid"

  local ws="" i
  for i in $(seq 1 20); do ws="$(browser_ws)"; [[ -n "$ws" ]] && break; sleep 1; done
  [[ -n "$ws" ]] || _die "Chrome tidak membuka port CDP ${CDP_PORT} dalam 20 detik"
  _ok "CDP siap: $ws"

  if [[ "$count" -gt 0 ]]; then
    local n; n="$(curl -fsS "http://127.0.0.1:${CDP_PORT}/json" 2>/dev/null | grep -c 'chrome-extension://' || echo 0)"
    if [[ "$n" -gt 0 ]]; then _ok "ekstensi terlihat lewat CDP ($n target)"
    else
      _warn "target chrome-extension:// tidak terlihat di /json."
      _warn "Bisa normal (service worker tidak selalu terdaftar di sana)."
      _warn "VERIFIKASI PASTI lewat noVNC: buka halaman, lalu di console cek"
      _warn "window.ethereum dan window.solana. Jangan farming sebelum itu hijau."
    fi
  fi
  echo
  echo "  noVNC : http://localhost:${NOVNC_PORT}/vnc.html"
  echo "  cdp   : http://127.0.0.1:${CDP_PORT}"
}

browser_status() {
  echo "=== Browser ==="
  if curl -fsS "http://127.0.0.1:${CDP_PORT}/json/version" >/dev/null 2>&1; then
    _ok "CDP hidup di ${CDP_PORT}"
    echo "   ws   : $(browser_ws)"
    echo "   tab  : $(curl -fsS "http://127.0.0.1:${CDP_PORT}/json" 2>/dev/null | grep -c '"type"' || echo 0)"
  else _warn "CDP tidak menjawab di ${CDP_PORT}"; fi
  for s in Xvfb x11vnc websockify; do
    pgrep -f "$s" >/dev/null 2>&1 && _ok "$s jalan" || _warn "$s tidak jalan"
  done
  echo "   profil   : $PROFILE_DIR"
  echo "   ekstensi : $EXT_ROOT"
}

browser_stop() {
  _log "Menghentikan browser"
  local f pid
  for f in "$STATE_DIR"/run/{chrome,novnc,x11vnc,xvfb}.pid; do
    [[ -f "$f" ]] || continue
    pid="$(cat "$f" 2>/dev/null || true)"
    [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null && { kill "$pid" 2>/dev/null && _ok "hentikan $(basename "$f" .pid)"; }
    rm -f "$f"
  done
}
