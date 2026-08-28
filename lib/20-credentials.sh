# lib/20-credentials.sh — tanya token & key, tulis ke tempat yang benar.
# Di-source oleh install.sh.

# ATURAN KERAS: private key TIDAK PERNAH masuk .env.
# Alasannya konkret: .env tersalin ke setiap profil Hermes, jadi satu key di
# sana berarti key itu ada di tujuh tempat. Key ditaruh di berkas tersendiri
# berizin 0600 yang sudah di-gitignore, dan .env hanya menyimpan PATH-nya.
_env_get() {  # _env_get KEY  — baca satu kunci dari $ENV_FILE (kosong kalau tidak ada)
  # Dipakai lib/30-hermes.sh untuk merender ${AGENTDROP_*} menjadi nilai konkret.
  # `|| true` wajib: tanpa itu, grep yang tidak menemukan apa pun membuat
  # pipeline gagal dan `set -euo pipefail` menjatuhkan seluruh install.
  local _k="$1"
  grep -E "^${_k}=" "$ENV_FILE" 2>/dev/null | head -1 | cut -d= -f2- || true
}

_env_set() {  # _env_set KEY VALUE  — tulis/ganti satu kunci di $ENV_FILE
  local k="$1" v="$2"
  if grep -qE "^${k}=" "$ENV_FILE" 2>/dev/null; then
    local esc=${v//&/\&}
    sed -i "s|^${k}=.*|${k}=${esc}|" "$ENV_FILE"
  else
    printf '%s=%s\n' "$k" "$v" >> "$ENV_FILE"
  fi
}

# CATATAN: `|| true` di dalam $( ) pada dua fungsi di bawah BUKAN hiasan.
#
# install.sh berjalan dengan `set -euo pipefail`. grep yang tidak menemukan apa
# pun keluar dengan 1; dengan pipefail status itu menular ke seluruh pipeline,
# lalu ke assignment-nya, lalu set -e mematikan seluruh installer TANPA pesan.
#
# Inilah sebabnya install berhenti tepat sesudah "==> Model": TELEGRAM_* sudah
# terisi di .env sehingga grep-nya cocok dan lolos, sedangkan OPENROUTER_API_KEY
# belum ada sehingga grep-nya gagal. Prompt kuncinya bahkan tidak sempat
# tercetak karena matinya di baris pertama fungsi, sebelum `read`.
#
# Tiga perbaikan sebelumnya meleset karena semuanya menyasar baris yang tidak
# pernah dieksekusi.
_ask() {  # _ask PROMPT VARNAME [default] — lewati kalau sudah terisi
  local prompt="$1" var="$2" def="${3:-}" cur=""
  cur="$(grep -E "^${var}=" "$ENV_FILE" 2>/dev/null | head -1 | cut -d= -f2- || true)"
  if [[ -n "$cur" ]]; then
    _ok "$var sudah terisi (dilewati)"
    return 0
  fi
  if [[ ! -t 0 ]]; then
    _warn "$var kosong dan stdin bukan terminal — isi manual di $ENV_FILE"
    return 0
  fi
  local v
  read -r -p "  $prompt${def:+ [$def]}: " v
  v="${v:-$def}"
  if [[ -n "$v" ]]; then _env_set "$var" "$v"; _ok "$var diisi"; fi
}

_ask_secret() {  # seperti _ask tapi tanpa echo
  local prompt="$1" var="$2" cur=""
  cur="$(grep -E "^${var}=" "$ENV_FILE" 2>/dev/null | head -1 | cut -d= -f2- || true)"
  [[ -n "$cur" ]] && { _ok "$var sudah terisi (dilewati)"; return 0; }
  [[ ! -t 0 ]] && { _warn "$var kosong dan stdin bukan terminal"; return 0; }
  local v
  read -r -s -p "  $prompt: " v; echo
  # if/then, BUKAN `[[ -n "$v" ]] && {...}`. Bentuk && mengembalikan status 1
  # kalau v kosong, dan karena ini baris TERAKHIR fungsi, fungsi ikut
  # mengembalikan 1 -- di bawah `set -euo pipefail` itu mematikan seluruh
  # install.sh tanpa pesan error apa pun.
  #
  # Ini yang membuat install operator berhenti tepat setelah "==> Model" dan
  # tidak pernah mencapai stage_setup, sehingga ~/.hermes/profiles/ kosong.
  # Prompt-nya sendiri menulis "atau kosongkan lalu isi di .env", jadi
  # mengosongkan adalah jalur yang sah dan tidak boleh mematikan pemasangan.
  if [[ -n "$v" ]]; then _env_set "$var" "$v"; _ok "$var diisi"; fi
  return 0
}

credentials_setup() {
  _log "Kredensial"
  mkdir -p "$HERMES_HOME_DIR"
  ENV_FILE="$HERMES_HOME_DIR/.env"
  [[ -f "$ENV_FILE" ]] || cp "$REPO_ROOT/.env.example" "$ENV_FILE"
  chmod 600 "$ENV_FILE"

  # ATURAN KERAS, diperiksa dulu sebelum apa pun.
  if grep -qE '^[A-Z_]*PRIVATE_KEY=.+' "$ENV_FILE"; then
    _err ".env berisi PRIVATE_KEY. Itu melanggar aturan keras:"
    _err "  .env tersalin ke setiap profil, jadi key akan ada di tujuh tempat."
    _die "Pindahkan ke AGENTDROP_KEY_FILE (berkas 0600) lalu ulangi."
  fi

  _log "Telegram (UI utama)"
  _ask "Bot token dari @BotFather" TELEGRAM_BOT_TOKEN
  _ask "Chat ID tujuan laporan"    TELEGRAM_HOME_CHANNEL

  _log "Model"
  # Satu kunci saja cukup; Hermes auto-detect provider dari kredensial.
  if grep -qE '^(OPENROUTER_API_KEY|ANTHROPIC_API_KEY|OPENAI_API_KEY|GOOGLE_API_KEY|GEMINI_API_KEY|NOUS_API_KEY)=.+' "$ENV_FILE"; then
    _ok "kunci model sudah ada"
  else
    _ask_secret "OpenRouter API key (atau kosongkan lalu isi di .env)" OPENROUTER_API_KEY
  fi

  credentials_ensure_model_vars
}

# Tiga variabel model yang dirujuk config.yaml. Dibuat sebagai fungsi terpisah
# supaya jalur interaktif DAN non-interaktif sama-sama menjalankannya — kalau
# hanya jalur interaktif yang menjamin, `./install.sh --non-interactive` pada
# .env yang lama akan menghasilkan config dengan ${AGENTDROP_MODEL} verbatim.
credentials_ensure_model_vars() {
  # Variabel model WAJIB ADA, dan ini bukan formalitas.
  #
  # config.yaml (utama + 7 profil) merujuk ${AGENTDROP_*}. Hermes meng-expand
  # ${VAR} (hermes_cli/config.py:2723) TAPI variabel yang tidak ada di
  # environment dibiarkan VERBATIM (config.py:2767: `return
  # os.environ.get(inner, raw)`). Tanpa penjaga, model.default jadi string
  # "${AGENTDROP_MODEL}" apa adanya dan SETIAP worker gagal dengan pesan yang
  # tidak menyebut penyebabnya.
  #
  # Di sinilah tempat operator menyetel provider-nya. Selama nilainya di .env,
  # `./install.sh` tidak bisa menghapusnya — installer menyalin config.yaml
  # dari repo tapi tidak pernah menyentuh .env.
  #
  # DUA TINGKAT: variabel per worker, jatuh ke variabel global. Fallback tidak
  # bisa ditulis di YAML karena Hermes tidak punya sintaks default untuk
  # ${VAR}; "${A:-$B}" akan menjadi string harfiah. Jadi fallback diselesaikan
  # DI SINI dan dituliskan ke .env sebagai nilai konkret.
  #
  # Hanya diisi kalau belum ada: nilai milik operator tidak pernah ditimpa.
  local _k _v _prof _kunci _glob _cur

  # 1) GLOBAL dulu — ini sumber fallback untuk setiap worker.
  for _k in MODEL PROVIDER BASE_URL MAX_TOKENS; do
    case "$_k" in
      MODEL)     _v="anthropic/claude-sonnet-4" ;;
      PROVIDER)  _v="openrouter" ;;
      BASE_URL)  _v="https://openrouter.ai/api/v1" ;;
      # Tanpa ini agent GAGAL di panggilan pertama pada akun ber-kredit
      # terbatas: ceiling native claude-sonnet-4 adalah 64.000
      # (agent/anthropic_adapter.py:175) dan OpenRouter menolaknya dengan
      # HTTP 402 "You requested up to 64000 tokens, but can only afford 2666".
      # Nilai config menang atas default model (agent/agent_init.py:2384).
      MAX_TOKENS) _v="8192" ;;
    esac
    if grep -qE "^AGENTDROP_${_k}=.+" "$ENV_FILE" 2>/dev/null; then
      _ok "AGENTDROP_${_k} sudah diset"
    else
      _env_set "AGENTDROP_${_k}" "$_v"
      _warn "AGENTDROP_${_k} belum ada — diisi default: $_v"
    fi
  done

  # 2) PER WORKER — mewarisi nilai global yang baru saja dijamin ada.
  for _prof in worker-analyzer worker-daily worker-discord worker-monitor \
               worker-onboard worker-orchestrator worker-quests worker-x; do
    _kunci="${_prof//-/_}"          # worker-x -> WORKER_X
    _kunci="${_kunci^^}"
    for _k in MODEL PROVIDER BASE_URL MAX_TOKENS; do
      _glob="AGENTDROP_${_k}"
      _cur="AGENTDROP_${_k}_${_kunci}"
      _v="$(grep -E "^${_glob}=" "$ENV_FILE" 2>/dev/null | head -1 | cut -d= -f2- || true)"
      if grep -qE "^${_cur}=.+" "$ENV_FILE" 2>/dev/null; then
        _ok "$_cur sudah diset"
      else
        _env_set "$_cur" "$_v"
        _ok "$_cur = $_v  (mengikuti global)"
      fi
    done
  done

  # Jebakan yang sudah benar-benar terjadi: operator mengisi CUSTOM_BASE_URL
  # karena .env.example lama menyuruh "Set model.base_url in config.yaml to the
  # same origin", lalu heran endpoint-nya tidak dipakai. Hermes memang membaca
  # CUSTOM_API_KEY (hermes_cli/models.py:4080) tapi TIDAK membaca
  # CUSTOM_BASE_URL — _get_custom_base_url() (models.py:2836-2839) mengambil
  # base_url dari model.base_url di config.yaml, yang sekarang merujuk
  # ${AGENTDROP_BASE_URL}. Jadi endpoint harus diisi ke AGENTDROP_BASE_URL.
  local _cb _ab
  _cb="$(grep -E "^CUSTOM_BASE_URL=.+" "$ENV_FILE" 2>/dev/null | head -1 | cut -d= -f2- || true)"
  _ab="$(grep -E "^AGENTDROP_BASE_URL=.+" "$ENV_FILE" 2>/dev/null | head -1 | cut -d= -f2- || true)"
  if [[ -n "$_cb" && "$_ab" == *"openrouter.ai"* ]]; then
    _warn "CUSTOM_BASE_URL=$_cb terisi, tapi AGENTDROP_BASE_URL masih $_ab"
    _warn "  Hermes TIDAK membaca CUSTOM_BASE_URL — hanya CUSTOM_API_KEY"
    _warn "  (models.py:4080). base_url diambil dari model.base_url di"
    _warn "  config.yaml (models.py:2836), yang merujuk AGENTDROP_BASE_URL."
    _warn "  Untuk memakai endpoint itu, setel di $ENV_FILE:"
    _warn "    AGENTDROP_PROVIDER=custom"
    _warn "    AGENTDROP_BASE_URL=$_cb"
    _warn "    AGENTDROP_MODEL=<id model dari endpoint itu>"
  fi

  _log "Model berbeda per worker: ubah AGENTDROP_*_<WORKER> di $ENV_FILE,"
  _log "  mis. AGENTDROP_MODEL_WORKER_QUESTS=anthropic/claude-opus-4"
}
