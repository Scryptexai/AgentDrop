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

  sc "[1] Biner"
  for b in python3 curl node; do
    command -v "$b" >/dev/null 2>&1 && ok "$b ada" || bd "$b tidak ada"
  done
  command -v hermes >/dev/null 2>&1 && ok "hermes ada" || bd "hermes tidak ada"
  "$(_pyu)" -c 'import yaml' 2>/dev/null && ok "PyYAML" || bd "PyYAML (jalankan ./install.sh)"

  sc "[2] Kredensial"
  local ENVF="$HERMES_HOME_DIR/.env"
  if [[ -f "$ENVF" ]]; then
    ok "~/.hermes/.env ada"
    grep -qE '^[A-Z_]*PRIVATE_KEY=.+' "$ENVF" \
      && bd ".env berisi PRIVATE_KEY — aturan keras: pakai AGENTDROP_KEY_FILE" \
      || ok ".env tidak berisi private key"
    grep -qE '^TELEGRAM_BOT_TOKEN=.+' "$ENVF" && ok "TELEGRAM_BOT_TOKEN" || wn "TELEGRAM_BOT_TOKEN kosong"
    grep -qE '^(OPENROUTER_API_KEY|ANTHROPIC_API_KEY|OPENAI_API_KEY|GOOGLE_API_KEY|GEMINI_API_KEY|NOUS_API_KEY)=.+' "$ENVF" \
      && ok "kunci model ada" || bd "tidak ada kunci model — agent tidak bisa berpikir"
  else bd "~/.hermes/.env tidak ada — jalankan ./install.sh"; fi

  sc "[3] Profil + hook audit"
  local n=0 h=0 a=0 d=0 c
  for c in "$HERMES_HOME_DIR"/profiles/*/config.yaml; do
    [[ -f "$c" ]] || continue
    n=$((n+1))
    grep -q "audit-log.py" "$c" && h=$((h+1))
    grep -qE "^hooks_auto_accept: true" "$c" && a=$((a+1))
    grep -q "disabled_toolsets" "$c" && d=$((d+1))
  done
  if [[ "$n" -eq 0 ]]; then bd "tidak ada profil di ~/.hermes/profiles/"
  else
    ok "$n profil"
    [[ "$h" -eq "$n" ]] && ok "hook audit di semua profil" || bd "hook audit hanya $h/$n — log akan berlubang"
    [[ "$a" -eq "$n" ]] && ok "hooks_auto_accept di semua profil" || bd "hooks_auto_accept kurang di $((n-a)) profil — hook diabaikan diam-diam pada cron/gateway"
    [[ "$d" -eq "$n" ]] && ok "akses shell dimatikan di semua profil" || bd "disabled_toolsets kurang di $((n-d)) profil — agent bisa membuka browser sendiri lewat shell"
  fi
  [[ -f "$HERMES_HOME_DIR/hooks/agentdrop-audit/handler.py" ]] && ok "gateway hook" || bd "gateway hook tidak terpasang"
  [[ -f "$STATE_DIR/agent-hooks/audit-log.py" ]] && ok "shell hook" || bd "shell hook tidak terpasang"
  [[ -f "$HERMES_HOME_DIR/hooks/agentdrop-audit/audit_log.py" ]] && ok "audit_log.py di sebelah hook" || wn "audit_log.py tidak ada di direktori hook"

  sc "[4] Browser + ekstensi"
  local CHROME; CHROME="$(browser_find_chrome || true)"
  if [[ -n "$CHROME" ]]; then
    ok "Chrome for Testing"
    case "$(basename "$CHROME")" in
      google-chrome|google-chrome-stable) bd "ini Chrome BRANDED — --load-extension diabaikan sejak 137" ;;
      *) ok "bukan build branded" ;;
    esac
  else bd "Chrome for Testing tidak ada — ./agentdrop browser"; fi

  local ne=0 dd
  if [[ -d "$EXT_ROOT" ]]; then
    for dd in "$EXT_ROOT"/*/; do [[ -f "${dd}manifest.json" ]] && ne=$((ne+1)); done
  fi
  [[ "$ne" -gt 0 ]] && ok "$ne ekstensi wallet" || bd "tidak ada ekstensi — ./agentdrop extensions"
  curl -fsS --max-time 3 "http://127.0.0.1:${CDP_PORT}/json/version" >/dev/null 2>&1 \
    && ok "CDP menjawab di ${CDP_PORT}" || wn "CDP tidak menjawab — ./agentdrop browser"

  sc "[5] Repo"
  if "$(_pyu)" "$REPO_ROOT/tools/validate_config.py" >/tmp/ad-val.txt 2>&1; then
    ok "validator lolos ($(grep -oE '[0-9]+ file diperiksa' /tmp/ad-val.txt | head -1))"
  else bd "validator GAGAL:"; tail -6 /tmp/ad-val.txt | sed 's/^/      /'; fi

  sc "Hasil"
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
