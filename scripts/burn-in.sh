#!/usr/bin/env bash
# ============================================================================
# burn-in.sh — jalankan uji stabilisasi browser SEBELUM agent dipakai kerja
# ============================================================================
# Tujuan: memastikan lapisan browser (Chrome/CDP + noVNC + persistence + snapshot
# accessibility tree) benar-benar berfungsi di mesin ini, dengan eksekusi nyata,
# sebelum kita mempercayakan campaign sungguhan ke agent.
#
# Pemakaian:
#   ./scripts/burn-in.sh                 # Uji 1-4 (aman, tanpa wallet/sosial)
#   ./scripts/burn-in.sh 3               # hanya Uji 3
#   ./scripts/burn-in.sh --with-wallet   # tambahkan Uji 5 (connect wallet)
#   ./scripts/burn-in.sh --with-social   # tambahkan Uji 6 (alur sosial nyata)
#   ./scripts/burn-in.sh --all           # Uji 1-6
#   ./scripts/burn-in.sh --profile worker-quests   # pakai profil lain
#
# Uji 5 dan 6 sengaja TIDAK jalan secara default: keduanya menyentuh wallet dan
# akun sosial Anda. Keduanya butuh flag eksplisit.
#
# CATATAN sintaks (sama seperti start-agent.sh):
#   `hermes chat` tidak menerima argumen posisional — prompt lewat -q saja.
#   `--profile` di-scan sebelum argparse, jadi aman diletakkan di depan.
# ============================================================================
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

PROFILE="worker-daily"
WALLET=0
SOCIAL=0
ONLY=""

die()  { printf '\033[1;31m  ✗ %s\033[0m\n' "$*" >&2; exit 1; }
warn() { printf '\033[1;33m  ! %s\033[0m\n' "$*"; }
ok()   { printf '\033[1;32m  ✓ %s\033[0m\n' "$*"; }
step() { printf '\n\033[1;36m%s\033[0m\n' "$*"; }

while [[ $# -gt 0 ]]; do
  case "$1" in
    --with-wallet) WALLET=1; shift ;;
    --with-social) SOCIAL=1; shift ;;
    --all)         WALLET=1; SOCIAL=1; shift ;;
    --profile|-p)  PROFILE="${2:-}"; shift 2 ;;
    -h|--help)     sed -n '2,22p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    ''|*[!0-9]*)   die "Argumen tidak dikenal: $1 (angka uji, atau --with-wallet/--with-social/--all/--profile)" ;;
    *)             ONLY="$1"; shift ;;
  esac
done

# ----------------------------------------------------------------------------
# Prasyarat
# ----------------------------------------------------------------------------
step "[1/4] Memeriksa prasyarat"

command -v hermes >/dev/null 2>&1 \
  || die "'hermes' tidak ada di PATH. Jalankan ./install.sh lalu 'source ~/.bashrc'."
ok "hermes ditemukan: $(command -v hermes)"

[[ -d "${REPO_ROOT}/config/hermes/profiles/${PROFILE}" ]] \
  || die "Profil '${PROFILE}' tidak ada di config/hermes/profiles/."
ok "profil: ${PROFILE}"

[[ -f "${REPO_ROOT}/skills/browser-burn-in/SKILL.md" ]] \
  || die "skills/browser-burn-in/SKILL.md tidak ada."

# Skill harus sudah tersalin ke profil — setup.sh yang melakukannya.
PROFILE_SKILLS="${HOME}/.hermes/profiles/${PROFILE}/skills/browser-burn-in"
[[ -d "${PROFILE_SKILLS}" ]] \
  || die "Skill 'browser-burn-in' belum terpasang di profil ${PROFILE}. Jalankan ./scripts/setup.sh."
ok "skill browser-burn-in terpasang untuk profil ini"

# ----------------------------------------------------------------------------
# Browser harus hidup. Burn-in tanpa browser yang hidup hanya membuang token.
# ----------------------------------------------------------------------------
step "[2/4] Memeriksa browser"

PORT="${CDP_PORT:-9222}"
healthy=0
for _ in $(seq 1 12); do
  if curl -fsS "http://127.0.0.1:${PORT}/json/version" >/dev/null 2>&1; then healthy=1; break; fi
  sleep 5
done
[[ "$healthy" -eq 1 ]] || die "CDP tidak menjawab di port ${PORT}. Jalankan: agentdrop browser"
ok "Chrome menjawab di http://127.0.0.1:${PORT}/json/version"

# Burn-in justru untuk DITONTON. Tanpa noVNC Anda buta saat agent salah.
NOVNC_PORT="${NOVNC_PORT:-6080}"
if curl -fsS -o /dev/null "http://127.0.0.1:${NOVNC_PORT}/vnc.html" 2>/dev/null; then
  ok "noVNC siap — tonton di http://localhost:${NOVNC_PORT}/vnc.html"
  warn "Buka noVNC di tab lain SEBELUM lanjut. Uji ini harus disaksikan, bukan hanya dibaca lognya."
else
  warn "noVNC tidak menjawab di port ${NOVNC_PORT}. Uji tetap jalan, tapi Anda tidak bisa menonton."
  warn "Untuk menyalakannya: agentdrop browser"
fi

# ----------------------------------------------------------------------------
# Rakit daftar uji
# ----------------------------------------------------------------------------
step "[3/4] Menyusun daftar uji"

TESTS=()
add() { TESTS+=("$1"); }

if [[ -n "$ONLY" ]]; then
  add "$ONLY"
else
  add 1; add 2; add 3; add 4
  [[ "$WALLET" -eq 1 ]] && add 5
  [[ "$SOCIAL" -eq 1 ]] && add 6
fi

# Uji 5 & 6 tidak boleh menyusup lewat --profile maupun urutan acak.
for t in "${TESTS[@]}"; do
  if [[ "$t" == "5" && "$WALLET" -eq 0 ]]; then die "Uji 5 butuh --with-wallet (menyentuh wallet)." ; fi
  if [[ "$t" == "6" && "$SOCIAL" -eq 0 ]]; then die "Uji 6 butuh --with-social (menyentuh akun sosial)."; fi
done

printf '  Uji yang akan dijalankan: %s\n' "${TESTS[*]}"

if [[ "$WALLET" -eq 1 ]]; then
  warn "Uji 5 AKAN menyentuh wallet. Pastikan ini TESTNET, bukan mainnet."
  printf '  Ketik TESTNET untuk lanjut: '
  read -r jawab
  [[ "$jawab" == "TESTNET" ]] || die "Dibatalkan. Uji 5 tidak dijalankan."
fi

# ----------------------------------------------------------------------------
# Jalankan satu per satu — bukan sekaligus
# ----------------------------------------------------------------------------
# Sengaja dipecah: kalau semuanya dikirim dalam satu prompt, kegagalan di Uji 2
# akan menular ke Uji 3-6 dan Anda tidak tahu lapisan mana yang rusak.
step "[4/4] Menjalankan uji"

FAIL=0
for t in "${TESTS[@]}"; do
  printf '\n\033[1;36m--- Uji %s ---\033[0m\n' "$t"
  PROMPT="Jalankan HANYA Uji ${t} dari skill browser-burn-in.
Ikuti Protokol Browser di SOUL.md: ambil elemen dari browser_snapshot, klik
memakai ref dari snapshot terbaru, tidak ada CSS selector.
Setelah aksi, verifikasi hasilnya sebelum melanjutkan.
Jangan menjalankan uji lain. Laporkan hasilnya dalam format laporan skill itu."

  if ! hermes --profile "${PROFILE}" chat -q "${PROMPT}"; then
    warn "Uji ${t} keluar dengan status bukan-nol."
    FAIL=1
  fi
  printf '\033[1;36m--- Uji %s selesai ---\033[0m\n' "$t"
done

# ----------------------------------------------------------------------------
echo
if [[ "$FAIL" -eq 0 ]]; then
  ok "Semua uji selesai dijalankan."
else
  warn "Ada uji yang keluar dengan status bukan-nol — periksa laporannya."
fi

cat <<'EOF'

Langkah berikutnya:
  1. Baca laporan uji (ditulis agent sesuai skill browser-burn-in).
  2. Tonton ulang lewat noVNC kalau ada hasil yang meragukan.
  3. Kalau ada uji yang gagal 3x dengan cara yang sama — itu bukan masalah
     prompt, itu masalah lingkungan. Perbaiki lingkungan dulu.
  4. Jangan naik ke campaign sungguhan sebelum Uji 1-4 hijau.
EOF

exit "$FAIL"
