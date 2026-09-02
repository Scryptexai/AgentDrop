#!/usr/bin/env python3
"""REPL AgentDrop -- satu sesi, banyak worker, tanpa `agentdrop run`.

Dijalankan oleh interpreter Python milik Hermes supaya `run_agent` bisa diimpor
langsung. Seluruh perintah `/...` ditangani DI SINI dan tidak pernah dikirim ke
LLM -- meniru pola cli.py Hermes, dan sesuai temuan Arc 29 bahwa teks `/` yang
tidak dikenal tidak diteruskan ke LLM.

Penggantian worker di tengah sesi memakai set_hermes_home_override()
(hermes_constants.py:30), bukan menulis ulang os.environ: Hermes mengunci
sebagian nilai pada saat impor, dan override ContextVar adalah mekanisme yang
gateway sendiri pakai (hermes_cli/gateway.py:3948).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import hermes_bridge as hb  # noqa: E402

# ---------------------------------------------------------------------------
# Tampilan
# ---------------------------------------------------------------------------

BIRU = "\033[36m"
HIJAU = "\033[32m"
MERAH = "\033[31m"
KUNING = "\033[33m"
REDUP = "\033[2m"
TEBAL = "\033[1m"
RESET = "\033[0m"


def _cetak(warna: str, teks: str) -> None:
    print(f"{warna}{teks}{RESET}")


def _garis(n: int = 62) -> None:
    print(f"{REDUP}{'─' * n}{RESET}")


# ---------------------------------------------------------------------------
# Penemuan worker
# ---------------------------------------------------------------------------


def daftar_worker(home: Path) -> list[str]:
    akar = home / "profiles"
    if not akar.is_dir():
        return []
    return sorted(p.name for p in akar.iterdir()
                  if p.is_dir() and (p / "config.yaml").is_file())


# ---------------------------------------------------------------------------
# Sesi
# ---------------------------------------------------------------------------


class Sesi:
    """Memegang satu agent aktif dan worker yang dipilih."""

    def __init__(self, home: Path, worker: str):
        self.home = home
        self.worker = worker
        self.agent = None
        self.info: dict = {}
        self._token = None

    def _pasang_home(self, worker: str) -> Path:
        direktori = hb.direktori_profil(self.home, worker)
        os.environ["HERMES_HOME"] = str(direktori)
        # Sesudah run_agent diimpor, env saja tidak cukup -- ContextVar yang
        # dibaca _agent_home() (agent/system_prompt.py:370) juga harus diarahkan.
        try:
            from hermes_constants import (  # type: ignore
                reset_hermes_home_override,
                set_hermes_home_override,
            )
            if self._token is not None:
                try:
                    reset_hermes_home_override(self._token)
                except Exception:
                    pass
            self._token = set_hermes_home_override(direktori)
        except Exception:
            # Hermes lama tanpa API ini: env tetap disetel, jadi tetap jalan
            # untuk worker pertama. Ganti worker mungkin butuh sesi baru.
            pass
        return direktori

    def muat(self, worker: str) -> None:
        self._pasang_home(worker)
        self.agent, self.info = hb.bangun_agent(
            self.home, worker,
            callbacks={
                "tool_start_callback": cb_tool_mulai,
                "tool_complete_callback": cb_tool_selesai,
            },
        )
        self.worker = worker


# ---------------------------------------------------------------------------
# Callback UX
# ---------------------------------------------------------------------------


def cb_tool_mulai(call_id, nama_tool, args):
    ringkas = str(args or "")
    if len(ringkas) > 90:
        ringkas = ringkas[:87] + "..."
    print(f"  {BIRU}▸{RESET} {nama_tool} {REDUP}{ringkas}{RESET}")


def cb_tool_selesai(call_id, nama_tool, args, result):
    teks = str(result or "")
    tanda = f"{REDUP}✗{RESET}" if '"error"' in teks[:200].lower() else f"{REDUP}·{RESET}"
    print(f"  {tanda} {nama_tool} selesai")


def cb_stream(delta):
    sys.stdout.write(str(delta))
    sys.stdout.flush()


# ---------------------------------------------------------------------------
# Perintah /...
# ---------------------------------------------------------------------------

BANTUAN = f"""{TEBAL}Perintah{RESET}
  /worker <nama>   pindah worker
  /daftar          daftar worker yang ada
  /info            toolset & config worker aktif
  /baru            mulai sesi bersih (buang riwayat)
  /bantuan         tampilkan ini
  /keluar          keluar  (Ctrl-D juga)

{TEBAL}Selain itu{RESET} apa pun yang Anda ketik dikirim ke worker sebagai task."""


def perintah_info(sesi: Sesi) -> None:
    info = sesi.info
    _garis()
    print(f"  worker    : {info.get('profil')}")
    print(f"  direktori : {info.get('home')}")
    ts = info.get("toolsets") or []
    print(f"  toolsets  : {', '.join(ts) if ts else '(bawaan Hermes)'}")
    dis = info.get("disabled_toolsets") or []
    print(f"  dimatikan : {', '.join(dis) if dis else '(tidak ada)'}")
    if sesi.agent is not None:
        n = len(getattr(sesi.agent, "valid_tool_names", ()) or ())
        print(f"  tool aktif: {n}")
    _garis()


def perintah_daftar(home: Path, aktif: str) -> None:
    pekerja = daftar_worker(home)
    if not pekerja:
        _cetak(MERAH, "  tidak ada worker terpasang -- jalankan ./install.sh")
        return
    _garis()
    for w in pekerja:
        tanda = f"{HIJAU}●{RESET}" if w == aktif else " "
        print(f"  {tanda} {w}")
    _garis()


# ---------------------------------------------------------------------------
# Loop utama
# ---------------------------------------------------------------------------


def buat_input_fn():
    """prompt_toolkit kalau ada (lingkungan Hermes punya), input() kalau tidak."""
    try:
        from prompt_toolkit import PromptSession  # type: ignore
        sesi = PromptSession()

        def _tanya(prompt: str) -> str:
            return sesi.prompt(prompt)
        return _tanya
    except Exception:
        def _tanya(prompt: str) -> str:
            return input(prompt)
        return _tanya


def banner(home: Path, worker: str) -> None:
    print()
    _cetak(TEBAL + HIJAU, "  AgentDrop — mesin Hermes, antarmuka AgentDrop")
    _cetak(REDUP, "  Ketik task lalu Enter. /bantuan untuk perintah.")
    n = len(daftar_worker(home))
    print(f"  {REDUP}{n} worker terpasang · aktif: {worker}{RESET}")
    print()


def jalankan(home: Path, worker: str, task_awal: str | None = None) -> int:
    sesi = Sesi(home, worker)
    banner(home, worker)

    try:
        sesi.muat(worker)
    except Exception as e:
        _cetak(MERAH, f"  gagal memuat worker '{worker}': {type(e).__name__}: {e}")
        _cetak(REDUP, "  periksa dengan: agentdrop status")
        return 2

    perintah_info(sesi)
    tanya = buat_input_fn()
    prompt = f"{BIRU}{worker}{RESET} › "

    def kerjakan(teks: str) -> None:
        try:
            hasil = sesi.agent.run_conversation(
                teks,
                stream_callback=cb_stream,
            )
        except TypeError:
            # Signature stream_callback berbeda di versi Hermes lain.
            hasil = sesi.agent.run_conversation(teks)
        except KeyboardInterrupt:
            print()
            _cetak(KUNING, "  dibatalkan")
            return
        print()
        sukses, alasan = hb.nilai_hasil(hasil)
        _cetak(HIJAU if sukses else MERAH,
               ("  ✓ " if sukses else "  ✗ ") + alasan)
        print()

    if task_awal:
        kerjakan(task_awal)

    while True:
        try:
            baris = tanya(prompt).strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not baris:
            continue

        if baris.startswith("/"):
            bagian = baris[1:].split(None, 1)
            nama = bagian[0].lower()
            arg = bagian[1].strip() if len(bagian) > 1 else ""

            if nama in ("keluar", "exit", "quit", "q"):
                break
            elif nama in ("bantuan", "help", "h", "?"):
                print(BANTUAN)
            elif nama == "daftar":
                perintah_daftar(home, sesi.worker)
            elif nama == "info":
                perintah_info(sesi)
            elif nama == "baru":
                try:
                    sesi.muat(sesi.worker)
                    _cetak(HIJAU, "  sesi baru dimulai")
                except Exception as e:
                    _cetak(MERAH, f"  gagal: {type(e).__name__}: {e}")
            elif nama == "worker":
                if not arg:
                    perintah_daftar(home, sesi.worker)
                    continue
                if arg not in daftar_worker(home):
                    _cetak(MERAH, f"  worker '{arg}' tidak ada. /daftar untuk melihat.")
                    continue
                try:
                    sesi.muat(arg)
                    prompt = f"{BIRU}{arg}{RESET} › "
                    _cetak(HIJAU, f"  pindah ke {arg}")
                    perintah_info(sesi)
                except Exception as e:
                    _cetak(MERAH, f"  gagal pindah: {type(e).__name__}: {e}")
            else:
                _cetak(MERAH, f"  perintah tidak dikenal: /{nama}")
                _cetak(REDUP, "  /bantuan untuk daftar")
            continue

        kerjakan(baris)

    _cetak(REDUP, "  sampai jumpa")
    return 0


def main(argv: list[str] | None = None) -> int:
    import argparse
    ap = argparse.ArgumentParser(prog="agentdrop-repl")
    ap.add_argument("--home", default=os.environ.get("HERMES_HOME_DIR", ""))
    ap.add_argument("--worker", default=None)
    ap.add_argument("--task", default=None, help="jalankan sekali lalu masuk REPL")
    args = ap.parse_args(argv)

    home = Path(args.home or os.environ.get("HERMES_HOME_DIR") or
                Path.home() / ".hermes")

    pekerja = daftar_worker(home)
    if not pekerja:
        _cetak(MERAH, f"  tidak ada worker di {home}/profiles")
        _cetak(REDUP, "  jalankan ./install.sh dulu")
        return 2

    worker = args.worker or os.environ.get("AGENTDROP_WORKER") or ""
    if worker not in pekerja:
        worker = "pekerja-koordinator" if "pekerja-koordinator" in pekerja else pekerja[0]

    return jalankan(home, worker, args.task)


if __name__ == "__main__":
    raise SystemExit(main())
