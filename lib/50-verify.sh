# lib/50-verify.sh — periksa kesiapan SEBELUM satu run dimulai.
# Di-source oleh install.sh (akhir) dan ./agentdrop status.

# Pencacah global: bash tidak mengizinkan `local` untuk definisi fungsi, jadi
# helper ini hidup di tingkat berkas dan memakai prefiks V_ supaya tidak
# bentrok dengan pencacah lain.
_vok(){ printf '\033[1;32m  ✓\033[0m %s\n' "$*"; V_PASS=$((V_PASS+1)); }
_vwn(){ printf '\033[1;33m  !\033[0m %s\n' "$*"; V_WARN=$((V_WARN+1)); }
_vbd(){ printf '\033[1;31m  ✗\033[0m %s\n' "$*"; V_FAIL=$((V_FAIL+1)); }
_vsc(){ printf '\n\033[1;34m%s\033[0m\n' "$*"; }

verify_run() {  # verify_run [--strict]
  local strict=0; [[ "${1:-}" == "--strict" ]] && strict=1
  V_FAIL=0; V_WARN=0; V_PASS=0

  _vsc "[1] Biner"
  for b in python3 curl node; do
    command -v "$b" >/dev/null 2>&1 && _vok "$b ada" || _vbd "$b tidak ada"
  done
  command -v hermes >/dev/null 2>&1 && _vok "hermes ada" || _vbd "hermes tidak ada"
  "$(_pyu)" -c 'import yaml' 2>/dev/null && _vok "PyYAML" || _vbd "PyYAML (jalankan ./install.sh)"

  _vsc "[2] Kredensial"
  local ENVF="$HERMES_HOME_DIR/.env"
  if [[ -f "$ENVF" ]]; then
    _vok "~/.hermes/.env ada"
    grep -qE '^[A-Z_]*PRIVATE_KEY=.+' "$ENVF" \
      && _vbd ".env berisi PRIVATE_KEY — aturan keras: pakai AGENTDROP_KEY_FILE" \
      || _vok ".env tidak berisi private key"
    grep -qE '^TELEGRAM_BOT_TOKEN=.+' "$ENVF" && _vok "TELEGRAM_BOT_TOKEN" || _vwn "TELEGRAM_BOT_TOKEN kosong"
    grep -qE '^(OPENROUTER_API_KEY|ANTHROPIC_API_KEY|OPENAI_API_KEY|GOOGLE_API_KEY|GEMINI_API_KEY|NOUS_API_KEY)=.+' "$ENVF" \
      && _vok "kunci model ada" || _vbd "tidak ada kunci model — agent tidak bisa berpikir"
  else _vbd "~/.hermes/.env tidak ada — jalankan ./install.sh"; fi

  _vsc "[3] Profil + hook audit"
  local n=0 h=0 a=0 d=0 c
  for c in "$HERMES_HOME_DIR"/profiles/*/config.yaml; do
    [[ -f "$c" ]] || continue
    n=$((n+1))
    grep -q "audit-log.py" "$c" && h=$((h+1))
    grep -qE "^hooks_auto_accept: true" "$c" && a=$((a+1))
    grep -q "disabled_toolsets" "$c" && d=$((d+1))
  done
  if [[ "$n" -eq 0 ]]; then _vbd "tidak ada profil di ~/.hermes/profiles/"
  else
    _vok "$n profil"
    [[ "$h" -eq "$n" ]] && _vok "hook audit di semua profil" || _vbd "hook audit hanya $h/$n — log akan berlubang"
    [[ "$a" -eq "$n" ]] && _vok "hooks_auto_accept di semua profil" || _vbd "hooks_auto_accept kurang di $((n-a)) profil — hook diabaikan diam-diam pada cron/gateway"
    [[ "$d" -eq "$n" ]] && _vok "akses shell dimatikan di semua profil" || _vbd "disabled_toolsets kurang di $((n-d)) profil — agent bisa membuka browser sendiri lewat shell"
  fi
  [[ -f "$HERMES_HOME_DIR/hooks/agentdrop-audit/handler.py" ]] && _vok "gateway hook" || _vbd "gateway hook tidak terpasang"
  [[ -f "$STATE_DIR/agent-hooks/audit-log.py" ]] && _vok "shell hook" || _vbd "shell hook tidak terpasang"
  [[ -f "$HERMES_HOME_DIR/hooks/agentdrop-audit/audit_log.py" ]] && _vok "audit_log.py di sebelah hook" || _vwn "audit_log.py tidak ada di direktori hook"

  _vsc "[4] Browser + ekstensi"
  local CHROME; CHROME="$(browser_find_chrome || true)"
  if [[ -n "$CHROME" ]]; then
    _vok "Chrome for Testing"
    case "$(basename "$CHROME")" in
      google-chrome|google-chrome-stable) _vbd "ini Chrome BRANDED — --load-extension diabaikan sejak 137" ;;
      *) _vok "bukan build branded" ;;
    esac
  else _vbd "Chrome for Testing tidak ada — ./agentdrop browser"; fi

  local ne=0 dd
  if [[ -d "$EXT_ROOT" ]]; then
    for dd in "$EXT_ROOT"/*/; do [[ -f "${dd}manifest.json" ]] && ne=$((ne+1)); done
  fi
  [[ "$ne" -gt 0 ]] && _vok "$ne ekstensi wallet" || _vbd "tidak ada ekstensi — ./agentdrop extensions"
  curl -fsS --max-time 3 "http://127.0.0.1:${CDP_PORT}/json/version" >/dev/null 2>&1 \
    && _vok "CDP menjawab di ${CDP_PORT}" || _vwn "CDP tidak menjawab — ./agentdrop browser"

  _vsc "[5] Pintasan Telegram"
  # Operator melaporkan semua perintah /riset /quest dst dibalas "Unknown
  # command". Penyebabnya bukan di skill-nya: Hermes memindai skill menjadi
  # perintah /nama-skill (agent/skill_commands.py:424 scan_skill_commands),
  # tapi cache-nya hanya di-refresh kalau PLATFORM atau HERMES_HOME berubah
  # (skill_commands.py:565-568) — BUKAN kalau isi folder skill berubah.
  #
  # Akibatnya: install.sh menyalin skill baru ke ~/.hermes/skills, tapi gateway
  # yang sudah hidup tidak pernah melihatnya. Perintah itu baru ada setelah
  # gateway di-restart. Ini sudah dibuktikan: skill yang ditambahkan saat
  # proses hidup tetap tidak ter-resolve.
  #
  # Jadi pemeriksaan ini memisahkan dua kegagalan yang gejalanya sama:
  #   skill belum tersalin  -> jalankan ./install.sh
  #   skill ada tapi gateway belum di-restart -> jalankan agentdrop stop && start
  local _sk _ada=0 _hilang=""
  for _sk in panggil-pekerja riset harian quest daftar x discord pantau; do
    if [[ -f "$HERMES_HOME_DIR/skills/$_sk/SKILL.md" ]]; then
      _ada=$((_ada+1))
    else
      _hilang="$_hilang $_sk"
    fi
  done
  if [[ "$_ada" -eq 8 ]]; then
    _vok "8 skill pintasan terpasang di ~/.hermes/skills"
  else
    _vbd "skill pintasan belum terpasang:$_hilang"
    echo "        jalankan: ./install.sh"
  fi

  # Gateway yang hidup saat install dijalankan TIDAK melihat skill baru.
  # PID_DIR hanya didefinisikan di CLI `agentdrop`, bukan di lib/*.sh, dan
  # verify_run bisa dipanggil dari install.sh yang tidak punya variabel itu.
  # Karena itu dihitung ulang dari STATE_DIR, dengan fallback kalau kosong.
  local _piddir="${PID_DIR:-$STATE_DIR/run}"
  if [[ -f "$_piddir/gateway.pid" ]] && kill -0 "$(cat "$_piddir/gateway.pid")" 2>/dev/null; then
    local _pid _mulaipid _skillbaru
    _pid="$(cat "$_piddir/gateway.pid")"
    # Waktu mulai proses gateway vs waktu skill terakhir diubah.
    # `stat -c %Y /proc/<pid>` TIDAK memberi waktu mulai proses — ia memberi
    # waktu AKSES, yang berubah setiap kali ada yang membaca direktori itu.
    # Versi pertama pemeriksaan ini memakainya dan karena itu selalu menyimpulkan
    # "gateway hidup setelah skill terpasang", termasuk pada kasus yang justru
    # harus ditangkap. `ps -o lstart=` adalah waktu mulai yang sebenarnya.
    _mulaipid="$(date -d "$(ps -o lstart= -p "$_pid" 2>/dev/null)" +%s 2>/dev/null || echo 0)"
    _skillbaru="$(stat -c %Y "$HERMES_HOME_DIR/skills/panggil-pekerja/SKILL.md" 2>/dev/null || echo 0)"
    if [[ "${_mulaipid:-0}" -gt 0 && "$_skillbaru" -gt "$_mulaipid" ]]; then
      _vbd "gateway (pid $_pid) dimulai SEBELUM skill terpasang — perintah /riset dst akan dibalas Unknown command"
      echo "        cache skill Hermes tidak di-refresh oleh perubahan folder"
      echo "        (agent/skill_commands.py:565-568). Jalankan:"
      echo "          agentdrop stop && agentdrop start"
    else
      _vok "gateway hidup setelah skill terpasang"
    fi
  else
    _vwn "gateway tidak jalan — nyalakan dengan: agentdrop start"
  fi

  _vsc "[6] Repo"
  if "$(_pyu)" "$REPO_ROOT/tools/validate_config.py" >/tmp/ad-val.txt 2>&1; then
    _vok "validator lolos ($(grep -oE '[0-9]+ file diperiksa' /tmp/ad-val.txt | head -1))"
  else _vbd "validator GAGAL:"; tail -6 /tmp/ad-val.txt | sed 's/^/      /'; fi

  _vsc "Hasil"
  printf '  lulus: %d   peringatan: %d   gagal: %d\n' "$V_PASS" "$V_WARN" "$V_FAIL"
  if [[ "$V_FAIL" -gt 0 ]]; then
    printf '\033[1;31mJANGAN mulai run. Perbaiki yang ✗ lebih dulu.\033[0m\n'; return 1
  fi
  if [[ "$V_WARN" -gt 0 ]]; then
    printf '\033[1;33mBoleh jalan, ada %d peringatan.\033[0m\n' "$V_WARN"
    [[ "$strict" -eq 1 ]] && return 2
  else
    printf '\033[1;32mSiap.\033[0m\n'
  fi
  return 0
}
