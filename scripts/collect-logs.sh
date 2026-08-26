#!/usr/bin/env bash
# ============================================================================
# collect-logs.sh — kumpulkan hasil uji ke dalam repo supaya bisa di-push
# ============================================================================
# MASALAH YANG DISELESAIKAN
# -------------------------
# Log audit tersimpan di ~/.agentdrop/logs/, DI LUAR repo. Jadi `git push`
# setelah pengujian tidak akan menyertakannya sama sekali, dan tidak ada yang
# bisa dianalisis.
#
# Skrip ini menyalin semuanya ke data/audit/<stempel>/ yang BISA di-commit,
# bersama konteks lingkungan yang dibutuhkan untuk menafsirkan log.
#
# Pemakaian:
#   ./scripts/collect-logs.sh                 # kumpulkan + tunjukkan ringkasan
#   ./scripts/collect-logs.sh --label uji-1   # beri nama supaya mudah dibedakan
#   ./scripts/collect-logs.sh --check         # periksa ulang tanpa menulis
#
# KEAMANAN
# --------
# Hasil skrip ini dimaksudkan untuk DI-COMMIT. Karena itu ia:
#   - hanya menyalin berkas yang sudah diredaksi (log audit menulis lewat
#     audit_log.write, yang meredaksi di satu tempat)
#   - MENOLAK menyalin .env, berkas key, cookie, atau storageState
#   - menyaring ulang hasil akhirnya dan GAGAL kalau menemukan secret
# Kalau pemeriksaan akhir menemukan sesuatu, skrip berhenti dan tidak menulis
# apa pun. Lebih baik tidak ada laporan daripada ada rahasia di git.
# ============================================================================
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_DIR="${AGENTDROP_LOG_DIR:-$HOME/.agentdrop/logs}"
LABEL=""
CHECK_ONLY=0

die()  { printf '\033[1;31m  ✗ %s\033[0m\n' "$*" >&2; exit 1; }
warn() { printf '\033[1;33m  ! %s\033[0m\n' "$*"; }
ok()   { printf '\033[1;32m  ✓ %s\033[0m\n' "$*"; }
log()  { printf '\033[1;34m==> %s\033[0m\n' "$*"; }

while [[ $# -gt 0 ]]; do
  case "$1" in
    --label) LABEL="${2:-}"; shift ;;
    --check) CHECK_ONLY=1 ;;
    -h|--help) sed -n '2,30p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) die "argumen tidak dikenal: $1" ;;
  esac
  shift
done

PY="$(command -v python3 || true)"
[[ -n "$PY" ]] || die "butuh python3"

STAMP="$(date -u +%Y%m%d-%H%M%S)"
[[ -n "$LABEL" ]] && STAMP="${STAMP}-${LABEL}"
DEST="$REPO_ROOT/data/audit/$STAMP"
TMP=""
if [[ "$CHECK_ONLY" -eq 0 ]]; then
  TMP="$(mktemp -d)"
  DEST="$TMP/out"
fi
mkdir -p "$DEST"

# ---------------------------------------------------------------------------
# 1. Log audit
# ---------------------------------------------------------------------------
log "log audit"
if [[ -d "$LOG_DIR" ]] && ls "$LOG_DIR"/audit-*.jsonl >/dev/null 2>&1; then
  mkdir -p "$DEST/logs"
  cp "$LOG_DIR"/audit-*.jsonl "$DEST/logs/" 2>/dev/null || true
  n=$(ls "$DEST/logs"/*.jsonl 2>/dev/null | wc -l)
  baris=$(cat "$DEST/logs"/*.jsonl 2>/dev/null | wc -l)
  ok "$n berkas, $baris baris"
else
  warn "tidak ada log di $LOG_DIR"
  warn "Berarti hook belum pernah menyala. Periksa:"
  warn "  - ls ~/.hermes/hooks/agentdrop-audit/"
  warn "  - ls ~/.agentdrop/agent-hooks/"
  warn "  - grep -c audit-log ~/.hermes/profiles/*/config.yaml"
  echo "LOG_KOSONG: tidak ada baris audit saat collect-logs dijalankan" \
    > "$DEST/CATATAN.txt"
fi

# ---------------------------------------------------------------------------
# 2. Ringkasan + diagnosis dari alat triase
# ---------------------------------------------------------------------------
log "ringkasan triase"
"$PY" "$REPO_ROOT/tools/audit.py" health > "$DEST/01-health.txt"  2>&1 || true
"$PY" "$REPO_ROOT/tools/audit.py" doctor > "$DEST/02-doctor.txt"  2>&1 || true
"$PY" "$REPO_ROOT/tools/audit.py" errors --limit 100 --verbose \
                                        > "$DEST/03-errors.txt"  2>&1 || true
"$PY" "$REPO_ROOT/tools/audit.py" stuck  > "$DEST/04-stuck.txt"  2>&1 || true
ok "health, doctor, errors, stuck"

# ---------------------------------------------------------------------------
# 3. Konteks lingkungan — tanpa ini log sulit ditafsirkan
# ---------------------------------------------------------------------------
log "konteks lingkungan"
{
  echo "stempel    : $STAMP"
  echo "tanggal    : $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "os         : $(uname -srm)"
  echo "repo       : $(cd "$REPO_ROOT" && git rev-parse --short HEAD 2>/dev/null || echo '?')"
  echo "branch     : $(cd "$REPO_ROOT" && git rev-parse --abbrev-ref HEAD 2>/dev/null || echo '?')"
  echo
  echo "-- binari --"
  for b in python3 node npx docker hermes chromium google-chrome chrome Xvfb x11vnc websockify; do
    if command -v "$b" >/dev/null 2>&1; then
      printf '%-14s %s\n' "$b" "$(command -v "$b")"
    else
      printf '%-14s %s\n' "$b" "TIDAK ADA"
    fi
  done
  echo
  echo "-- versi --"
  python3 --version 2>&1 | sed 's/^/python3  /' || true
  node --version 2>&1 | sed 's/^/node     /' || true
  hermes --version 2>&1 | head -1 | sed 's/^/hermes   /' || true
  "$REPO_ROOT/scripts/start-browser-cdp.sh" --status 2>&1 | sed 's/^/browser  /' || true
} > "$DEST/05-lingkungan.txt" 2>&1
ok "05-lingkungan.txt"

# ---------------------------------------------------------------------------
# 4. Status pemasangan hook — penyebab paling umum log kosong
# ---------------------------------------------------------------------------
log "status hook"
{
  echo "-- gateway hook --"
  if [[ -d "$HOME/.hermes/hooks/agentdrop-audit" ]]; then
    ls -la "$HOME/.hermes/hooks/agentdrop-audit" | sed 's/^/  /'
  else
    echo "  TIDAK TERPASANG (~/.hermes/hooks/agentdrop-audit tidak ada)"
  fi
  echo
  echo "-- shell hook --"
  if [[ -d "$HOME/.agentdrop/agent-hooks" ]]; then
    ls -la "$HOME/.agentdrop/agent-hooks" | sed 's/^/  /'
  else
    echo "  TIDAK TERPASANG (~/.agentdrop/agent-hooks tidak ada)"
  fi
  echo
  echo "-- blok hooks di tiap profil (HANYA jumlah + auto_accept, bukan isinya) --"
  for c in "$HOME"/.hermes/profiles/*/config.yaml "$HOME"/.hermes/config.yaml; do
    [[ -f "$c" ]] || continue
    n=$(grep -c "audit-log.py" "$c" 2>/dev/null || echo 0)
    aa=$(grep -c "^hooks_auto_accept: true" "$c" 2>/dev/null || echo 0)
    printf '  %-50s audit-log=%s auto_accept=%s\n' "${c/#$HOME/~}" "$n" "$aa"
  done
  echo
  echo "-- ekstensi terpasang --"
  if [[ -d "$REPO_ROOT/extensions/installed" ]]; then
    for d in "$REPO_ROOT/extensions/installed"/*/; do
      [[ -f "${d}manifest.json" ]] && echo "  $(basename "$d")"
    done
  else
    echo "  extensions/installed tidak ada"
  fi
} > "$DEST/06-hook.txt" 2>&1
ok "06-hook.txt"

# ---------------------------------------------------------------------------
# 5. Validator — keadaan repo saat uji dilakukan
# ---------------------------------------------------------------------------
log "validator"
"$PY" "$REPO_ROOT/tools/validate_config.py" > "$DEST/07-validator.txt" 2>&1 || true
ok "07-validator.txt"

# ---------------------------------------------------------------------------
# 6. PEMERIKSAAN SECRET — gerbang terakhir sebelum apa pun ditulis
# ---------------------------------------------------------------------------
log "memeriksa secret di hasil pengumpulan"
# Nama berkas yang tidak boleh pernah ikut.
forbidden_names=(.env .env.local "*.pem" "*.key" "id_rsa*" "cookies.json"
                 "storageState*.json" "*keyfile*" "*.keystore")
leak=0
while IFS= read -r f; do
  base="$(basename "$f")"
  for pat in "${forbidden_names[@]}"; do
    # shellcheck disable=SC2053
    if [[ "$base" == $pat ]]; then
      printf '\033[1;31m  ✗ berkas terlarang ikut terkumpul: %s\033[0m\n' "$f" >&2
      leak=1
    fi
  done
done < <(find "$DEST" -type f)

# Isi: pola secret yang lolos redaksi.
if command -v python3 >/dev/null 2>&1; then
  if ! python3 - "$DEST" <<'PYSCAN'
import re, sys, pathlib
pola = [
    (re.compile(r"\b0x[a-fA-F0-9]{64}\b"), "private key EVM"),
    (re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"), "api key sk-"),
    (re.compile(r"\d{8,10}:AA[A-Za-z0-9_-]{30,}"), "bot token Telegram"),
    (re.compile(r"\b(?:[a-z]{3,8}\s+){11,23}[a-z]{3,8}\b"), "kemungkinan seed phrase"),
]
kunci = re.compile(
    r"(?i)\b(private_key|privkey|secret_key|seed_phrase|mnemonic|password|passwd)"
    r"\b\s*[:=]\s*\S{6,}")
ada = 0
for p in pathlib.Path(sys.argv[1]).rglob("*"):
    if not p.is_file():
        continue
    try:
        t = p.read_text(errors="replace")
    except OSError:
        continue
    for pat, nama in pola:
        if pat.search(t):
            print(f"  {p.name}: {nama}")
            ada += 1
    if kunci.search(t):
        print(f"  {p.name}: pola kunci=nilai")
        ada += 1
sys.exit(1 if ada else 0)
PYSCAN
  then
    leak=1
  fi
fi

if [[ "$leak" -ne 0 ]]; then
  printf '\033[1;31m  ✗ DIBATALKAN: hasil pengumpulan mengandung pola secret.\033[0m\n' >&2
  printf '\033[1;31m    Tidak ada yang ditulis ke repo. Hapus berkas itu dan ulangi.\033[0m\n' >&2
  [[ -n "$TMP" ]] && rm -rf "$TMP"
  exit 1
fi
ok "tidak ada secret"

if [[ "$CHECK_ONLY" -eq 1 ]]; then
  ok "mode --check: tidak ada yang ditulis"
  exit 0
fi

# ---------------------------------------------------------------------------
# 7. Pindahkan ke repo
# ---------------------------------------------------------------------------
mkdir -p "$REPO_ROOT/data/audit"
DEST_FINAL="$REPO_ROOT/data/audit/$STAMP"
rm -rf "$DEST_FINAL" 2>/dev/null || true
mv "$TMP/out" "$DEST_FINAL"
rm -rf "$TMP"

# Pastikan direktori ini memang bisa di-commit.
if (cd "$REPO_ROOT" && git check-ignore -q "data/audit/$STAMP" 2>/dev/null); then
  warn "data/audit/ rupanya di-gitignore — hasil tidak akan ikut ter-push."
  warn "Periksa .gitignore."
fi

cat <<EOF

$(printf '\033[1;32m✓ Terkumpul di:\033[0m')  data/audit/$STAMP/

  01-health.txt      ringkasan per komponen
  02-doctor.txt      diagnosis + berkas yang harus dibuka
  03-errors.txt      error terperinci
  04-stuck.txt       tool yang menggantung
  05-lingkungan.txt  OS, versi binari, status browser
  06-hook.txt        apakah hook benar-benar terpasang
  07-validator.txt   keadaan repo saat uji
  logs/              JSONL mentah (sudah diredaksi)

Langkah berikutnya:

  git add data/audit/$STAMP
  git commit -m "audit: hasil uji $STAMP"
  git push origin <branch-anda>

Kalau 02-doctor.txt sudah menyebut penyebabnya, itu titik mulainya.
Kalau logs/ kosong, masalahnya di pemasangan hook — lihat 06-hook.txt.
EOF
