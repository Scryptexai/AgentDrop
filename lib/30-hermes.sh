# lib/30-hermes.sh — config utama, profil, skill, dan hook audit.
# Di-source oleh install.sh.

PROFILES=(pekerja-koordinator pekerja-riset pekerja-harian pekerja-daftar
          pekerja-quest pekerja-discord pekerja-pantau pekerja-x)

# ---------------------------------------------------------------------------
# SKILLS di HERMES_HOME utama = HANYA milik koordinator.
#
# Dulu daftar ini memuat SEMUA 18 skill. Itu salah dua kali:
#
#   1. HERMES_HOME utama adalah profil DEFAULT, dan profil default-lah yang
#      memegang TELEGRAM_BOT_TOKEN (profiles.py:1105 "the default profile is
#      always served"). Jadi setiap kali Telegram berbicara, yang melihat 18
#      skill itu adalah koordinator -- padahal ia tidak mengeksekusi apa pun.
#   2. Manifest skill masuk ke system prompt setiap putaran. 18 nama + deskripsi
#      bukan biaya besar, tapi 18 PROSEDUR yang bisa diikuti adalah permukaan
#      kesalahan: koordinator bisa memutuskan mengikuti quest-executor sendiri.
#
# Jadi pool global dihapus. Setiap profil membawa skill-nya sendiri, dan
# HERMES_HOME utama membawa milik koordinator saja. `browser-burn-in` tetap di
# sini karena `agentdrop burn-in` menjalankannya dari home utama.
# ---------------------------------------------------------------------------
SKILLS=(airdrop-intake airdrop-analyzer self-improvement panggil-pekerja
        browser-burn-in
        riset harian quest daftar x discord pantau)

# Hermes tidak membatasi skill apa yang boleh dipanggil sebuah profil — apa pun
# yang ada di foldernya bisa dipakai. Tanpa pemetaan ini, pekerja-discord bisa
# memanggil daily-executor dan mengerjakan campaign yang bukan urusannya.
declare -A PROFILE_SKILLS=(
  # KOORDINATOR: tidak punya tool browser (lihat toolsets di config.yaml), jadi
  # browser-operation dan browser-burn-in TIDAK dipetakan ke sini. Memberinya
  # prosedur browser tanpa tool browser hanya menghasilkan halusinasi langkah.
  # panggil-pekerja hanya di sini: dialah yang menghadap Telegram.
  [pekerja-koordinator]="airdrop-intake airdrop-analyzer self-improvement panggil-pekerja riset harian quest daftar x discord pantau"
  # WORKER: masing-masing SATU skill prosedur + browser-operation + self-improvement.
  # browser-burn-in sengaja tidak dipetakan ke worker mana pun: itu alat uji
  # pemasangan (dijalankan `agentdrop burn-in` dari home utama), bukan prosedur
  # kerja harian. Membawanya ke tujuh worker hanya menambah prosedur yang bisa
  # diikuti di saat yang salah.
  [pekerja-riset]="browser-operation riset-executor airdrop-analyzer self-improvement"
  [pekerja-harian]="browser-operation daily-executor self-improvement"
  # onboard = register + connect wallet di SITUS PROYEK (bukan platform quest).
  # quest-executor tidak dipetakan ke sini: alurnya berbeda dan mencampurnya
  # membuat pekerja-daftar mengerjakan campaign yang bukan urusannya.
  [pekerja-daftar]="browser-operation onboard-executor airdrop-intake self-improvement"
  [pekerja-quest]="browser-operation quest-executor self-improvement"
  [pekerja-discord]="browser-operation discord-engager self-improvement"
  [pekerja-pantau]="browser-operation portfolio-tracker self-improvement"
  [pekerja-x]="browser-operation x-engager self-improvement"
)

_render_config() {  # _render_config SRC DST LABEL
  # Salin SRC ke DST sambil mengganti placeholder menjadi nilai konkret.
  # Alasan kedua kelompok placeholder ada di komentar pemanggil di bawah.
  local _src="$1" _dst="$2" _lbl="$3"
  local _tmp _nama _nilai
  _tmp="$(mktemp)"
  sed "s|__AGENTDROP_HOOK__|$STATE_DIR/agent-hooks/audit-log.py|g" "$_src" > "$_tmp"
  if grep -q "__AGENTDROP_HOOK__" "$_tmp"; then
    _warn "$_lbl: placeholder __AGENTDROP_HOOK__ belum terganti"
  fi

  # custom_providers hanya relevan kalau operator memakai endpoint custom.
  # Kalau tidak, bloknya dibuang — kalau dibiarkan, config berisi provider
  # hantu dengan base_url kosong dan Hermes bisa merutekan ke sana.
  local _prov
  _prov="$(_env_get AGENTDROP_PROVIDER)"
  if [[ "$_prov" != "custom" ]]; then
    # Hapus blok custom_providers (dari barisnya sampai baris top-level berikutnya).
    awk '
      /^custom_providers:/ { skip=1; next }
      skip && /^[^ \t#]/ { skip=0 }
      skip && /^#/ { next }
      !skip { print }
    ' "$_tmp" > "$_tmp.2" && mv "$_tmp.2" "$_tmp"
  else
    local _pn _am
    _pn="$(_env_get AGENTDROP_PROVIDER_NAME)"; [[ -n "$_pn" ]] || _pn="agentdrop-custom"
    _am="$(_env_get AGENTDROP_API_MODE)";     [[ -n "$_am" ]] || _am="auto"
    sed -i "s|__AGENTDROP_PROVIDER_NAME__|$_pn|g; s|__AGENTDROP_API_MODE__|$_am|g" "$_tmp"
  fi
  if grep -q "__AGENTDROP_PROVIDER_NAME__\|__AGENTDROP_API_MODE__" "$_tmp"; then
    _warn "$_lbl: placeholder custom_providers belum terganti"
  fi
  # Ganti setiap ${AGENTDROP_NAMA} dengan nilainya dari .env.
  for _nama in $(grep -oE '\$\{AGENTDROP_[A-Z0-9_]+\}' "$_tmp" \
                 | tr -d '${}' | sort -u); do
    _nilai="$(_env_get "$_nama")"
    if [[ -z "$_nilai" ]]; then
      _warn "$_lbl: $_nama kosong di .env — config akan berisi string kosong"
      continue
    fi
    # | sebagai pemisah sed karena nilai bisa berisi / (URL).
    sed -i "s|\${$_nama}|$_nilai|g" "$_tmp"
  done
  if grep -qE '\$\{AGENTDROP_[A-Z0-9_]+\}' "$_tmp"; then
    _warn "$_lbl: masih ada \${AGENTDROP_*} yang belum terganti"
  fi
  mv "$_tmp" "$_dst"
}

_render_all_configs() {  # render ulang config utama + semua profil dari .env
  # Dipanggil `agentdrop model` sesudah .env berubah, supaya operator tidak
  # harus menjalankan ./install.sh penuh hanya untuk mengganti provider.
  # Tanpa ini, .env berubah tapi config terpasang masih memegang nilai lama —
  # dan gejalanya persis yang sudah terjadi: provider disetel, worker tetap
  # memakai yang lama, tanpa pesan error apa pun.
  local _d _n
  if [[ -f "$REPO_ROOT/config/hermes/config.yaml" ]]; then
    _render_config "$REPO_ROOT/config/hermes/config.yaml" \
                   "$HERMES_HOME_DIR/config.yaml" "config utama"
  fi
  for _d in "$REPO_ROOT"/config/hermes/profiles/*/; do
    [[ -f "${_d}config.yaml" ]] || continue
    _n="$(basename "$_d")"
    mkdir -p "$HERMES_HOME_DIR/profiles/$_n"
    _render_config "${_d}config.yaml" \
                   "$HERMES_HOME_DIR/profiles/$_n/config.yaml" "$_n"
  done
}

hermes_install() {
  _log "Config utama"
  mkdir -p "$HERMES_HOME_DIR"
  # Config utama juga dirender, bukan disalin. Alasannya sama dengan profil:
  # jalur tampilan Hermes memakai read_user_config_raw() yang TIDAK
  # meng-expand ${VAR} (config.py:3366-3372), jadi menyalin mentah membuat
  # profil "default" tampil sebagai "${AGENTDROP_MODEL}" di dashboard.
  _render_config "$REPO_ROOT/config/hermes/config.yaml" \
                 "$HERMES_HOME_DIR/config.yaml" "config utama"
  [[ -f "$REPO_ROOT/config/hermes/SOUL.md" ]] && \
    cp "$REPO_ROOT/config/hermes/SOUL.md" "$HERMES_HOME_DIR/SOUL.md"
  _ok "~/.hermes/config.yaml"

  _log "Profil worker"
  for p in "${PROFILES[@]}"; do
    src="$REPO_ROOT/config/hermes/profiles/$p"
    dst="$HERMES_HOME_DIR/profiles/$p"
    [[ -d "$src" ]] || { _warn "profil $p tidak ada di repo, dilewati"; continue; }

    # memory/lessons/ WAJIB ada sebelum run pertama. Ketujuh SOUL.md menyuruh
    # agent membaca `memory/lessons/<profil>.md` sebelum mengerjakan task, dan
    # skill self-improvement menyuruh menulis ke sana. cwd agent adalah
    # HERMES_HOME profil itu, jadi path relatif tersebut menunjuk ke sini.
    # Kalau direktorinya tidak ada, langkah pertama setiap agent adalah membaca
    # berkas yang tidak pernah ada — dan memory loop yang jadi alasan K12
    # tidak pernah benar-benar berputar.
    mkdir -p "$dst/memories" "$dst/logs" "$dst/cron" "$dst/memory/lessons"
    # config.yaml dirender, bukan disalin mentah: placeholder
    # __AGENTDROP_HOOK__ diganti path ABSOLUT ke audit-log.py.
    #
    # Kenapa tidak pakai "~/.agentdrop/..." di repo:
    # agent/shell_hooks.py:555 memang memanggil os.path.expanduser(spec.command),
    # TAPI expanduser hanya meng-expand `~` di AWAL string. Command hook kita
    # berbentuk `python3 ~/.agentdrop/agent-hooks/audit-log.py` — `~` ada di
    # token KEDUA, jadi ia lolos apa adanya. Lalu split_command_line() memakai
    # shlex.split dan subprocess dipanggil dengan shell=False (baris 581), jadi
    # tidak ada shell yang meng-expand `~` itu. Python memperlakukannya sebagai
    # path RELATIF terhadap cwd agent, dan hasilnya:
    #
    #   /home/<user>/AgentDrop/~/.agentdrop/agent-hooks/audit-log.py
    #
    # Hook gagal -> SEMUA tool browser ikut gagal. Sudah terjadi di mesin
    # operator. Path absolut satu-satunya perbaikan yang benar; repo tidak bisa
    # hardcode /home/<user> karena config ini di-commit untuk semua orang.
    # config.yaml DIRENDER, bukan disalin mentah. Dua kelompok placeholder:
    #
    # 1. __AGENTDROP_HOOK__ -> path ABSOLUT ke audit-log.py.
    #    Kenapa tidak "~/.agentdrop/...": agent/shell_hooks.py:555 memang
    #    memanggil os.path.expanduser(spec.command), TAPI expanduser hanya
    #    meng-expand `~` di AWAL string. Command hook kita berbentuk
    #    `python3 ~/...` — `~` ada di token KEDUA, jadi lolos apa adanya.
    #    split_command_line() memakai shlex.split dan subprocess dipanggil
    #    dengan shell=False (baris 581), jadi tidak ada shell yang
    #    meng-expand-nya. Python memperlakukannya sebagai path RELATIF
    #    terhadap cwd agent. Sudah terjadi di mesin operator: hook gagal ->
    #    SEMUA tool browser ikut gagal.
    #
    # 2. ${AGENTDROP_*} -> nilai konkret dari .env.
    #    Hermes meng-expand ${VAR} di jalur RUNTIME (config.py:2723
    #    _expand_env_vars, dipakai load_config) — itu benar dan sudah diuji.
    #    TAPI jalur TAMPILAN memakai read_user_config_raw(), yang dokumen
    #    Hermes sendiri nyatakan TIDAK melakukan ekspansi:
    #
    #      "No DEFAULT_CONFIG merge, no managed-scope overlay, no
    #       ${ENV_VAR} expansion"      (config.py:3366-3372)
    #
    #    profiles.py:756 _read_config_model() memakainya, jadi `hermes profile
    #    list` dan dashboard menampilkan string "${AGENTDROP_MODEL_PEKERJA_X}"
    #    apa adanya. doctor.py juga memakai read_user_config_raw di beberapa
    #    tempat (1507, 1747, 1795, 3217). Menambal semua jalur tampilan itu
    #    berarti mengubah kode Hermes — bukan bagian kita.
    #
    #    Jadi nilainya dirender DI SINI, dari .env, saat install. Runtime dan
    #    tampilan jadi sama-sama benar, dan config terpasang tetap bisa dibaca
    #    manusia tanpa harus membuka .env.
    # ---------------------------------------------------------------------
    # TOLAK SKILL BAWAAN HERMES MASUK KE PROFIL INI.
    #
    # Hermes mengirim 58 skill bawaan (13 kategori di hermes-agent/skills/).
    # sync_skills() menyuntikkannya ke HERMES_HOME saat install, saat
    # `hermes update`, dan saat sync langsung. Tanpa penolakan, profil worker
    # yang tadinya hanya membawa 3 skill tiba-tiba membawa 61 -- dan manifest
    # skill masuk ke system prompt setiap putaran.
    #
    # Mekanismenya resmi, bukan akal-akalan: berkas penanda
    # `.no-bundled-skills` di root profil membuat sync_skills() hanya men-seed
    # ESSENTIAL_SKILLS (agent/skill_utils.py:443 = {"hermes-agent"}).
    # Lihat tools/skills_sync.py:99-105 dan :728, serta
    # hermes_cli/profiles.py:145-158 dan :1337-1343.
    #
    # Dibuat SETIAP install, bukan sekali: operator bisa menghapusnya, dan
    # `hermes update` berikutnya akan menyuntikkan 58 skill lagi.
    # ---------------------------------------------------------------------
    printf '%s\n' \
      "Profil ini menolak penyemaian skill bawaan Hermes." \
      "Dibuat oleh install.sh AgentDrop." \
      > "$dst/.no-bundled-skills"

    _render_config "$src/config.yaml" "$dst/config.yaml" "$p"
    [[ -f "$src/SOUL.md" ]] && cp "$src/SOUL.md" "$dst/SOUL.md"

    # Tiap profil adalah HERMES_HOME terpisah, jadi butuh .env sendiri:
    # --profile menyetel HERMES_HOME sebelum env_loader membaca .env.
    if [[ -f "$HERMES_HOME_DIR/.env" ]]; then
      install -m 600 "$HERMES_HOME_DIR/.env" "$dst/.env"
    fi

    # Skill dibersihkan lebih dulu. Kalau sebuah skill dikeluarkan dari
    # pemetaan, menjalankan ulang installer harus benar-benar mencabutnya —
    # tanpa ini pembatasan hanya berlaku pada pemasangan pertama.
    rm -rf "$dst/skills"; mkdir -p "$dst/skills"
    local dipasang=()
    for s in ${PROFILE_SKILLS[$p]:-}; do
      if [[ -d "$REPO_ROOT/skills/$s" ]]; then
        mkdir -p "$dst/skills/$s"
        cp -r "$REPO_ROOT/skills/$s/." "$dst/skills/$s/"
        dipasang+=("$s")
      else
        _warn "skill '$s' dipetakan ke $p tapi tidak ada di repo"
      fi
    done
    [[ ${#dipasang[@]} -gt 0 ]] || _warn "profil $p tidak mendapat skill"
    _ok "$p — ${#dipasang[@]} skill"
  done

  # Penolakan yang sama untuk home utama. Home utama adalah profil DEFAULT, dan
  # profil default-lah yang memegang TELEGRAM_BOT_TOKEN (profiles.py:1105) --
  # jadi justru di sinilah 58 skill bawaan paling mahal harganya.
  printf '%s\n' \
    "Home utama ini menolak penyemaian skill bawaan Hermes." \
    "Dibuat oleh install.sh AgentDrop." \
    > "$HERMES_HOME_DIR/.no-bundled-skills"

  _log "Skill di HERMES_HOME utama"
  rm -rf "$HERMES_HOME_DIR/skills"; mkdir -p "$HERMES_HOME_DIR/skills"
  for s in "${SKILLS[@]}"; do
    [[ -d "$REPO_ROOT/skills/$s" ]] || continue
    mkdir -p "$HERMES_HOME_DIR/skills/$s"
    cp -r "$REPO_ROOT/skills/$s/." "$HERMES_HOME_DIR/skills/$s/"
  done
  _ok "${#SKILLS[@]} skill"

  hermes_install_hooks
  hermes_install_memory
}

hermes_install_hooks() {
  _log "Hook log audit"
  # Dua sistem hook Hermes, dua lokasi berbeda:
  #   shell hook   -> dipanggil dari blok `hooks:` di config.yaml
  #   gateway hook -> dipindai dari ~/.hermes/hooks/<nama>/{HOOK.yaml,handler.py}
  # Keduanya butuh tools/audit_log.py DI SEBELAH mereka, karena hook berjalan
  # dari lokasi instal, bukan dari repo.
  mkdir -p "$STATE_DIR/agent-hooks" "$LOG_DIR"
  cp "$REPO_ROOT/agent-hooks/audit-log.py" "$STATE_DIR/agent-hooks/"
  cp "$REPO_ROOT/tools/audit_log.py"       "$STATE_DIR/agent-hooks/"
  chmod +x "$STATE_DIR/agent-hooks/audit-log.py"
  _ok "~/.agentdrop/agent-hooks (sisi tool: pre/post_tool_call, subagent_*)"

  mkdir -p "$HERMES_HOME_DIR/hooks/agentdrop-audit"
  cp "$REPO_ROOT/hooks/agentdrop-audit/HOOK.yaml"  "$HERMES_HOME_DIR/hooks/agentdrop-audit/"
  cp "$REPO_ROOT/hooks/agentdrop-audit/handler.py" "$HERMES_HOME_DIR/hooks/agentdrop-audit/"
  cp "$REPO_ROOT/tools/audit_log.py"               "$HERMES_HOME_DIR/hooks/agentdrop-audit/"
  _ok "~/.hermes/hooks/agentdrop-audit (sisi agent: agent:start/step/end)"
}

hermes_install_memory() {
  _log "Memory lessons"
  mkdir -p "$STATE_DIR/memory/lessons"
  # README-nya disalin supaya protokolnya terbaca di lokasi kerja, bukan hanya
  # di repo yang mungkin sudah dipindah atau dihapus sesudah install.
  [[ -f "$REPO_ROOT/memory/lessons/README.md" ]] && \
    cp "$REPO_ROOT/memory/lessons/README.md" "$STATE_DIR/memory/lessons/README.md"
  # Berkas per profil dibuat kosong lebih dulu. Tanpa ini agent harus menebak
  # apakah "berkas tidak ada" berarti "belum ada pelajaran" atau "salah path".
  local p n=0
  for p in "${PROFILES[@]}"; do
    [[ -f "$STATE_DIR/memory/lessons/$p.md" ]] && continue
    : > "$STATE_DIR/memory/lessons/$p.md"; n=$((n+1))
  done
  _ok "$STATE_DIR/memory/lessons/ (append-only, per profil, $n berkas baru)"
}
