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

# Cetak tautan Chrome Web Store untuk tiap wallet.
#
# Ini jalur pemasangan yang DIPILIH, bukan jalur CRX. Alasannya ada di
# stage_browser (install.sh): ekstensi dari Web Store terdaftar sungguhan di
# profil, ikut diperbarui Chrome, dan versinya yang ditinjau Google.
#
# Memakai _pyu, bukan python3 polos: PyYAML ada di venv proyek, dan python3
# sistem sering tidak punya (PEP 668 memblokir pip system).
browser_print_store_links() {
  "$(_pyu)" - "$REPO_ROOT/config/extensions.yaml" "$EXT_ROOT" <<'PY'
import yaml, sys, os
cfg, dest = sys.argv[1], sys.argv[2]
try:
    m = yaml.safe_load(open(cfg)) or {}
except FileNotFoundError:
    print("  ! " + cfg + " tidak ada")
    sys.exit(1)
items = (m.get('extensions') or []) + (m.get('extra') or [])
print("  %-12s %-6s %-11s %s" % ("WALLET", "WAJIB", "STATUS", "TAUTAN"))
print("  " + "-" * 74)
for e in items:
    url = e.get('store') or (
        "https://chromewebstore.google.com/detail/" + e['id'] if e.get('id') else "-")
    ada = 'terpasang' if os.path.exists(
        os.path.join(dest, e.get('folder', ''), 'manifest.json')) else 'BELUM'
    wajib = 'ya' if e.get('required') else '-'
    print("  %-12s %-6s %-11s %s" % (e['name'], wajib, ada, url))
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

browser_install_extensions() {  # [--sideload] [--all | --only a,b]
  # TANPA --sideload, perintah ini hanya MENCETAK tautan Chrome Web Store.
  #
  # Itu jalur yang dipilih. Memasang dari Web Store membuat ekstensi terdaftar
  # sungguhan di profil (bukan sementara seperti --load-extension, yang sejak
  # Chrome 126 membuat service worker mati dan popup tidak bisa dibuka), ikut
  # diperbarui Chrome, dan versinya yang ditinjau Google.
  #
  # --sideload menghidupkan jalur lama: unduh CRX lalu ekstrak sendiri. Masih
  # ada untuk mesin tanpa akses ke Web Store, tapi bukan default.
  local mode="required" only="" sideload=false
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --sideload) sideload=true ;;
      --all) mode="all" ;;
      --only) mode="only"; only="${2:-}"; shift ;;
      *) _die "argumen tidak dikenal: $1" ;;
    esac; shift
  done

  if [[ "$sideload" == false ]]; then
    _log "Ekstensi wallet — pasang dari Chrome Web Store"
    browser_print_store_links
    echo
    _warn "Buka tiap tautan di jendela Chrome for Testing, lalu tekan 'Add to Chrome'."
    _warn "Sesudah terpasang, buat atau impor wallet-nya di sana."
    _warn "Jalur lama (unduh CRX otomatis): agentdrop extensions --sideload"
    return 0
  fi
  _warn "Mode --sideload: mengunduh CRX pihak ketiga dan mengekstraknya sendiri."
  _warn "Ekstensi semacam ini TIDAK terdaftar di profil dan tidak diperbarui Chrome."
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

# ---------------------------------------------------------------------------
# Deteksi layar ASLI mesin.
#
# Chrome for Testing adalah aplikasi desktop penuh: punya ikon sendiri (logo
# Chrome dengan tulisan "Test" di kotak hitam) dan jendela sendiri. Kalau mesin
# sudah punya layar, memaksanya lewat VNC hanya menambah lapisan yang justru
# merusak — popup ekstensi wallet sering tidak bisa dibuka, clipboard tidak
# sinkron, dan koordinat klik meleset.
#
# DISPLAY yang di-set belum tentu hidup: SSH tanpa -X, systemd unit, dan
# container semuanya bisa mewariskan DISPLAY yang tidak menunjuk ke mana pun.
# Jadi kalau xdpyinfo ada, DISPLAY diverifikasi dulu sebelum dipercaya.
# ---------------------------------------------------------------------------
browser_real_display() {
  [[ -n "${BROWSER_DISPLAY:-}" ]] && { echo "$BROWSER_DISPLAY"; return 0; }
  [[ -z "${DISPLAY:-}" ]] && return 1
  if command -v xdpyinfo >/dev/null 2>&1; then
    xdpyinfo -display "$DISPLAY" >/dev/null 2>&1 && { echo "$DISPLAY"; return 0; }
    return 1
  fi
  # Tanpa xdpyinfo, DISPLAY tidak boleh dipercaya buta. SSH tanpa -X, systemd
  # unit, dan container semuanya mewariskan DISPLAY yang tidak menunjuk ke mana
  # pun; kalau itu dipakai, Chrome gagal start dan yang muncul hanya "CDP tidak
  # menjawab dalam 20 detik" — jauh dari penyebabnya.
  #
  # X lokal bisa dipastikan dari socketnya: :N berarti /tmp/.X11-unix/XN.
  case "$DISPLAY" in
    :[0-9]*)
      local n="${DISPLAY#:}"; n="${n%%.*}"
      [[ -S "/tmp/.X11-unix/X${n}" ]] && { echo "$DISPLAY"; return 0; }
      return 1 ;;
    *)
      # DISPLAY jarak jauh (host:0) tidak bisa dipastikan dari socket lokal.
      # Dipakai apa adanya: kalau salah, Chrome gagal cepat dan CDP tidak naik.
      echo "$DISPLAY"; return 0 ;;
  esac
}

browser_start() {
  local a
  for a in "$@"; do
    case "$a" in
      --native) BROWSER_MODE=native ;;
      --vnc)    BROWSER_MODE=vnc ;;
    esac
  done

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

  mkdir -p "$STATE_DIR/run" "$PROFILE_DIR"

  # -------------------------------------------------------------------------
  # PILIH LAYAR. Chrome for Testing adalah aplikasi desktop biasa — punya ikon
  # sendiri dan jendela sendiri. Kalau mesin sudah punya layar, pakai layar itu
  # langsung; Xvfb + noVNC hanya untuk mesin tanpa layar (VPS, container).
  #
  # noVNC bukan sekadar "kurang nyaman". Popup ekstensi wallet sering tidak
  # bisa dibuka di dalamnya, clipboard tidak sinkron, dan koordinat klik bisa
  # meleset. Untuk login manual dan persetujuan transaksi itu fatal, bukan
  # kosmetik. Karena itu layar asli didahulukan, bukan dijadikan pengecualian.
  # -------------------------------------------------------------------------
  local mode="${BROWSER_MODE:-auto}" layar_asli="" pakai_vnc=false CHROME_DISPLAY
  layar_asli="$(browser_real_display || true)"
  case "$mode" in
    native) pakai_vnc=false ;;
    vnc)    pakai_vnc=true ;;
    auto)   [[ -n "$layar_asli" ]] && pakai_vnc=false || pakai_vnc=true ;;
    *)      _die "BROWSER_MODE tidak dikenal: '$mode' — pakai auto|native|vnc" ;;
  esac
  if [[ "$pakai_vnc" == false && -z "$layar_asli" ]]; then
    _err "Tidak ada layar yang bisa dipakai, padahal BROWSER_MODE=$mode."
    _die "Set BROWSER_MODE=vnc untuk lewat noVNC, atau jalankan di mesin berlayar."
  fi

  if [[ "$pakai_vnc" == false ]]; then
    CHROME_DISPLAY="$layar_asli"
    _ok "Layar asli mesin dipakai: $CHROME_DISPLAY"
    _ok "Chrome for Testing akan muncul sebagai jendela biasa — popup ekstensi bisa dibuka"
  else
    command -v Xvfb >/dev/null 2>&1 || _die "butuh Xvfb. Debian/Ubuntu: apt install xvfb"
    if ! pgrep -f "Xvfb :${DISPLAY_NUM}" >/dev/null 2>&1; then
      _log "Xvfb :${DISPLAY_NUM} ${RESOLUTION}"
      Xvfb ":${DISPLAY_NUM}" -screen 0 "$RESOLUTION" -nolisten tcp >/dev/null 2>&1 &
      echo $! > "$STATE_DIR/run/xvfb.pid"; sleep 2
    fi
    CHROME_DISPLAY=":${DISPLAY_NUM}"

    # GUI WAJIB ada di jalur ini: login Google/Discord/X, OAuth, pembuatan
    # wallet, dan CAPTCHA semuanya dikerjakan manusia lewat layar ini. Tanpa
    # VNC, Chrome berjalan headless-secara-efektif dan operator tidak punya
    # cara masuk — jadi berhenti keras, bukan lanjut diam-diam.
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
  fi

  _log "Chrome for Testing + remote debugging"
  # --enable-unsafe-extension-debugging BUKAN opsional sejak Chrome 126.
  #
  # Tanpa flag ini, Chrome memperlakukan ekstensi dari --load-extension sebagai
  # sementara: halamannya bisa dibuka, TAPI ekstensi tidak ditulis ke Secure
  # Preferences profil, service worker tidak pernah jalan, content script tidak
  # disuntikkan, dan popup-nya tidak bisa dibuka. Semuanya gagal tanpa pesan
  # error apa pun. MetaMask/OKX/Phantom persis kena ini — ketiganya MV3 dengan
  # service worker.
  #
  # Ini sebabnya keluhan "ekstensi terunduh tapi tidak bisa dibuka" tidak pernah
  # sembuh dengan berpindah layar: penyebabnya bukan VNC, melainkan flag ini
  # tidak ada.
  #
  # Aman di sini karena CDP diikat ke 127.0.0.1 saja (lihat
  # --remote-debugging-address di atas), jadi permukaan serangnya lokal.
  local args=(--remote-debugging-port="${CDP_PORT}" --remote-debugging-address=127.0.0.1
              --user-data-dir="${PROFILE_DIR}" --no-sandbox --disable-dev-shm-usage
              --window-size=1920,1080 --window-position=0,0
              --no-first-run --no-default-browser-check
              --enable-unsafe-extension-debugging)
  # --load-extension hanya kalau ada ekstensi valid: Chrome gagal start kalau
  # path-nya tidak ada, dan pesannya tidak menjelaskan apa-apa.
  [[ -n "$list" ]] && args+=(--load-extension="${list}")

  # -------------------------------------------------------------------------
  # MATIKAN CHROME LAMA DULU. Ini bukan kebersihan, ini syarat.
  #
  # Chrome memakai ProcessSingleton pada --user-data-dir. Kalau sudah ada
  # instance dengan profil yang sama, peluncuran kedua hanya memberi sinyal ke
  # proses lama lalu KELUAR SENDIRI — tanpa jendela baru dan tanpa pesan error.
  # Port CDP tetap dijawab oleh proses LAMA, jadi `browser_ws` melihat "CDP
  # siap" dan kita percaya Chrome baru sudah jalan padahal tidak.
  #
  # Akibatnya nyata: operator menjalankan ulang `agentdrop browser` sesudah
  # perbaikan flag, tapi yang menjawab tetap Chrome lama yang tidak punya flag
  # itu. websocket UUID-nya identik antar-run — itu tanda diagnostiknya.
  # -------------------------------------------------------------------------
  local ws_lama=""
  ws_lama="$(browser_ws || true)"
  if [[ -n "$ws_lama" ]]; then
    _warn "Chrome lama masih memegang port CDP ${CDP_PORT} — menghentikannya dulu"
    _warn "(tanpa ini, peluncuran baru keluar sendiri dan flag baru tidak terpakai)"
    browser_stop
    # browser_stop hanya membunuh PID yang tercatut. Chrome yang dimulai di luar
    # agentdrop, atau yang PID-nya hilang, tetap hidup dan tetap memegang profil.
    pkill -f -- "--user-data-dir=${PROFILE_DIR}" >/dev/null 2>&1 || true
    # Yang ditunggu adalah PROSESNYA mati, bukan portnya berhenti menjawab.
    # Menunggu port itu salah dua kali: port bisa tetap dijawab sebentar oleh
    # socket yang belum dilepas, dan yang lebih penting — kalau ada proses lain
    # yang kebetulan memegang port itu, kita akan menunggu selamanya padahal
    # Chrome lama sudah benar-benar berhenti. Uji dengan Chrome tiruan
    # menunjukkan kegagalan ini: prosesnya mati, tapi kodenya tetap _die.
    local k sisa=""
    for k in $(seq 1 20); do
      sisa="$(pgrep -f -- "--user-data-dir=${PROFILE_DIR}" 2>/dev/null | tr '\n' ' ' || true)"
      [[ -z "${sisa// /}" ]] && break
      sleep 1
    done
    if [[ -n "${sisa// /}" ]]; then
      _err "Chrome lama masih hidup: pid ${sisa}"
      _die "Hentikan manual: pkill -f 'user-data-dir=${PROFILE_DIR}', lalu ulangi."
    fi
    _ok "Chrome lama berhenti"
  fi
  # SingletonLock yang tertinggal (Chrome crash / mesin mati paksa) membuat
  # peluncuran baru gagal dengan "Failed to create a ProcessSingleton".
  rm -f "${PROFILE_DIR}/SingletonLock" "${PROFILE_DIR}/SingletonCookie" \
        "${PROFILE_DIR}/SingletonSocket" 2>/dev/null || true

  DISPLAY="$CHROME_DISPLAY" "$CHROME" "${args[@]}" >/dev/null 2>&1 &
  local chrome_pid=$!
  echo "$chrome_pid" > "$STATE_DIR/run/chrome.pid"

  # Proses yang keluar sendiri adalah gejala ProcessSingleton, dan kalau tidak
  # diperiksa yang terlihat hanyalah "CDP siap" dari Chrome lama.
  sleep 1
  if ! kill -0 "$chrome_pid" 2>/dev/null; then
    _err "Chrome keluar segera setelah dinyalakan (pid $chrome_pid)."
    _die "Kemungkinan besar masih ada instance lain dengan profil ${PROFILE_DIR}.\n       Jalankan: agentdrop browser-stop, lalu ulangi."
  fi

  local ws="" i
  for i in $(seq 1 20); do ws="$(browser_ws || true)"; [[ -n "$ws" ]] && break; sleep 1; done
  [[ -n "$ws" ]] || _die "Chrome tidak membuka port CDP ${CDP_PORT} dalam 20 detik"

  # Bukti bahwa yang menjawab adalah Chrome BARU, bukan sisa yang lama.
  if [[ -n "$ws_lama" && "$ws" == "$ws_lama" ]]; then
    _err "websocket CDP tidak berubah — yang menjawab masih Chrome lama."
    _die "Hentikan manual: pkill -f 'user-data-dir=${PROFILE_DIR}', lalu ulangi."
  fi
  _ok "CDP siap: $ws"

  if [[ "$count" -gt 0 ]]; then
    # `grep -c` mencetak 0 DAN keluar dengan status 1 saat tidak ada kecocokan.
    # Jadi `|| echo 0` di sini mencetak nol KEDUA dan n menjadi "0\n0", yang
    # membuat [[ -gt ]] gagal dengan "syntax error in expression". `|| true`
    # menahan statusnya untuk set -e tanpa menambah keluaran.
    local n; n="$(curl -fsS "http://127.0.0.1:${CDP_PORT}/json" 2>/dev/null | grep -c 'chrome-extension://' || true)"
    n="${n:-0}"
    if [[ "$n" -gt 0 ]]; then _ok "ekstensi terlihat lewat CDP ($n target)"
    else
      _warn "target chrome-extension:// tidak terlihat di /json."
      _warn "Ini belum tentu cacat: service worker MV3 memang sering tidak"
      _warn "terdaftar di /json walau ekstensinya sehat. Jadi /json bukan bukti."
      _warn "BUKTI sebenarnya cuma satu — di jendela browser, buka halaman lalu"
      _warn "di console cek window.ethereum dan window.solana."
      _warn "Kalau keduanya undefined, popup tidak akan bisa dibuka."
    fi
  fi
  echo
  if [[ "$pakai_vnc" == true ]]; then
    echo "  noVNC : http://localhost:${NOVNC_PORT}/vnc.html"
    echo "  (paksa jendela asli di mesin berlayar: BROWSER_MODE=native agentdrop browser)"
  else
    echo "  jendela : Chrome for Testing muncul di layar $CHROME_DISPLAY"
    echo "  (paksa lewat noVNC: BROWSER_MODE=vnc agentdrop browser)"
  fi
  echo "  cdp   : http://127.0.0.1:${CDP_PORT}"
}

browser_status() {
  echo "=== Browser ==="
  if curl -fsS "http://127.0.0.1:${CDP_PORT}/json/version" >/dev/null 2>&1; then
    _ok "CDP hidup di ${CDP_PORT}"
    echo "   ws   : $(browser_ws)"
    # Cacat yang sama seperti di atas: tanpa ini barisnya tercetak "0\n0".
    local tab; tab="$(curl -fsS "http://127.0.0.1:${CDP_PORT}/json" 2>/dev/null | grep -c '"type"' || true)"
    echo "   tab  : ${tab:-0}"
  else _warn "CDP tidak menjawab di ${CDP_PORT}"; fi
  # Xvfb/VNC hanya relevan di jalur tanpa layar. Melaporkannya sebagai "tidak
  # jalan" di desktop biasa membuat operator mengira ada yang rusak.
  if [[ -n "$(browser_real_display || true)" ]]; then
    _ok "layar asli dipakai (${DISPLAY}) — Xvfb/VNC tidak diperlukan"
  else
    for s in Xvfb x11vnc websockify; do
      pgrep -f "$s" >/dev/null 2>&1 && _ok "$s jalan" || _warn "$s tidak jalan"
    done
  fi
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
