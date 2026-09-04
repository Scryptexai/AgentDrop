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
  # _extract_crx sudah dihapus. Ekstensi dipasang dari Chrome Web Store di
  # dalam GUI browser; tidak ada CRX yang diunduh dan diekstrak sendiri.
browser_print_store_links() {
  "$(_pyu)" - "$REPO_ROOT/config/extensions.yaml" "$EXT_ROOT" <<'PY'
import sys, os
try:
    import yaml
except ImportError:
    print("  ! PyYAML tidak tersedia di interpreter ini.")
    print("  ! Jalankan ./install.sh -- ia menyiapkan venv dengan PyYAML.")
    sys.exit(3)
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
  "$(_pyu)" - "$REPO_ROOT/config/extensions.yaml" "$EXT_ROOT" <<'PY'
import sys, os
try:
    import yaml
except ImportError:
    print("  ! PyYAML tidak tersedia. Jalankan ./install.sh untuk menyiapkan venv.")
    sys.exit(3)
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

browser_install_extensions() {  # cetak tautan Chrome Web Store saja
  # Perintah ini hanya MENCETAK tautan Chrome Web Store. Tidak ada unduhan.
  #
  # Ekstensi dipasang di dalam GUI browser lewat Web Store, bukan diunduh lewat
  # terminal lalu diekstrak. Alasannya bukan selera:
  #   - ekstensi Web Store TERDAFTAR di profil, ikut diperbarui Chrome, dan
  #     versinya yang ditinjau Google;
  #   - CRX yang diekstrak manual harus dimuat lewat --load-extension, dan sejak
  #     Chrome 126 ekstensi semacam itu service worker-nya mati, content script
  #     tidak disuntikkan, dan popup-nya tidak bisa dibuka -- semuanya gagal
  #     tanpa pesan error.
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --all|--only)
        _die "opsi $1 sudah dihapus. Ekstensi dipasang dari Chrome Web Store
di dalam GUI browser, bukan diunduh lewat terminal." ;;
      --sideload)
        _die "--sideload sudah dihapus. Mengunduh CRX lalu mengekstraknya sendiri
menghasilkan ekstensi yang tidak terdaftar di profil, tidak diperbarui Chrome,
dan service worker-nya mati sejak Chrome 126. Pasang dari Chrome Web Store:
buka tautan di bawah di jendela Chrome, tekan Add to Chrome." ;;
      *) _die "argumen tidak dikenal: $1" ;;
    esac; shift
  done

  _log "Ekstensi wallet — pasang dari Chrome Web Store"
  # Tanpa pemeriksaan ini, kegagalan mencetak daftar (PyYAML hilang, misalnya)
  # hanya memunculkan traceback lalu perintah lanjut mencetak petunjuk seolah
  # semuanya baik-baik saja -- persis yang terjadi sebelum diperbaiki.
  if ! browser_print_store_links; then
    _die "gagal membaca config/extensions.yaml. Perbaiki dulu penyebabnya di atas."
  fi
  echo
  _warn "Buka tiap tautan di jendela Chrome for Testing, lalu tekan Add to Chrome."
  _warn "Sesudah terpasang, buat atau impor wallet-nya DI DALAM BROWSER itu."
  _warn "Tidak ada yang diunduh lewat terminal — semuanya lewat Web Store."
  return 0
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

# ---------------------------------------------------------------------------
# Pemeriksaan sebelum worker dijalankan.
#
# Celah yang nyata terjadi: operator menjalankan `agentdrop test-workers` dan
# `agentdrop run` TANPA lebih dulu menjalankan `agentdrop browser`. Task-nya
# berbunyi "buka https://..." tapi tidak ada Chrome yang memegang port CDP, jadi
# browser_navigate gagal -- dan yang terlihat hanyalah worker yang "lambat" atau
# "tidak mengerjakan apa-apa". Tidak ada satu pun pesan yang menunjuk penyebabnya.
#
# Karena itu diperiksa di sini, sebelum hermes dipanggil. Sengaja PERINGATAN
# bukan _die: koordinator tidak punya tool browser sama sekali, dan task
# tertentu (riset murni) memang tidak menyentuh halaman.
# ---------------------------------------------------------------------------
browser_preflight() {
  local ws=""
  ws="$(browser_ws || true)"
  if [[ -n "$ws" ]]; then
    _ok "Chrome for Testing hidup, CDP :${CDP_PORT} siap"
    return 0
  fi
  _warn "Chrome for Testing TIDAK hidup — CDP :${CDP_PORT} tidak menjawab."
  _warn "Task yang menyentuh halaman web akan gagal. Nyalakan dulu:"
  _warn "    agentdrop browser"
  _warn "(kalau jendela tidak muncul di mesin berlayar: BROWSER_MODE=native agentdrop browser)"
  return 0
}

# Jalankan proses latar dengan keluaran ke berkas log, bukan /dev/null.
# websockify dan x11vnc yang gagal dulu lenyap tanpa jejak karena stderr-nya
# dibuang, jadi yang terlihat operator hanya URL yang tidak bisa dibuka.
_log_dir_bg() { echo "${AGENTDROP_LOG_DIR:-$STATE_DIR/log}"; }

# Apakah ada yang menjawab di port TCP loopback. Dipakai menggantikan
# `pgrep -f "websockify.*6080"`, yang mencocokkan SUBSTRING di baris perintah
# proses apa pun: shell yang sedang men-grep, editor yang membuka berkas ini,
# atau `agentdrop browser` itu sendiri bisa membuat pgrep "berhasil" sehingga
# websockify tidak pernah dinyalakan sama sekali. Yang kita butuhkan bukan
# nama prosesnya, tapi apakah portnya menjawab.
_port_tcp_siap() {  # _port_tcp_siap <port>
  (exec 3<>"/dev/tcp/127.0.0.1/$1") 2>/dev/null
}

# noVNC dianggap hidup HANYA kalau halamannya benar-benar menjawab.
# "Prosesnya ada" bukan bukti: websockify bisa hidup sebentar lalu mati karena
# port dipakai, modul python kurang, atau --web menunjuk direktori kosong.
novnc_siap() {  # novnc_siap <detik-tunggu>
  local tunggu="${1:-8}" k
  for k in $(seq 1 "$tunggu"); do
    curl -fsS "http://127.0.0.1:${NOVNC_PORT}/vnc.html" >/dev/null 2>&1 && return 0
    curl -fsS "http://127.0.0.1:${NOVNC_PORT}/"        >/dev/null 2>&1 && return 0
    sleep 1
  done
  return 1
}

# Perbaiki URL noVNC yang benar-benar bisa dibuka. Di VPS, "localhost" di
# laptop operator BUKAN mesin ini — itu penyebab paling umum "URL tidak bisa
# dibuka" walau noVNC-nya sehat.
novnc_petunjuk_url() {
  local ip
  ip="$(hostname -I 2>/dev/null | awk '{print $1}')"
  echo "  noVNC  : http://localhost:${NOVNC_PORT}/vnc.html"
  echo "           (jalan kalau Anda di mesin ini, atau lewat terowongan SSH)"
  if [[ -n "${SSH_CONNECTION:-}" || -n "${SSH_TTY:-}" ]]; then
    echo
    echo "  Anda tersambung lewat SSH. 'localhost' di laptop Anda bukan mesin ini."
    echo "  Buka terowongan dari laptop Anda, baru buka URL di atas:"
    echo "    ssh -L ${NOVNC_PORT}:localhost:${NOVNC_PORT} $(whoami 2>/dev/null)@$(hostname -f 2>/dev/null || hostname)"
  elif [[ -n "$ip" ]]; then
    echo
    echo "  Dari mesin lain di jaringan yang sama: http://${ip}:${NOVNC_PORT}/vnc.html"
    echo "  ! noVNC ini TANPA kata sandi. Jangan buka port ${NOVNC_PORT} ke internet."
  fi
}

# ---------------------------------------------------------------------------
# DEPENDENSI PER JALUR.
#
# Dua jalur ini butuh paket yang BERBEDA, jadi pemeriksaannya juga harus
# terpisah. Kesalahan lama: satu daftar dependensi untuk keduanya, dipasang
# (atau tidak dipasang) tanpa memandang jalur mana yang dipilih operator.
#
# Aturan di sini: PERIKSA DULU, baru pasang. Yang sudah ada dilewati, supaya
# `agentdrop browser` yang dijalankan ulang tidak memasang apa pun.
# ---------------------------------------------------------------------------

_paket_manager() {
  if command -v apt-get >/dev/null 2>&1; then echo apt
  elif command -v dnf >/dev/null 2>&1; then echo dnf
  elif command -v pacman >/dev/null 2>&1; then echo pacman
  else echo ""
  fi
}

# Prefix untuk memasang sebagai root. Kosong kalau sudah root.
_prefix_root() {
  [[ "$(id -u)" -eq 0 ]] && { echo ""; return 0; }
  command -v sudo >/dev/null 2>&1 && { echo "sudo"; return 0; }
  echo "TIDAKADA"
}

# Pasang binari yang belum ada. Argumen: <label> <binari=paket>...
# Mengembalikan 0 kalau sesudahnya semua binari benar-benar ada.
_pasang_binari() {
  local label="$1"; shift
  local kurang=() paket=() entri b p
  for entri in "$@"; do
    b="${entri%%=*}"; p="${entri#*=}"
    command -v "$b" >/dev/null 2>&1 || { kurang+=("$b"); paket+=("$p"); }
  done
  if [[ ${#kurang[@]} -eq 0 ]]; then
    _ok "$label: semua dependensi sudah terpasang — pemasangan dilewati"
    return 0
  fi
  _log "$label: kurang ${kurang[*]} — memasang"

  local pm pre
  pm="$(_paket_manager)"; pre="$(_prefix_root)"
  if [[ -z "$pm" ]]; then
    _err "Tidak menemukan apt-get/dnf/pacman. Pasang manual: ${paket[*]}"
    return 1
  fi
  if [[ "$pre" == "TIDAKADA" ]]; then
    _err "Butuh hak root untuk memasang ${kurang[*]}, tapi sudo tidak ada."
    _err "Jalankan sebagai root, atau pasang manual: ${paket[*]}"
    return 1
  fi

  case "$pm" in
    apt)
      export DEBIAN_FRONTEND=noninteractive
      $pre apt-get update -qq >/dev/null 2>&1 || true
      $pre apt-get install -y -qq "${paket[@]}" || {
        _err "apt-get gagal memasang ${paket[*]}"
        return 1; } ;;
    dnf)    $pre dnf install -y "${paket[@]}" || { _err "dnf gagal"; return 1; } ;;
    pacman) $pre pacman -S --noconfirm "${paket[@]}" || { _err "pacman gagal"; return 1; } ;;
  esac

  # Dipasang bukan berarti ada. Diperiksa ulang, bukan dipercaya.
  local masih=()
  for b in "${kurang[@]}"; do
    command -v "$b" >/dev/null 2>&1 || masih+=("$b")
  done
  if [[ ${#masih[@]} -gt 0 ]]; then
    _err "sesudah pemasangan, masih tidak ada: ${masih[*]}"
    _err "Nama paketnya mungkin berbeda di distro Anda. Pasang manual lalu ulangi."
    return 1
  fi
  _ok "$label: ${kurang[*]} terpasang"
  return 0
}

# Pustaka bersama tidak punya binari; diperiksa lewat ldconfig.
_pasang_lib() {
  local label="$1"; shift
  command -v ldconfig >/dev/null 2>&1 || { _warn "ldconfig tidak ada — pemeriksaan pustaka dilewati"; return 0; }
  local kurang=() paket=() entri soname p
  for entri in "$@"; do
    soname="${entri%%=*}"; p="${entri#*=}"
    ldconfig -p 2>/dev/null | grep -q "$soname" || { kurang+=("$soname"); paket+=("$p"); }
  done
  if [[ ${#kurang[@]} -eq 0 ]]; then
    _ok "$label: pustaka tampilan sudah lengkap — pemasangan dilewati"
    return 0
  fi
  _log "$label: pustaka kurang (${#kurang[@]}) — memasang ${paket[*]}"
  local pm pre
  pm="$(_paket_manager)"; pre="$(_prefix_root)"
  [[ "$pre" == "TIDAKADA" ]] && { _err "butuh root untuk memasang pustaka"; return 1; }
  [[ -z "$pm" ]] && { _err "tidak ada pengelola paket; pasang manual: ${paket[*]}"; return 1; }
  case "$pm" in
    apt)
      export DEBIAN_FRONTEND=noninteractive
      $pre apt-get install -y -qq "${paket[@]}" >/dev/null || { _err "gagal memasang pustaka"; return 1; } ;;
    *)  _warn "pemasangan pustaka otomatis hanya diuji di Debian/Ubuntu."
        $pre "$pm" install -y "${paket[@]}" >/dev/null 2>&1 || {
          _err "pasang manual: ${paket[*]}"; return 1; } ;;
  esac

  # Pengelola paket yang keluar 0 TIDAK berarti pustakanya ada: nama paket bisa
  # salah di distro ini, atau arsitekturnya tidak cocok. Diperiksa ulang lewat
  # ldconfig, sama seperti _pasang_binari memeriksa ulang binarinya.
  ldconfig 2>/dev/null || true
  local masih=() s
  for s in "${kurang[@]}"; do
    ldconfig -p 2>/dev/null | grep -q "$s" || masih+=("$s")
  done
  if [[ ${#masih[@]} -gt 0 ]]; then
    _err "sesudah pemasangan, pustaka ini tetap tidak ada: ${masih[*]}"
    _err "Nama paketnya mungkin berbeda di distro Anda. Pasang manual lalu ulangi."
    return 1
  fi
  _ok "$label: pustaka tampilan terpasang"
  return 0
}

# Jalur Chrome for Testing: jendela asli di layar mesin.
browser_deps_chrome() {
  _log "Periksa dependensi jalur CHROME FOR TESTING (jendela asli)"
  # Pustaka yang dibutuhkan Chrome di Debian/Ubuntu. Tanpanya Chrome keluar
  # seketika dengan "error while loading shared libraries" dan yang terlihat
  # hanya "CDP tidak menjawab dalam 20 detik".
  _pasang_lib "chrome" \
    "libnss3.so=libnss3" "libnspr4.so=libnspr4" "libatk-1.0.so.0=libatk1.0-0" \
    "libatk-bridge-2.0.so.0=libatk-bridge2.0-0" "libcups.so.2=libcups2" \
    "libdrm.so.2=libdrm2" "libxkbcommon.so.0=libxkbcommon0" \
    "libXcomposite.so.1=libxcomposite1" "libXdamage.so.1=libxdamage1" \
    "libXfixes.so.3=libxfixes3" "libXrandr.so.2=libxrandr2" "libgbm.so.1=libgbm1" \
    "libpango-1.0.so.0=libpango-1.0-0" "libcairo.so.2=libcairo2" \
    "libasound.so.2=libasound2" "libatspi.so.0=libatspi2.0-0" \
    "libxshmfence.so.1=libxshmfence1"
}

# Jalur noVNC: Xvfb + x11vnc + websockify. Tidak menyentuh pustaka Chrome.
browser_deps_vnc() {
  _log "Periksa dependensi jalur noVNC (VPS / tanpa layar)"
  _pasang_binari "novnc" \
    "Xvfb=xvfb" "x11vnc=x11vnc" "websockify=novnc" || return 1
  # Chrome tetap dibutuhkan di jalur ini: yang ditampilkan noVNC adalah Chrome
  # yang berjalan di dalam Xvfb.
  _pasang_lib "chrome" \
    "libnss3.so=libnss3" "libnspr4.so=libnspr4" "libatk-1.0.so.0=libatk1.0-0" \
    "libatk-bridge-2.0.so.0=libatk-bridge2.0-0" "libcups.so.2=libcups2" \
    "libdrm.so.2=libdrm2" "libxkbcommon.so.0=libxkbcommon0" \
    "libXcomposite.so.1=libxcomposite1" "libXdamage.so.1=libxdamage1" \
    "libXfixes.so.3=libxfixes3" "libXrandr.so.2=libxrandr2" "libgbm.so.1=libgbm1" \
    "libpango-1.0.so.0=libpango-1.0-0" "libcairo.so.2=libcairo2" \
    "libasound.so.2=libasound2" "libatspi.so.0=libatspi2.0-0" \
    "libxshmfence.so.1=libxshmfence1" \
    || { _err "pustaka Chrome belum lengkap; noVNC akan menampilkan Chrome yang mati.";
         return 1; }
  # Halaman web noVNC. Tanpa ini websockify jalan tapi tidak ada yang bisa
  # dibuka di browser -- persis gejala "url belum bisa dibuka".
  if [[ ! -d /usr/share/novnc && ! -d /usr/share/webapps/novnc && ! -d /opt/novnc ]]; then
    _warn "halaman web noVNC tidak ditemukan walau paket novnc terpasang."
    _warn "VNC tetap bisa dipakai dengan VNC viewer, tapi tidak lewat browser."
  fi
}

# Tanya operator. Hanya kalau ada terminal; skrip dan cron tidak punya.
#
# SEMUA tampilan ditulis ke stderr, dan HANYA jawabannya ke stdout. Fungsi ini
# dipanggil lewat `mode="$(browser_tanya_mode ...)"`; kalau menu ikut ke stdout,
# seluruh menu tertangkap ke dalam variabel dan operator tidak melihat apa pun.
# Diuji: dengan stdout bersama, hasilnya kosong dan menu hilang.
browser_tanya_mode() {  # -> stdout: native|vnc
  local layar_asli="$1" saran=1 jawab=""
  [[ -z "$layar_asli" ]] && saran=2
  {
    echo
    echo "  PILIH MODE BROWSER"
    echo "    1) Chrome for Testing -- jendela asli di layar mesin ini"
    echo "    2) noVNC              -- dibuka lewat browser (untuk VPS / tanpa layar)"
    echo
    if [[ "$saran" == 1 ]]; then
      echo "  Layar asli terdeteksi (${DISPLAY:-}), jadi 1 disarankan."
    else
      echo "  Tidak ada layar asli, jadi 2 disarankan."
    fi
    printf '  Pilihan [1/2, Enter = %s]: ' "$saran"
  } >&2
  IFS= read -r jawab || jawab=""
  jawab="${jawab:-$saran}"
  case "$jawab" in
    1|native|chrome) echo native ;;
    2|vnc|novnc)     echo vnc ;;
    *) # _warn menulis ke STDOUT (lib/00-common.sh:22), jadi di dalam substitusi
       # perintah pesannya akan ikut tertangkap ke variabel mode. Ditulis ke
       # stderr langsung di sini.
       printf '\033[1;33m  !\033[0m jawaban %s tidak dikenal -- pakai saran (%s)\n' \
         "'$jawab'" "$saran" >&2
       if [[ "$saran" == 1 ]]; then echo native; else echo vnc; fi ;;
  esac
}

browser_start() {
  # Tutup sesi SSH mengirim SIGHUP ke seluruh grup proses. Tanpa baris ini,
  # Xvfb, x11vnc, websockify, dan Chrome ikut mati tepat saat operator menutup
  # terminalnya — browser "hilang sendiri". Diuji: dengan `&` polos anak mati;
  # dengan trap ini anak hidup dan `$!` tetap memberi PID yang benar.
  trap '' HUP

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

  # Ekstensi dipasang dari Chrome Web Store di dalam GUI browser, bukan
  # diunduh lewat terminal. Yang terpasang masuk ke profil Chrome dan dimuat
  # otomatis, jadi tidak ada yang perlu dipindai atau diteruskan di sini.
  if [[ ! -f "$PROFILE_DIR/Default/Secure Preferences" ]]; then
    _warn "Profil Chrome belum punya ekstensi. Buka Chrome dulu lalu pasang dari"
    _warn "Chrome Web Store:  agentdrop extensions"
  fi

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
    auto)
      # Auto dulu MEMILIH DIAM-DIAM: begitu ada layar, jalur noVNC tidak pernah
      # dijalankan sama sekali dan operator tidak tahu itu terjadi -- gejalanya
      # "noVNC belum di-fix" padahal tidak pernah dicoba. Sekarang operator
      # ditanya, dan pilihannya menentukan dependensi mana yang diperiksa.
      if [[ -t 0 && -t 1 && -z "${AGENTDROP_BROWSER_MODE:-}" ]]; then
        mode="$(browser_tanya_mode "$layar_asli")"
      else
        [[ -n "$layar_asli" ]] && mode=native || mode=vnc
        echo "  mode  : $mode (dipilih otomatis; jalankan agentdrop browser di"
        echo "          terminal untuk ditanya, atau set BROWSER_MODE=native|vnc)"
      fi
      [[ "$mode" == native ]] && pakai_vnc=false || pakai_vnc=true ;;
    *)      _die "BROWSER_MODE tidak dikenal: '$mode' -- pakai auto|native|vnc" ;;
  esac

  # Dependensi DIPERIKSA DAN DIPASANG per jalur, sesudah mode dipastikan.
  # Diperiksa dulu: yang sudah ada dilewati, jadi menjalankan ulang tidak
  # memasang apa pun.
  if [[ "$pakai_vnc" == true ]]; then
    browser_deps_vnc       || _die "dependensi noVNC belum lengkap -- perbaiki pesan di atas, lalu ulangi."
  else
    browser_deps_chrome       || _die "dependensi Chrome belum lengkap -- perbaiki pesan di atas, lalu ulangi."
  fi
  if [[ "$pakai_vnc" == false && -z "$layar_asli" ]]; then
    _err "Tidak ada layar yang bisa dipakai, padahal BROWSER_MODE=$mode."
    _die "Set BROWSER_MODE=vnc untuk lewat noVNC, atau jalankan di mesin berlayar."
  fi

  # Semua proses latar menulis ke berkas log, bukan /dev/null: kegagalan yang
  # tidak bisa dibaca ulang adalah kegagalan yang akan dilaporkan operator
  # sebagai "tidak jalan" tanpa petunjuk apa pun.
  local logbg; logbg="$(_log_dir_bg)"; mkdir -p "$logbg"
  # noVNC boleh diklaim hidup hanya sesudah halamannya benar-benar menjawab.
  local novnc_hidup=false

  if [[ "$pakai_vnc" == false ]]; then
    CHROME_DISPLAY="$layar_asli"
    _ok "Layar asli mesin dipakai: $CHROME_DISPLAY"
    _ok "Chrome for Testing akan muncul sebagai jendela biasa — popup ekstensi bisa dibuka"
  else
    command -v Xvfb >/dev/null 2>&1 || _die "butuh Xvfb. Debian/Ubuntu: apt install xvfb"
    # Yang diperiksa soket X-nya, bukan nama prosesnya -- sama seperti yang
    # dipakai browser_real_display(), jadi keduanya tidak bisa berbeda pendapat.
    if [[ ! -S "/tmp/.X11-unix/X${DISPLAY_NUM}" ]]; then
      _log "Xvfb :${DISPLAY_NUM} ${RESOLUTION}"
      Xvfb ":${DISPLAY_NUM}" -screen 0 "$RESOLUTION" -nolisten tcp \
        </dev/null >>"$logbg/xvfb.log" 2>&1 &
      echo $! > "$STATE_DIR/run/xvfb.pid"
      local k
      for k in $(seq 1 20); do
        [[ -S "/tmp/.X11-unix/X${DISPLAY_NUM}" ]] && break
        sleep 0.5
      done
      [[ -S "/tmp/.X11-unix/X${DISPLAY_NUM}" ]] \
        || _die "Xvfb gagal hidup di :${DISPLAY_NUM} — lihat $logbg/xvfb.log"
      _ok "Xvfb siap di :${DISPLAY_NUM}"
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

    if ! _port_tcp_siap "$VNC_PORT"; then
      _log "x11vnc :${VNC_PORT}"
      x11vnc -display ":${DISPLAY_NUM}" -rfbport "$VNC_PORT" -nopw -forever -shared \
        </dev/null >>"$logbg/x11vnc.log" 2>&1 &
      echo $! > "$STATE_DIR/run/x11vnc.pid"
      local k
      for k in $(seq 1 10); do
        _port_tcp_siap "$VNC_PORT" && break
        sleep 1
      done
      _port_tcp_siap "$VNC_PORT" \
        || _die "x11vnc gagal membuka port ${VNC_PORT} di display :${DISPLAY_NUM} — lihat $logbg/x11vnc.log"
      _ok "x11vnc siap di :${VNC_PORT}"
    fi

    # `novnc_siap 1`, bukan pgrep: yang menentukan "sudah jalan" adalah apakah
    # halamannya menjawab, bukan apakah ada proses yang namanya kebetulan cocok.
    if novnc_siap 1; then
      novnc_hidup=true
      _ok "noVNC sudah berjalan di port ${NOVNC_PORT}"
    else
      _log "noVNC :${NOVNC_PORT}"
      # --web dicari, bukan dihardcode: lokasi novnc berbeda antar distro, dan
      # path yang salah membuat websockify jalan tapi halamannya 404.
      local novnc_web="" c
      for c in /usr/share/novnc /usr/share/webapps/novnc /opt/novnc; do
        [[ -d "$c" ]] && { novnc_web="$c"; break; }
      done
      # Direktori ada tapi isinya kosong sama buruknya dengan tidak ada: halaman
      # akan 404 dan operator melihat "URL tidak bisa dibuka".
      if [[ -n "$novnc_web" && ! -f "$novnc_web/vnc.html" && ! -f "$novnc_web/index.html" ]]; then
        _warn "$novnc_web ada tapi tidak punya vnc.html/index.html — dianggap tidak ada"
        novnc_web=""
      fi

      # Sebagian distro tidak memasang binari `websockify`, hanya modul python.
      local ws_cmd=()
      if command -v websockify >/dev/null 2>&1; then
        ws_cmd=(websockify)
      elif python3 -c 'import websockify' >/dev/null 2>&1; then
        ws_cmd=(python3 -m websockify)
      else
        _err "websockify tidak ada, baik sebagai binari maupun modul python."
        _err "Debian/Ubuntu: sudo apt install novnc   (atau: pip install websockify)"
        _die "Tanpa websockify tidak ada halaman noVNC."
      fi

      if [[ -n "$novnc_web" ]]; then
        "${ws_cmd[@]}" --web="$novnc_web" "$NOVNC_PORT" "127.0.0.1:${VNC_PORT}" \
          </dev/null >>"$logbg/novnc.log" 2>&1 &
      else
        _warn "direktori novnc tidak ditemukan — VNC tetap jalan di port ${VNC_PORT},"
        _warn "tapi tanpa halaman web. Pakai VNC viewer ke 127.0.0.1:${VNC_PORT}."
        "${ws_cmd[@]}" "$NOVNC_PORT" "127.0.0.1:${VNC_PORT}" \
          </dev/null >>"$logbg/novnc.log" 2>&1 &
      fi
      echo $! > "$STATE_DIR/run/novnc.pid"

      # INI YANG DULU TIDAK ADA. URL dicetak tanpa diperiksa, jadi websockify
      # yang mati seketika tetap menghasilkan "noVNC : http://localhost:6080"
      # yang tidak bisa dibuka. Sekarang diverifikasi dulu.
      if novnc_siap 8; then
        novnc_hidup=true
        _ok "noVNC menjawab di port ${NOVNC_PORT}"
      else
        _err "websockify tidak menjawab di port ${NOVNC_PORT}."
        _err "Keluaran terakhirnya:"
        tail -5 "$logbg/novnc.log" 2>/dev/null | sed 's/^/     /'
        _warn "Penyebab paling sering: port ${NOVNC_PORT} sudah dipakai proses lain,"
        _warn "atau paket novnc belum terpasang. Coba: sudo apt install novnc"
        _warn "VNC polos tetap bisa dipakai dengan VNC viewer ke 127.0.0.1:${VNC_PORT}."
      fi
    fi
  fi

  _log "Chrome for Testing + remote debugging"
  # Ekstensi TIDAK dimuat lewat --load-extension. Yang dipasang dari Chrome Web
  # Store sudah terdaftar di profil, jadi Chrome memuatnya sendiri; flag itu
  # hanya untuk CRX yang diekstrak manual, dan sejak Chrome 126 ekstensi yang
  # dimuat seperti itu service worker-nya mati dan popup-nya tidak bisa dibuka.
  # Lihat docs/ untuk riwayat lengkapnya.
  local args=(--remote-debugging-port="${CDP_PORT}" --remote-debugging-address=127.0.0.1
              --user-data-dir="${PROFILE_DIR}" --no-sandbox --disable-dev-shm-usage
              --window-size=1920,1080 --window-position=0,0
              --no-first-run --no-default-browser-check)

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

  DISPLAY="$CHROME_DISPLAY" "$CHROME" "${args[@]}" </dev/null >>"$logbg/chrome.log" 2>&1 &
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

  # Pemeriksaan ini sekarang SELALU jalan. Dulu ia dijaga `if [[ "$count" -gt 0 ]]`
  # karena hanya relevan kalau ada ekstensi yang dimuat lewat --load-extension.
  # Jalur itu sudah dibuang (ekstensi dipasang dari Chrome Web Store ke dalam
  # profil), dan penjaganya tertinggal tanpa `count` yang mendefinisikannya —
  # di bawah `set -uo pipefail` itu mematikan perintah PERSIS sesudah CDP siap.
  # `grep -c` mencetak 0 DAN keluar dengan status 1 saat tidak ada kecocokan.
  # Jadi `|| echo 0` di sini mencetak nol KEDUA dan n menjadi "0\n0", yang
  # membuat [[ -gt ]] gagal dengan "syntax error in expression". `|| true`
  # menahan statusnya untuk set -e tanpa menambah keluaran.
  local n; n="$(curl -fsS "http://127.0.0.1:${CDP_PORT}/json" 2>/dev/null | grep -c 'chrome-extension://' || true)"
  n="${n:-0}"
  if [[ "$n" -gt 0 ]]; then _ok "ekstensi terlihat lewat CDP ($n target)"
  else
    _warn "target chrome-extension:// tidak terlihat di /json."
    _warn "Kalau Anda belum memasang wallet: agentdrop extensions"
    _warn "Ini belum tentu cacat: service worker MV3 memang sering tidak"
    _warn "terdaftar di /json walau ekstensinya sehat. Jadi /json bukan bukti."
    _warn "BUKTI sebenarnya cuma satu — di jendela browser, buka halaman lalu"
    _warn "di console cek window.ethereum dan window.solana."
    _warn "Kalau keduanya undefined, popup tidak akan bisa dibuka."
  fi
  echo
  if [[ "$pakai_vnc" == true && "$novnc_hidup" == true ]]; then
    novnc_petunjuk_url
    echo "  (paksa jendela asli di mesin berlayar: BROWSER_MODE=native agentdrop browser)"
  elif [[ "$pakai_vnc" == true ]]; then
    # Mencetak URL yang kita tahu mati adalah cara tercepat membuat operator
    # menyimpulkan "agentdrop rusak" tanpa petunjuk apa pun.
    echo "  noVNC  : TIDAK BISA DINYALAKAN (lihat pesan error di atas)"
    echo "  vnc    : pakai VNC viewer ke 127.0.0.1:${VNC_PORT} — layar tetap ada"
    echo "  log    : $(_log_dir_bg)/novnc.log"
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
  echo "   ekstensi : dipasang dari Chrome Web Store di dalam browser"
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
