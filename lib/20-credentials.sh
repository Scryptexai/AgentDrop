# lib/20-credentials.sh — tanya token & key, tulis ke tempat yang benar.
# Di-source oleh install.sh.

# ATURAN KERAS: private key TIDAK PERNAH masuk .env.
# Alasannya konkret: .env tersalin ke setiap profil Hermes, jadi satu key di
# sana berarti key itu ada di tujuh tempat. Key ditaruh di berkas tersendiri
# berizin 0600 yang sudah di-gitignore, dan .env hanya menyimpan PATH-nya.
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
  # TIGA VARIABEL MODEL WAJIB ADA, dan ini bukan formalitas.
  #
  # config.yaml (utama + 7 profil) merujuk ${AGENTDROP_MODEL},
  # ${AGENTDROP_PROVIDER}, ${AGENTDROP_BASE_URL}. Hermes meng-expand ${VAR}
  # (hermes_cli/config.py:2723) TAPI variabel yang tidak ada di environment
  # dibiarkan VERBATIM (config.py:2767: `return os.environ.get(inner, raw)`).
  # Tanpa default, model.default jadi string "${AGENTDROP_MODEL}" apa adanya
  # dan SETIAP worker gagal dengan pesan yang tidak menyebut penyebabnya.
  #
  # Di sinilah tempat operator menyetel provider custom-nya. Selama nilainya
  # di .env, `./install.sh` tidak bisa menghapusnya — installer menyalin
  # config.yaml dari repo tapi tidak pernah menyentuh .env. Sebelumnya model
  # di-hardcode di config repo, jadi setiap install ulang membuang setelan
  # operator; itu sebabnya update tidak bisa di-pull.
  #
  # Hanya diisi kalau belum ada: nilai milik operator tidak pernah ditimpa.
  local _k _v
  for _k in AGENTDROP_MODEL AGENTDROP_PROVIDER AGENTDROP_BASE_URL; do
    case "$_k" in
      AGENTDROP_MODEL)    _v="anthropic/claude-sonnet-4" ;;
      AGENTDROP_PROVIDER) _v="openrouter" ;;
      AGENTDROP_BASE_URL) _v="https://openrouter.ai/api/v1" ;;
    esac
    if grep -qE "^${_k}=.+" "$ENV_FILE" 2>/dev/null; then
      _ok "$_k sudah diset"
    else
      _env_set "$_k" "$_v"
      _warn "$_k belum ada — diisi default: $_v"
      _warn "    ganti di $ENV_FILE kalau memakai provider custom"
    fi
  done

  _log "Wallet"
  # Wallet yang dipakai agent adalah MetaMask/OKX/Phantom yang Anda pasang
  # sendiri lewat ./agentdrop extensions. Berkas key di bawah hanya untuk
  # tooling CLI (cek saldo, pantau portofolio) — BUKAN untuk signing otomatis.
  KEYF="$STATE_DIR/wallet.key"
  if [[ -f "$KEYF" ]]; then
    _ok "key file sudah ada: $KEYF"
  elif [[ -t 0 ]]; then
    printf '  Private key untuk tooling (Enter = lewati): '
    read -r -s k; echo
    if [[ -n "$k" ]]; then
      umask 077; printf '%s\n' "$k" > "$KEYF"; chmod 600 "$KEYF"
      _ok "key ditulis ke $KEYF (izin 600)"
    fi
  fi
  [[ -f "$KEYF" ]] && _env_set AGENTDROP_KEY_FILE "$KEYF"

  # Kunci izinnya. Penyalinan ke tiap profil terjadi nanti di tahap setup
  # (lib/30-hermes.sh, `install -m 600 ... "$dst/.env"`), karena tiap profil
  # adalah HERMES_HOME terpisah dan --profile menyetel HERMES_HOME sebelum
  # env_loader membaca .env (override=True, hermes_cli/env_loader.py:470-504).
  chmod 600 "$ENV_FILE"
  _ok "~/.hermes/.env (mode 600)"
}
