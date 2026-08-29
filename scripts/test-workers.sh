#!/usr/bin/env bash
# scripts/test-workers.sh — uji fungsional SEMUA worker, satu per satu.
#
# Kenapa skrip ini ada, dan kenapa ia tidak boleh menilai dari exit code:
#
#   `hermes --profile X chat -q "..."` mengembalikan rc=0 WALAU task-nya gagal.
#   Sudah terjadi di mesin operator: panggilan API pertama ditolak HTTP 402,
#   agent tidak pernah memanggil satu tool pun, dan agentdrop tetap mencetak
#   "✓ worker-onboard selesai (rc=0)". Exit code hermes menandakan "sesi
#   selesai", bukan "tugas berhasil".
#
# Jadi penilaian di sini diambil dari LOG AUDIT, yang mencatat apa yang
# sebenarnya terjadi: berapa tool dipanggil, dan kesalahan apa yang tercatat.
#
#   LULUS  = ada pre_tool_call DAN tidak ada baris level=error
#   GAGAL  = tidak ada tool call (agent mati di awal), atau ada error
#
# Setiap task sengaja KECIL dan READ-ONLY. Tidak ada yang menyentuh wallet,
# login, atau mem-post apa pun. Tujuannya membuktikan tiap worker bisa:
# menyala, memakai model yang benar, memanggil tool, dan selesai — sebelum
# task sungguhan dijalankan.

set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=/dev/null
for m in "$ROOT"/lib/*.sh; do source "$m"; done
REPO_ROOT="$ROOT"

die()  { printf '\033[1;31m  ✗ %s\033[0m\n' "$*" >&2; exit 1; }
warn() { printf '\033[1;33m  ! %s\033[0m\n' "$*"; }
ok()   { printf '\033[1;32m  ✓ %s\033[0m\n' "$*"; }
step() { printf '\n\033[1;36m%s\033[0m\n' "$*"; }

ONLY=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --only) ONLY="${2:-}"; shift 2 ;;
    -h|--help)
      echo "Pakai: agentdrop test-workers [--only <profil>]"
      echo
      echo "Menjalankan satu task kecil read-only per worker, lalu menilai dari"
      echo "log audit (bukan exit code, yang selalu 0 walau task gagal)."
      exit 0 ;;
    *) die "opsi tidak dikenal: $1" ;;
  esac
done

command -v hermes >/dev/null 2>&1 || die "hermes tidak ada — jalankan ./install.sh"
[[ -d "$HERMES_HOME_DIR/profiles" ]] || die "belum ada profil — jalankan ./install.sh"

# ---------------------------------------------------------------------------
# Task per worker. Kecil, read-only, dan sesuai peran tiap worker.
# ---------------------------------------------------------------------------
# Peran diambil dari SOUL.md masing-masing; lihat AGENTS.md bagian TUJUAN.
task_for() {
  case "$1" in
    worker-analyzer)
      echo "Baca https://example.com lalu ringkas isinya dalam dua kalimat. Jangan menulis berkas apa pun." ;;
    worker-daily)
      echo "Laporkan tanggal dan waktu sekarang, lalu tulis satu baris catatan ke memory/lessons/worker-daily.md bahwa uji smoke berhasil." ;;
    worker-discord)
      echo "Buka https://discord.com dan laporkan judul halamannya. Jangan login dan jangan bergabung ke server mana pun." ;;
    worker-monitor)
      echo "Baca berkas di knowledge/chains/ dan laporkan isinya sebagai satu tabel. Jangan menulis berkas apa pun." ;;
    worker-onboard)
      echo "Buka https://example.com dan laporkan judul halamannya. Jangan mengisi form dan jangan menghubungkan wallet." ;;
    worker-orchestrator)
      echo "Sebutkan worker mana yang akan kamu delegasikan untuk tiga tugas ini: (a) register airdrop baru, (b) check-in harian, (c) mem-post di X. Jangan mengeksekusi atau mendelegasikan apa pun." ;;
    worker-quests)
      echo "Buka https://example.com dan laporkan judul halamannya. Jangan mengerjakan quest apa pun." ;;
    worker-x)
      echo "Buka https://example.com dan laporkan judul halamannya. Jangan mem-post, mem-follow, atau me-like apa pun." ;;
    *) echo "" ;;
  esac
}

# ---------------------------------------------------------------------------
# Baca log audit untuk menilai satu task
# ---------------------------------------------------------------------------
_log_dir() {
  # audit_log.py menentukan direktori log; pakai python agar tidak menebak.
  PYTHONPATH="$ROOT/tools" "$(_pyu)" - <<'PY' 2>/dev/null
import audit_log
print(audit_log.log_dir())
PY
}

# hitung_total — mencetak "<jumlah pre_tool_call> <jumlah error>" di SELURUH log.
#
# Sengaja memakai SELISIH jumlah baris, bukan memfilter berdasarkan waktu.
# Versi pertama memfilter `ts > sejak` dan itu salah dua kali: date(1) GNU
# tidak mendukung %f (pembandingnya jadi "%f" harfiah), dan walau timestampnya
# benar, resolusi milidetik terlalu kasar — dua task yang berurutan cepat bisa
# berbagi timestamp yang sama sehingga task kedua mewarisi hitungan task
# pertama. Selisih jumlah tidak bergantung pada presisi jam sama sekali.
hitung_total() {
  PYTHONPATH="$ROOT/tools" "$(_pyu)" - <<'PY' 2>/dev/null
import audit_log
pre = err = 0
for r in audit_log.read_all():
    if r.get("event") == "pre_tool_call":
        pre += 1
    if r.get("level") == "error":
        err += 1
print(pre, err)
PY
}


# ---------------------------------------------------------------------------
# Jalankan
# ---------------------------------------------------------------------------
PROFIL=$(cd "$HERMES_HOME_DIR/profiles" && ls -d */ 2>/dev/null | tr -d '/')
[[ -n "$PROFIL" ]] || die "tidak ada profil terpasang di $HERMES_HOME_DIR/profiles"

LDIR="$(_log_dir)"
[[ -n "$LDIR" ]] || warn "tidak bisa menentukan direktori log audit; penilaian akan dilewati"

step "[1/2] Model yang dipakai"
MODEL="$(_env_get AGENTDROP_MODEL 2>/dev/null || true)"
[[ -n "$MODEL" ]] && printf '  %-24s %s\n' "AGENTDROP_MODEL" "$MODEL" \
                  || warn "AGENTDROP_MODEL kosong — jalankan: agentdrop model"
printf '  %-24s %s\n' "AGENTDROP_PROVIDER" "$(_env_get AGENTDROP_PROVIDER 2>/dev/null || true)"

step "[2/2] Uji per worker"
printf '  Task kecil, read-only. Tidak menyentuh wallet, login, atau posting.\n'

LULUS=0; GAGAL=0; HASIL=()
for p in $PROFIL; do
  [[ -n "$ONLY" && "$p" != "$ONLY" ]] && continue
  T="$(task_for "$p")"
  if [[ -z "$T" ]]; then
    warn "$p: tidak punya task uji — dilewati"
    continue
  fi

  printf '\n\033[1;36m--- %s ---\033[0m\n' "$p"
  printf '  task: %s\n' "${T:0:90}…"
  SEBELUM="$(hitung_total)"
  PRE0="${SEBELUM%% *}"; ERR0="${SEBELUM##* }"
  PRE0="${PRE0:-0}"; ERR0="${ERR0:-0}"

  # rc sengaja TIDAK dipakai untuk menilai — hermes chat mengembalikan 0 walau
  # task gagal. Lihat komentar di kepala berkas.
  hermes --profile "$p" chat -q "$T" >/dev/null 2>&1
  RC=$?

  if [[ -n "$LDIR" ]]; then
    SESUDAH="$(hitung_total)"
    PRE1="${SESUDAH%% *}"; ERR1="${SESUDAH##* }"
    PRE1="${PRE1:-0}"; ERR1="${ERR1:-0}"
    PRE=$(( PRE1 - PRE0 ))
    ERR=$(( ERR1 - ERR0 ))
    [[ $PRE -lt 0 ]] && PRE=0
    [[ $ERR -lt 0 ]] && ERR=0
    if [[ "$PRE" -gt 0 && "$ERR" -eq 0 ]]; then
      ok "$p: $PRE tool call, tanpa error"
      LULUS=$((LULUS+1)); HASIL+=("$p|LULUS|$PRE tool call")
    elif [[ "$PRE" -eq 0 ]]; then
      printf '\033[1;31m  ✗ %s: tidak ada tool call — agent mati sebelum bertindak\033[0m\n' "$p"
      printf '     periksa: agentdrop audit errors\n'
      GAGAL=$((GAGAL+1)); HASIL+=("$p|GAGAL|0 tool call")
    else
      printf '\033[1;31m  ✗ %s: %s tool call tapi %s error tercatat\033[0m\n' "$p" "$PRE" "$ERR"
      printf '     periksa: agentdrop audit errors\n'
      GAGAL=$((GAGAL+1)); HASIL+=("$p|GAGAL|$ERR error")
    fi
  else
    # Tanpa log audit, satu-satunya sinyal adalah rc — dan itu tidak bisa
    # diandalkan. Katakan terus terang daripada berpura-pura menilai.
    if [[ $RC -eq 0 ]]; then
      warn "$p: selesai (rc=0), tapi TIDAK BISA dinilai tanpa log audit"
      HASIL+=("$p|TIDAK DINILAI|log audit tidak terbaca")
    else
      printf '\033[1;31m  ✗ %s: rc=%s\033[0m\n' "$p" "$RC"
      GAGAL=$((GAGAL+1)); HASIL+=("$p|GAGAL|rc=$RC")
    fi
  fi
done

step "Ringkasan"
for h in "${HASIL[@]}"; do
  IFS='|' read -r n s k <<< "$h"
  case "$s" in
    LULUS) printf '  \033[1;32m✓\033[0m %-22s %s\n' "$n" "$k" ;;
    GAGAL) printf '  \033[1;31m✗\033[0m %-22s %s\n' "$n" "$k" ;;
    *)     printf '  \033[1;33m?\033[0m %-22s %s\n' "$n" "$k" ;;
  esac
done
printf '\n  lulus %s, gagal %s\n' "$LULUS" "$GAGAL"

if [[ $GAGAL -gt 0 ]]; then
  printf '\n  Yang gagal hampir selalu soal model/provider, bukan browser.\n'
  printf '  Langkah: agentdrop model  —  lalu ulangi skrip ini.\n'
  exit 1
fi
printf '\n  Semua worker bisa menyala, memanggil tool, dan selesai.\n'
exit 0
