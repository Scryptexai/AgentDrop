# lib/30-hermes.sh — config utama, profil, skill, dan hook audit.
# Di-source oleh install.sh.

PROFILES=(worker-orchestrator worker-analyzer worker-daily worker-quests
          worker-discord worker-monitor worker-x)

SKILLS=(browser-operation browser-burn-in airdrop-intake airdrop-analyzer
        daily-executor quest-executor discord-engager portfolio-tracker
        x-engager self-improvement)

# Hermes tidak membatasi skill apa yang boleh dipanggil sebuah profil — apa pun
# yang ada di foldernya bisa dipakai. Tanpa pemetaan ini, worker-discord bisa
# memanggil daily-executor dan mengerjakan campaign yang bukan urusannya.
declare -A PROFILE_SKILLS=(
  [worker-orchestrator]="browser-operation browser-burn-in airdrop-intake airdrop-analyzer self-improvement"
  [worker-analyzer]="browser-operation browser-burn-in airdrop-analyzer self-improvement"
  [worker-daily]="browser-operation browser-burn-in daily-executor self-improvement"
  [worker-quests]="browser-operation browser-burn-in quest-executor self-improvement"
  [worker-discord]="browser-operation browser-burn-in discord-engager self-improvement"
  [worker-monitor]="browser-operation browser-burn-in portfolio-tracker self-improvement"
  [worker-x]="browser-operation browser-burn-in x-engager self-improvement"
)

hermes_install() {
  _log "Config utama"
  mkdir -p "$HERMES_HOME_DIR"
  cp "$REPO_ROOT/config/hermes/config.yaml" "$HERMES_HOME_DIR/config.yaml"
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
    cp "$src/config.yaml" "$dst/config.yaml"
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
