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

_ask() {  # _ask PROMPT VARNAME [default] — lewati kalau sudah terisi
  local prompt="$1" var="$2" def="${3:-}" cur=""
  cur="$(grep -E "^${var}=" "$ENV_FILE" 2>/dev/null | head -1 | cut -d= -f2-)"
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
  cur="$(grep -E "^${var}=" "$ENV_FILE" 2>/dev/null | head -1 | cut -d= -f2-)"
  [[ -n "$cur" ]] && { _ok "$var sudah terisi (dilewati)"; return 0; }
  [[ ! -t 0 ]] && { _warn "$var kosong dan stdin bukan terminal"; return 0; }
  local v
  read -r -s -p "  $prompt: " v; echo
  [[ -n "$v" ]] && { _env_set "$var" "$v"; _ok "$var diisi"; }
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

  # Salin .env ke setiap profil. Hermes membaca HERMES_HOME/.env dengan
  # override=True (hermes_cli/env_loader.py:470-504), dan --profile menyetel
  # HERMES_HOME — jadi tiap profil butuh salinannya sendiri.
  chmod 600 "$ENV_FILE"
  _ok "~/.hermes/.env (mode 600)"
}
