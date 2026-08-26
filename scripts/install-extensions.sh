#!/usr/bin/env bash
# ============================================================================
# install-extensions.sh — unduh & ekstrak ekstensi ke extensions/installed/
# ============================================================================
# Manifest: config/extensions.yaml
#
# Chrome for Testing memuat ekstensi dari DIREKTORI yang berisi manifest.json,
# lewat --load-extension. Jadi CRX dari Chrome Web Store harus diekstrak dulu.
#
# Pemakaian:
#   ./scripts/install-extensions.sh              # hanya yang required: true
#   ./scripts/install-extensions.sh --all        # semua entri manifest
#   ./scripts/install-extensions.sh --only metamask,phantom
#   ./scripts/install-extensions.sh --list       # tampilkan manifest + status
#
# CATATAN KEAMANAN
#   Skrip ini mengunduh kode pihak ketiga ke dalam browser yang memegang
#   private key Anda. Ia TIDAK menjalankan apa pun, hanya mengekstrak.
#   Cocokkan `id` di config/extensions.yaml dengan halaman Chrome Web Store
#   resmi proyeknya sebelum menjalankan --all.
# ============================================================================
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MANIFEST="$REPO_ROOT/config/extensions.yaml"
DEST="$REPO_ROOT/extensions/installed"
# Versi Chrome dipakai hanya untuk memenuhi parameter endpoint; Chrome Web
# Store menerima rentang yang luas.
PROD_VERSION="${CHROME_PROD_VERSION:-131.0.0.0}"

die()  { printf '\033[1;31m  ✗ %s\033[0m\n' "$*" >&2; exit 1; }
warn() { printf '\033[1;33m  ! %s\033[0m\n' "$*"; }
ok()   { printf '\033[1;32m  ✓ %s\033[0m\n' "$*"; }
log()  { printf '\033[1;34m==> %s\033[0m\n' "$*"; }

[[ -f "$MANIFEST" ]] || die "manifest tidak ada: $MANIFEST"
command -v python3 >/dev/null 2>&1 || die "butuh python3"
command -v curl >/dev/null 2>&1 || die "butuh curl"
python3 -c 'import yaml' 2>/dev/null \
  || die "butuh PyYAML. Pasang: pip install pyyaml (atau pakai venv proyek)"

mkdir -p "$DEST"

# ----------------------------------------------------------------------------
# Ekstraktor CRX. CRX3 = "Cr24" + versi(4) + panjang header(4) + header + ZIP.
# Jadi ZIP dimulai di offset 8 + header_size. unzip biasa sering gagal karena
# header itu, jadi kita potong lebih dulu.
# ----------------------------------------------------------------------------
extract_crx() {
  python3 - "$1" "$2" <<'PY'
import struct, sys, zipfile, io, os, json
src, dst = sys.argv[1], sys.argv[2]
raw = open(src, 'rb').read()
if raw[:4] == b'Cr24':
    hsize = struct.unpack('<I', raw[8:12])[0]
    blob = raw[12 + hsize:]
else:
    blob = raw  # mungkin memang zip polos
try:
    zf = zipfile.ZipFile(io.BytesIO(blob))
except Exception as e:
    print(f"BUKAN_ZIP: {e}"); sys.exit(1)
os.makedirs(dst, exist_ok=True)
zf.extractall(dst)
mf = os.path.join(dst, 'manifest.json')
if not os.path.exists(mf):
    print("TANPA_MANIFEST"); sys.exit(1)
m = json.load(open(mf))
print(f"OK\t{m.get('name','?')}\t{m.get('version','?')}\tMV{m.get('manifest_version','?')}")
PY
}

list_manifest() {
  python3 - "$MANIFEST" "$DEST" <<'PY'
import yaml, sys, os
m = yaml.safe_load(open(sys.argv[1])) or {}
dest = sys.argv[2]
print(f"{'NAMA':<12} {'WAJIB':<6} {'KATEGORI':<14} {'STATUS':<12} LABEL")
print('-' * 78)
for e in (m.get('extensions') or []) + (m.get('extra') or []):
    folder = os.path.join(dest, e['folder'])
    ada = 'terpasang' if os.path.exists(os.path.join(folder, 'manifest.json')) else 'BELUM'
    print(f"{e['name']:<12} {('ya' if e.get('required') else '-'):<6} "
          f"{e.get('category','-'):<14} {ada:<12} {e.get('label','')}")
PY
}

install_one() {
  local name="$1" id="$2" folder="$3" src="${4:-}"
  local target="$DEST/$folder"
  local tmp; tmp="$(mktemp -d)"

  log "memasang $name"
  if [[ -n "$src" ]]; then
    curl -fsSL "$src" -o "$tmp/ext.bin" || { warn "gagal unduh $src"; rm -rf "$tmp"; return 1; }
  else
    # Endpoint CRX Chrome Web Store.
    local url="https://clients2.google.com/service/update2/crx?response=redirect&prodversion=${PROD_VERSION}&acceptformat=crx2,crx3&x=id%3D${id}%26uc"
    curl -fsSL "$url" -o "$tmp/ext.crx" || { warn "gagal unduh id=$id"; rm -rf "$tmp"; return 1; }
    # Chrome Web Store mengembalikan XML error, bukan CRX, kalau id-nya salah.
    if head -c 64 "$tmp/ext.crx" | grep -q '<?xml'; then
      warn "endpoint mengembalikan XML, bukan CRX — id '$id' kemungkinan salah"
      head -c 300 "$tmp/ext.crx" | sed 's/^/       /'
      rm -rf "$tmp"; return 1
    fi
  fi

  rm -rf "$target"
  local f out
  f="$(ls "$tmp"/*.crx "$tmp"/*.bin 2>/dev/null | head -1)"
  [[ -n "$f" ]] || { warn "tidak ada berkas terunduh untuk $name"; rm -rf "$tmp"; return 1; }
  out="$(extract_crx "$f" "$target")" || { warn "ekstraksi gagal untuk $name: $out"; rm -rf "$tmp"; return 1; }

  case "$out" in
    OK*)
      IFS=$'\t' read -r _ nm ver mv <<< "$out"
      ok "$name → $target"
      echo "     terdeteksi: $nm v$ver ($mv)"
      # Peringatan penting: MetaMask dkk adalah MV3, dan extension bikinan kita
      # di extensions/agentdrop-wallet adalah MV2 (untuk Firefox). Keduanya
      # memang beda target — jangan dicampur ke satu direktori.
      if [[ "$mv" == "MV2" ]]; then
        warn "$name adalah Manifest V2. Chrome sudah menghapus dukungan MV2;"
        warn "ekstensi ini mungkin tidak akan berfungsi di Chrome for Testing."
      fi
      ;;
    *) warn "hasil tak terduga untuk $name: $out"; rm -rf "$tmp"; return 1 ;;
  esac
  rm -rf "$tmp"
}

# ----------------------------------------------------------------------------
MODE="required"; ONLY=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --all)   MODE="all" ;;
    --only)  MODE="only"; ONLY="${2:-}"; shift ;;
    --list)  list_manifest; exit 0 ;;
    -h|--help) sed -n '2,25p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) die "argumen tidak dikenal: $1" ;;
  esac
  shift
done

# Ekspor supaya python di bawah bisa membacanya
export _MODE="$MODE" _ONLY="$ONLY" _DEST="$DEST"

mapfile -t JOBS < <(python3 - "$MANIFEST" <<'PY'
import yaml, os, sys
m = yaml.safe_load(open(sys.argv[1])) or {}
mode, only = os.environ['_MODE'], os.environ.get('_ONLY', '')
want = {x.strip() for x in only.split(',') if x.strip()}
for e in (m.get('extensions') or []) + (m.get('extra') or []):
    if mode == 'required' and not e.get('required'): continue
    if mode == 'only' and e['name'] not in want: continue
    print('\t'.join([e['name'], e.get('id', ''), e['folder'], e.get('source', '')]))
PY
)

if [[ "${#JOBS[@]}" -eq 0 ]]; then
  warn "tidak ada entri yang cocok dengan mode '$MODE'"
  echo "    coba: $0 --list"
  exit 0
fi

gagal=0
for job in "${JOBS[@]}"; do
  IFS=$'\t' read -r n id fo src <<< "$job"
  install_one "$n" "$id" "$fo" "$src" || gagal=$((gagal + 1))
done

echo
if [[ "$gagal" -gt 0 ]]; then
  warn "$gagal ekstensi gagal dipasang"
else
  ok "selesai"
fi
echo "Terpasang di: $DEST"
echo "Selanjutnya: ./scripts/start-browser-cdp.sh"
echo
warn "Setelah terpasang, buka Chrome lewat noVNC SEKALI untuk membuat/mengimpor"
warn "wallet tiap ekstensi. Agent tidak boleh dan tidak bisa melakukan itu sendiri."
exit $(( gagal > 0 ? 1 : 0 ))
