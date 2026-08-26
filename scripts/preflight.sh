#!/usr/bin/env bash
# ============================================================================
# preflight.sh — periksa semuanya SEBELUM satu run uji dimulai
# ============================================================================
# Alasan skrip ini ada: satu run uji memakan waktu. Kalau browser tidak bisa
# memuat ekstensi, atau hook tidak terpasang, Anda baru tahu di akhir — dan
# lognya kosong atau tidak berarti. Semua itu bisa dideteksi dalam lima detik.
#
# Pemakaian:
#   ./scripts/preflight.sh              periksa semua
#   ./scripts/preflight.sh --strict     keluar non-zero kalau ada WARN juga
#
# Kode keluar:
#   0  siap
#   1  ada FAIL  (jangan mulai uji)
#   2  hanya WARN (boleh jalan, tapi baca dulu)
# ============================================================================
set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STRICT=0
[[ "${1:-}" == "--strict" ]] && STRICT=1

FAIL=0; WARN=0; PASS=0

ok()   { printf '\033[1;32m  ✓\033[0m %s\n' "$*"; PASS=$((PASS+1)); }
warn() { printf '\033[1;33m  !\033[0m %s\n' "$*"; WARN=$((WARN+1)); }
bad()  { printf '\033[1;31m  ✗\033[0m %s\n' "$*"; FAIL=$((FAIL+1)); }
sec()  { printf '\n\033[1;34m%s\033[0m\n' "$*"; }

# ---------------------------------------------------------------------------
sec "[1] Biner dasar"
for b in python3 curl; do
  command -v "$b" >/dev/null 2>&1 && ok "$b ada" || bad "$b tidak ada"
done
command -v node >/dev/null 2>&1 && ok "node $(node --version)" \
  || bad "node tidak ada — Hermes menjalankan browser lewat npx agent-browser"
command -v hermes >/dev/null 2>&1 && ok "hermes ada" \
  || bad "hermes tidak ada — jalankan install.sh lebih dulu"

python3 -c 'import yaml' 2>/dev/null && ok "PyYAML" || bad "PyYAML tidak ada"
python3 -c 'import eth_account' 2>/dev/null && ok "eth-account" \
  || bad "eth-account tidak ada — daemon signing tidak bisa jalan (install.sh bagian 2d)"

# ---------------------------------------------------------------------------
sec "[2] Kredensial"
ENVF="$HOME/.hermes/.env"
if [[ -f "$ENVF" ]]; then
  ok "~/.hermes/.env ada"
  # ATURAN KERAS: private key tidak boleh ada di .env. File itu tersalin ke
  # setiap profil, jadi satu key di sana berarti key ada di tujuh tempat.
  if grep -qE '^[A-Z_]*PRIVATE_KEY=.+' "$ENVF"; then
    bad ".env berisi PRIVATE_KEY. Aturan keras: key ditaruh di AGENTDROP_KEY_FILE"
  else
    ok ".env tidak berisi private key"
  fi
  for k in TELEGRAM_BOT_TOKEN; do
    if grep -qE "^${k}=.+" "$ENVF"; then ok "$k terisi"; else warn "$k kosong"; fi
  done
  if grep -qE '^(OPENROUTER_API_KEY|ANTHROPIC_API_KEY|OPENAI_API_KEY|GOOGLE_API_KEY|GEMINI_API_KEY|NOUS_API_KEY)=.+' "$ENVF"; then
    ok "setidaknya satu kunci model terisi"
  else
    bad "tidak ada kunci model — agent tidak akan bisa berpikir"
  fi
else
  bad "~/.hermes/.env tidak ada — jalankan install.sh"
fi

KEYF="$(grep -E '^AGENTDROP_KEY_FILE=' "$ENVF" 2>/dev/null | cut -d= -f2- | tr -d '\"')"
if [[ -n "${KEYF:-}" ]]; then
  KEXP="${KEYF/#\~/$HOME}"
  if [[ -f "$KEXP" ]]; then
    ok "key file ada: $KEXP"
    perm=$(stat -c '%a' "$KEXP" 2>/dev/null || stat -f '%Lp' "$KEXP" 2>/dev/null || echo '?')
    [[ "$perm" == "600" ]] && ok "izin key file 600" \
      || warn "izin key file $perm — seharusnya 600: chmod 600 $KEXP"
  else
    bad "AGENTDROP_KEY_FILE menunjuk $KEXP tapi filenya tidak ada"
  fi
else
  warn "AGENTDROP_KEY_FILE tidak disetel — daemon signing tidak akan bisa signing"
fi

# ---------------------------------------------------------------------------
sec "[3] Profil + hook audit"
nprof=0; nhook=0; naa=0; ndis=0
for c in "$HOME"/.hermes/profiles/*/config.yaml; do
  [[ -f "$c" ]] || continue
  nprof=$((nprof+1))
  grep -q "audit-log.py" "$c" && nhook=$((nhook+1))
  grep -qE "^hooks_auto_accept: true" "$c" && naa=$((naa+1))
  grep -q "disabled_toolsets" "$c" && ndis=$((ndis+1))
done
if [[ "$nprof" -eq 0 ]]; then
  bad "tidak ada profil terpasang di ~/.hermes/profiles/"
else
  ok "$nprof profil terpasang"
  [[ "$nhook" -eq "$nprof" ]] && ok "semua profil punya hook audit" \
    || bad "hanya $nhook/$nprof profil punya hook audit — log akan berlubang"
  [[ "$naa" -eq "$nprof" ]] && ok "hooks_auto_accept=true di semua profil" \
    || bad "hooks_auto_accept bukan true di $((nprof-naa)) profil — pada cron/gateway hook diabaikan diam-diam"
  [[ "$ndis" -eq "$nprof" ]] && ok "akses shell dimatikan di semua profil" \
    || bad "disabled_toolsets hilang di $((nprof-ndis)) profil — agent bisa membuka browser sendiri lewat shell"
fi

[[ -f "$HOME/.hermes/hooks/agentdrop-audit/handler.py" ]] \
  && ok "gateway hook terpasang" \
  || bad "~/.hermes/hooks/agentdrop-audit/handler.py tidak ada — sisi agent tidak tercatat"
[[ -f "$HOME/.agentdrop/agent-hooks/audit-log.py" ]] \
  && ok "shell hook terpasang" \
  || bad "~/.agentdrop/agent-hooks/audit-log.py tidak ada — sisi tool tidak tercatat"
[[ -f "$HOME/.hermes/hooks/agentdrop-audit/audit_log.py" ]] \
  && ok "audit_log.py tersalin ke sebelah hook" \
  || warn "audit_log.py tidak ada di direktori hook — handler akan pakai penulis darurat"

# ---------------------------------------------------------------------------
sec "[4] Browser"
CHROME=""
for c in "$HOME/.cache/puppeteer"/chrome/*/chrome-linux64/chrome; do
  [[ -x "$c" ]] && { CHROME="$c"; break; }
done
[[ -z "$CHROME" ]] && command -v chrome-for-testing >/dev/null 2>&1 && CHROME="$(command -v chrome-for-testing)"
if [[ -n "$CHROME" ]]; then
  ok "Chrome for Testing: $CHROME"
  # Chrome branded mengabaikan --load-extension sejak 137. Ini penyebab
  # kegagalan "ekstensi tidak termuat" yang paling sering.
  if "$CHROME" --version 2>/dev/null | grep -qi "google"; then
    bad "ini Google Chrome BRANDED — --load-extension diabaikan sejak Chrome 137"
  else
    ok "bukan build branded"
  fi
else
  bad "Chrome for Testing tidak ditemukan — jalankan scripts/start-browser-cdp.sh"
fi

if [[ -d "$REPO_ROOT/extensions/installed" ]]; then
  ne=0; for d in "$REPO_ROOT/extensions/installed"/*/; do
    [[ -f "${d}manifest.json" ]] && ne=$((ne+1)); done
  [[ "$ne" -gt 0 ]] && ok "$ne ekstensi terpasang" \
    || bad "extensions/installed ada tapi kosong — jalankan scripts/install-extensions.sh"
else
  bad "extensions/installed tidak ada — tanpa wallet, sebagian besar task airdrop mustahil"
fi

if curl -fsS --max-time 3 "http://127.0.0.1:9222/json/version" >/dev/null 2>&1; then
  ok "CDP menjawab di 9222"
else
  warn "CDP tidak menjawab di 9222 — jalankan scripts/start-browser-cdp.sh sebelum uji"
fi
for b in Xvfb x11vnc; do
  command -v "$b" >/dev/null 2>&1 && ok "$b ada" \
    || warn "$b tidak ada — browser jalan tanpa GUI yang bisa dilihat (login manual mustahil)"
done

# ---------------------------------------------------------------------------
sec "[5] Daemon signing"
if curl -fsS --max-time 3 "http://127.0.0.1:9721/health" >/dev/null 2>&1; then
  ok "daemon menjawab di 9721"
else
  warn "daemon tidak menjawab di 9721 — jalankan tools/signing_daemon.py"
fi
if grep -qE '^AGENTDROP_SIGNER_TOKEN=.+' "$ENVF" 2>/dev/null; then
  ok "AGENTDROP_SIGNER_TOKEN terisi"
else
  bad "AGENTDROP_SIGNER_TOKEN kosong — extension tidak bisa memanggil daemon"
fi
if curl -fsS --max-time 3 -X POST "http://127.0.0.1:9721/" >/dev/null 2>&1; then
  bad "daemon menjawab TANPA token — itu lubang keamanan"
fi

# ---------------------------------------------------------------------------
sec "[6] Repo"
if python3 -c 'import yaml' 2>/dev/null; then
  if python3 "$REPO_ROOT/tools/validate_config.py" >/tmp/pf-val.txt 2>&1; then
    ok "validator lolos ($(grep -oE '[0-9]+ file diperiksa' /tmp/pf-val.txt | head -1))"
  else
    bad "validator GAGAL:"; tail -6 /tmp/pf-val.txt | sed 's/^/      /'
  fi
fi
[[ -f "$REPO_ROOT/config/hermes/signing-policy.yaml" ]] && ok "signing-policy.yaml ada" \
  || bad "signing-policy.yaml tidak ada"

# ---------------------------------------------------------------------------
sec "Hasil"
printf '  lulus: %d   peringatan: %d   gagal: %d\n' "$PASS" "$WARN" "$FAIL"
echo
if [[ "$FAIL" -gt 0 ]]; then
  printf '\033[1;31mJANGAN mulai uji. Perbaiki yang ✗ lebih dulu.\033[0m\n'
  exit 1
fi
if [[ "$WARN" -gt 0 ]]; then
  printf '\033[1;33mBoleh jalan, tapi ada %d peringatan.\033[0m\n' "$WARN"
  [[ "$STRICT" -eq 1 ]] && exit 2
  exit 0
fi
printf '\033[1;32mSiap. Setelah uji selesai:\033[0m\n'
printf '  ./scripts/collect-logs.sh --label <nama>\n'
printf '  git add data/audit/<stempel> && git commit && git push\n'
exit 0
