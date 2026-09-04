# lib/60-latih.sh — melatih tiap worker satu per satu.
#
# KENAPA ADA DI SINI, BUKAN HANYA DI DALAM REPL
# Arc 36 menaruh /latih di python/agentdrop_repl.py. Masalahnya: REPL itu
# berjalan di atas jembatan yang mengimpor run_agent langsung, dan jembatan itu
# belum pernah diuji terhadap Hermes sungguhan. Jadi perintah latih ada di kode
# tapi tidak bisa dijalankan operator -- "train belum terimplementasi".
#
# Berkas ini memakai jalur yang SUDAH TERBUKTI jalan: `hermes --profile <worker>
# chat -q "..."`, sama persis dengan yang dipakai `agentdrop run` dan yang
# membuat pekerja-x berhasil posting ke X. Tidak ada dependensi baru.
#
# DUA HAL YANG TIDAK BOLEH HILANG
# 1. Prompt pelatihan diambil dari build_learn_prompt() milik Hermes kalau
#    tersedia, supaya hasilnya identik dengan `hermes /learn`. Kalau tidak
#    tersedia, dipakai prompt bawaan dan operator DIBERITAHU.
# 2. Pelatihan dinilai dari skill yang benar-benar tersimpan, bukan dari
#    exit code dan bukan dari jawaban yang terdengar meyakinkan. Agent bisa
#    membalas panjang tanpa memanggil skill_manage sama sekali.

# Direktori skill milik satu worker. Skill itu per-profil, jadi hasil pelatihan
# worker A tidak pernah bocor ke worker B.
latih_dir_skill() {  # latih_dir_skill <worker>
  echo "$HERMES_HOME_DIR/profiles/$1/skills"
}

# Nama skill yang benar-benar ada (punya SKILL.md), satu per baris.
latih_skill_terpasang() {  # latih_skill_terpasang <worker>
  local d; d="$(latih_dir_skill "$1")"
  [[ -d "$d" ]] || return 0
  local s
  for s in "$d"/*/; do
    [[ -f "${s}SKILL.md" ]] && basename "${s%/}"
  done
}

latih_daftar() {
  local d w n
  _log "Worker yang bisa dilatih"
  printf '  %-22s %6s  %s\n' "WORKER" "SKILL" "DIREKTORI"
  printf '  %s\n' "--------------------------------------------------------------"
  for d in "$HERMES_HOME_DIR"/profiles/*/; do
    [[ -f "${d}config.yaml" ]] || continue
    w="$(basename "${d%/}")"
    n="$(latih_skill_terpasang "$w" | grep -ac . || true)"; n="${n:-0}"
    printf '  %-22s %6s  %s\n' "$w" "$n" "$(latih_dir_skill "$w")"
  done
  echo
  _warn "Latih satu worker:  agentdrop latih <worker> \"<materi>\""
}

# Susun prompt pelatihan. Mengutamakan mesin /learn milik Hermes sendiri.
latih_prompt() {  # latih_prompt <materi>  -> stdout: prompt
  local materi="$1" py keluar
  py="$(python_hermes 2>/dev/null || true)"
  if [[ -n "$py" ]]; then
    keluar="$("$py" - "$materi" <<'PY' 2>/dev/null
import sys
try:
    from agent.learn_prompt import build_learn_prompt
except Exception:
    sys.exit(3)
sys.stdout.write(build_learn_prompt(sys.argv[1]))
PY
)" && [[ -n "$keluar" ]] && { printf '%s' "$keluar"; return 0; }
    # Hermes terpasang tapi build_learn_prompt tidak ada -> pakai bawaan,
    # dan beri tahu operator supaya tidak mengira ini prompt Hermes.
    _warn "build_learn_prompt tidak tersedia di Hermes terpasang — pakai prompt bawaan AgentDrop." >&2
  fi
  cat <<EOF
[/learn] Saya sedang melatih Anda. Simpan ini sebagai skill yang bisa dipakai ulang.

MATERI YANG SAYA AJARKAN:
$materi

Lakukan ini:
1. Pahami materinya. Kalau saya menyebut URL, direktori, atau "yang barusan kita
   lakukan", kumpulkan dulu sumber itu dengan tool yang Anda punya.
2. Tulis skill baru lewat skill_manage (action=create) di direktori skill ANDA
   SENDIRI. Namai dengan bahasa Indonesia, ringkas, dan spesifik untuk pekerjaan
   Anda — jangan membuat skill yang menjadi tugas worker lain.
3. Isi SKILL.md dengan prosedur yang bisa diikuti ulang, bukan ringkasan umum.
   Sertakan cara memverifikasi hasilnya, karena kegagalan yang terlihat seperti
   keberhasilan lebih berbahaya daripada kegagalan yang jelas.
4. Sesudah tersimpan, sebutkan nama skill yang Anda buat.

Jangan hanya menjawab. Kalau tidak ada skill yang tersimpan, pelatihan ini
gagal walau jawaban Anda terdengar bagus.
EOF
}

cmd_latih() {  # cmd_latih [--list] <worker> "<materi>"
  if [[ "${1:-}" == "--list" || "${1:-}" == "-l" ]]; then latih_daftar; return 0; fi
  if [[ -z "${1:-}" ]]; then latih_daftar; return 0; fi

  local worker="$1"; shift
  if [[ -z "${1:-}" ]]; then
    _err "butuh materi. Contoh:"
    echo "    agentdrop latih $worker \"gaya menulis thread crypto yang tidak terdengar seperti bot\""
    return 1
  fi
  local materi="$*"

  local d; d="$HERMES_HOME_DIR/profiles/$worker"
  if [[ ! -f "$d/config.yaml" ]]; then
    _err "worker '$worker' tidak ada di $HERMES_HOME_DIR/profiles"
    latih_daftar
    return 1
  fi
  command -v hermes >/dev/null 2>&1 || _die "hermes tidak ada — jalankan ./install.sh"

  local sebelum sesudah prompt rc pra0 err0 pra1 err1
  sebelum="$(latih_skill_terpasang "$worker" | sort)"
  read -r pra0 err0 <<< "$(_audit_counts)"

  prompt="$(latih_prompt "$materi")"

  _log "Melatih $worker"
  echo "  materi : ${materi:0:120}"
  echo "  skill  : $(latih_dir_skill "$worker")"
  echo

  # Jalur yang terbukti jalan. HERMES_HOME diarahkan ke profil worker ini supaya
  # SOUL.md dan skill-nya yang terbaca, bukan milik profil default.
  HERMES_HOME="$d" hermes --profile "$worker" chat -q "$prompt"
  rc=$?

  read -r pra1 err1 <<< "$(_audit_counts)"
  sesudah="$(latih_skill_terpasang "$worker" | sort)"

  echo
  echo "──────────────────────────────────────────────────────────────"
  # Selisih dihitung dengan loop, bukan `comm`: comm menuntut kedua masukan
  # terurut dan gagal senyap kalau salah satunya kosong.
  local baru="" s
  while IFS= read -r s; do
    [[ -z "$s" ]] && continue
    printf '%s\n' "$sebelum" | grep -aqxF "$s" || baru="${baru}${baru:+, }$s"
  done <<< "$sesudah"

  local dpra=$((pra1 - pra0)) derr=$((err1 - err0))
  echo "  worker      : $worker"
  echo "  exit code   : $rc   (TIDAK dipakai sebagai penilaian)"
  echo "  tool call   : $dpra"
  echo "  baris error : $derr"

  local gagal=0
  if [[ "$dpra" -eq 0 ]]; then
    _err "tidak ada satu pun tool terpanggil — task tidak dikerjakan."
    _warn "Periksa endpoint & API key:  agentdrop model --show"
    gagal=1
  fi
  if [[ "$derr" -gt 0 ]]; then
    _err "ada $derr baris error di log audit — lihat: agentdrop audit errors"
    gagal=1
  fi

  if [[ -n "$baru" ]]; then
    _ok "skill baru tersimpan: $baru"
    echo "  lokasi: $(latih_dir_skill "$worker")"
  else
    # Ini kasus yang paling menipu: agent membalas panjang dan meyakinkan,
    # exit code 0, tool terpanggil -- tapi tidak ada skill yang tersimpan.
    _warn "TIDAK ADA skill baru yang tersimpan."
    _warn "Agent mungkin hanya menjawab tanpa memanggil skill_manage."
    _warn "Coba lagi dengan materi lebih spesifik, atau periksa apakah worker"
    _warn "ini punya toolset 'skills':  grep toolsets $d/config.yaml"
    gagal=1
  fi
  echo "──────────────────────────────────────────────────────────────"
  return $gagal
}
