#!/usr/bin/env bash
# Install the vision-first AgentDrop configuration into ~/.hermes/
# Merge-safe: existing files are preserved unless --force is given.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEST="${HERMES_HOME:-$HOME/.hermes}"
FORCE=0
[[ "${1:-}" == "--force" ]] && FORCE=1

echo "[agentdrop] installing hermes config -> $DEST"

copy() {
  local rel="$1"
  local src="$HERE/$rel"
  local out="$DEST/$rel"
  mkdir -p "$(dirname "$out")"
  if [[ -e "$out" && $FORCE -eq 0 ]]; then
    echo "  skip (exists): $rel"
  else
    cp "$src" "$out"
    echo "  install: $rel"
  fi
}

copy hermes.yaml
for f in $(cd "$HERE" && find profiles skills memory security -type f); do
  copy "$f"
done

# Point the engine at the installed profile config
mkdir -p "$DEST"
cat > "$DEST/agentdrop.env" <<EOF
# written by agentdrop hermes-config/install.sh
export AGENTDROP_WORKER_CONFIG="$DEST/profiles/workers/worker-quests/config.yaml"
export AGENTDROP_PROFILE_REGISTRY="$(cd "$HERE/.." && pwd)/data/profile_registry.json"
EOF
echo "[agentdrop] done. Next: source $DEST/agentdrop.env"
