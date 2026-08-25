#!/usr/bin/env bash
# ============================================================================
# start-browser.sh — build (bila perlu) dan nyalakan Camofox browser
# ============================================================================
# Camofox = "stealth headless browser for AI agents" berbasis Camoufox
# (Firefox). Repo: https://github.com/jo-inc/camofox-browser
#
# PENTING — kenapa skrip ini memakai `make`, bukan `docker build`:
# README camofox-browser memberi peringatan eksplisit:
#   "Do not run `docker build` directly. The Dockerfile uses bind mounts to
#    pull pre-downloaded binaries from dist/. Always use `make up`
#    (or `make fetch` then `make build`)."
#
# Skrip ini menghormati itu: build lewat `make fetch && make build`, lalu
# jalankan lewat `docker compose up -d` memakai image yang sudah jadi.
# ============================================================================
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CAMOFOX_SRC="${CAMOFOX_SRC:-$HOME/.camofox-src}"
CAMOFOX_REPO="https://github.com/jo-inc/camofox-browser.git"

log()  { printf '\033[1;34m==>\033[0m %s\n' "$*"; }
ok()   { printf '\033[1;32m  ✓\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m  !\033[0m %s\n' "$*"; }
die()  { printf '\033[1;31m  ✗ %s\033[0m\n' "$*" >&2; exit 1; }

# Muat .env kalau ada (CAMOFOX_VERSION, CAMOFOX_ARCH, CAMOFOX_PORT, ...)
if [[ -f "$REPO_ROOT/.env" ]]; then
  set -a; # shellcheck disable=SC1091
  source "$REPO_ROOT/.env"; set +a
fi

VERSION="${CAMOFOX_VERSION:-135.0.1}"

# Deteksi arsitektur dengan logika yang sama seperti Makefile upstream:
#   arm64 (macOS) -> aarch64, selain itu pakai uname -m apa adanya.
uname_arch="$(uname -m)"
if [[ "$uname_arch" == "arm64" ]]; then
  DETECTED_ARCH="aarch64"
else
  DETECTED_ARCH="$uname_arch"
fi
ARCH="${CAMOFOX_ARCH:-$DETECTED_ARCH}"
IMAGE="camofox-browser:${VERSION}-${ARCH}"

# ----------------------------------------------------------------------------
# 1. Prasyarat
# ----------------------------------------------------------------------------
log "Memeriksa prasyarat"
command -v docker >/dev/null 2>&1 || die "docker belum terinstal."
docker info >/dev/null 2>&1 || die "Docker daemon tidak berjalan. Start Docker dulu."
command -v git >/dev/null 2>&1 || die "git belum terinstal."
ok "docker + git tersedia"

# docker compose v2 (plugin) atau docker-compose v1 (binary)
if docker compose version >/dev/null 2>&1; then
  COMPOSE=(docker compose)
elif command -v docker-compose >/dev/null 2>&1; then
  COMPOSE=(docker-compose)
else
  die "Butuh 'docker compose' (v2) atau 'docker-compose' (v1)."
fi
ok "compose: ${COMPOSE[*]}"

# ----------------------------------------------------------------------------
# 2. Source Camofox
# ----------------------------------------------------------------------------
if [[ ! -d "$CAMOFOX_SRC/.git" ]]; then
  log "Clone camofox-browser ke $CAMOFOX_SRC"
  git clone --depth 1 "$CAMOFOX_REPO" "$CAMOFOX_SRC"
else
  log "Source Camofox sudah ada di $CAMOFOX_SRC"
fi

# ----------------------------------------------------------------------------
# 3. Build image kalau belum ada
# ----------------------------------------------------------------------------
if docker image inspect "$IMAGE" >/dev/null 2>&1; then
  ok "image $IMAGE sudah ada"
else
  log "Build image $IMAGE (ini mengunduh Camoufox + yt-dlp dulu, ~beberapa menit)"
  # `make fetch` mengunduh binari ke dist/ — WAJIB sebelum build, karena
  # Dockerfile memakai bind mount dari dist/.
  make -C "$CAMOFOX_SRC" fetch ARCH="$ARCH" VERSION="$VERSION"
  make -C "$CAMOFOX_SRC" build ARCH="$ARCH" VERSION="$VERSION"
  ok "image $IMAGE selesai dibuild"
fi

# ----------------------------------------------------------------------------
# 4. Jalankan via compose
# ----------------------------------------------------------------------------
log "Menyalakan Camofox via docker compose"
# Ekspor variabel yang dibutuhkan docker-compose.yml
export CAMOFOX_VERSION="$VERSION"
export CAMOFOX_ARCH="$ARCH"
export ENABLE_VNC="${ENABLE_VNC:-1}"
export NOVNC_PORT="${NOVNC_PORT:-6080}"
"${COMPOSE[@]}" -f "$REPO_ROOT/docker-compose.yml" up -d

# ----------------------------------------------------------------------------
# 5. Tunggu sehat
# ----------------------------------------------------------------------------
PORT="${CAMOFOX_PORT:-9377}"
log "Menunggu Camofox sehat di port $PORT ..."
healthy=0
for i in $(seq 1 30); do
  if curl -fsS "http://127.0.0.1:${PORT}/health" >/dev/null 2>&1; then
    healthy=1
    break
  fi
  sleep 2
done

if [[ "$healthy" -eq 1 ]]; then
  ok "Camofox sehat: http://127.0.0.1:${PORT}"
else
  warn "Camofox belum merespons /health setelah 60 detik."
  echo "  Periksa: ${COMPOSE[*]} -f $REPO_ROOT/docker-compose.yml logs --tail=50"
  exit 1
fi

# ----------------------------------------------------------------------------
# 6. GUI browser (noVNC)
# ----------------------------------------------------------------------------
if [[ "${ENABLE_VNC:-1}" == "1" ]]; then
  NOVNC="${NOVNC_PORT:-6080}"
  log "Memeriksa GUI browser (noVNC) di port $NOVNC ..."
  gui=0
  for i in $(seq 1 20); do
    if curl -fsS -o /dev/null "http://127.0.0.1:${NOVNC}/vnc.html" 2>/dev/null; then
      gui=1
      break
    fi
    sleep 2
  done

  echo
  if [[ "$gui" -eq 1 ]]; then
    ok "GUI browser siap: http://localhost:${NOVNC}/vnc.html"
  else
    warn "noVNC belum merespons di port $NOVNC."
    echo "  Plugin vnc butuh Xvfb+x11vnc+noVNC di dalam image. Cek:"
    echo "    ${COMPOSE[*]} -f $REPO_ROOT/docker-compose.yml logs camofox | grep -i vnc"
  fi
else
  warn "ENABLE_VNC bukan 1 — browser berjalan HEADLESS. Airdrop farming butuh GUI."
fi

echo
echo "Langkah berikutnya:"
echo "  1. Pastikan .env berisi:  CAMOFOX_URL=http://localhost:${PORT}"
echo "  2. Login VISUAL sekali per platform (agent tidak boleh mengerjakan ini):"
echo "       ./scripts/takeover.sh worker-daily https://app.galxe.com/login"
echo "  3. Uji agent:"
echo "       hermes --profile worker-daily chat -q \"Buka https://example.com dan screenshot\""
