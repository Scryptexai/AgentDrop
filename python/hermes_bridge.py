#!/usr/bin/env python3
"""Jembatan AgentDrop -> mesin Hermes.

Berkas ini satu-satunya tempat AgentDrop menyentuh Python Hermes. Ia dijalankan
OLEH interpreter Python milik Hermes (bukan python3 sistem), supaya `run_agent`
bisa diimpor langsung dan tidak ada proses `hermes` anak yang harus diurai
stdout-nya.

Tiga aturan yang tidak boleh dilanggar, semuanya berasal dari
docs/struktur-hermes-internals.md:

1. HERMES_HOME disetel SEBELUM `import run_agent`. `resolve_profile_env()` di
   hermes_cli/profiles.py:2571 dipanggil "before any hermes modules are
   imported" karena Hermes mengunci nilai pada saat impor. Melanggar urutan ini
   menghasilkan profil yang salah TANPA pesan error.
2. `toolsets:` dibaca dari config profil terpasang dan diteruskan sebagai
   `enabled_toolsets`. Di run_agent.py:10012 parameter itu datang dari argumen
   CLI, bukan dari config -- jadi kalau kita tidak meneruskannya, worker
   mendapat SELURUH tool.
3. Keberhasilan dinilai dari hasil `run_conversation()` (`completed`,
   `api_calls`), bukan dari exit code. `hermes chat` keluar 0 walau task gagal
   total (Arc 34 Gap 1).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Penemuan interpreter Hermes
# ---------------------------------------------------------------------------


def temukan_python_hermes(binari: str | None = None) -> str | None:
    """Kembalikan interpreter Python yang menjalankan Hermes.

    Binari `hermes` adalah console_script pip: baris pertamanya shebang yang
    menunjuk persis ke interpreter lingkungan Hermes. Ini cara yang tidak perlu
    menebak lokasi pemasangan (yang tidak bisa diverifikasi dari sandbox).

    Mengembalikan None kalau tidak ketemu -- pemanggil yang memutuskan apakah
    itu fatal.
    """
    kandidat: list[Path] = []
    if binari:
        kandidat.append(Path(binari))
    dari_path = os.environ.get("AGENTDROP_HERMES_BIN")
    if dari_path:
        kandidat.append(Path(dari_path))
    for nama in ("hermes", "hermes-agent"):
        for direktori in os.environ.get("PATH", "").split(os.pathsep):
            if not direktori:
                continue
            p = Path(direktori) / nama
            if p.is_file():
                kandidat.append(p)

    for p in kandidat:
        try:
            with p.open("rb") as f:
                baris = f.readline(512)
        except OSError:
            continue
        if not baris.startswith(b"#!"):
            continue
        shebang = baris[2:].decode("utf-8", "replace").strip()
        # Bentuk "/usr/bin/env python3" maupun "/venv/bin/python" keduanya sah.
        bagian = shebang.split()
        if not bagian:
            continue
        py = bagian[-1]
        if "python" not in Path(py).name:
            continue
        if Path(py).is_absolute() and Path(py).is_file():
            return str(Path(py))
        # "/usr/bin/env python3" -> cari python3 di PATH
        for direktori in os.environ.get("PATH", "").split(os.pathsep):
            calon = Path(direktori) / py
            if calon.is_file():
                return str(calon)
    return None


# ---------------------------------------------------------------------------
# Pembacaan config profil
# ---------------------------------------------------------------------------


def direktori_profil(home: Path, nama: str) -> Path:
    """Cermin get_profile_dir() di hermes_cli/profiles.py:385."""
    if nama == "default":
        return home
    return home / "profiles" / nama


def muat_config(path: Path) -> dict:
    """Baca config.yaml. PyYAML pasti ada di lingkungan Hermes (Hermes sendiri
    memakainya), tapi kegagalannya dibuat jelas, bukan jadi KeyError misterius.
    """
    try:
        import yaml  # type: ignore
    except ImportError:
        raise SystemExit(
            "PyYAML tidak tersedia di interpreter ini. Jalankan lewat "
            "interpreter Hermes (lihat `agentdrop status`)."
        )
    if not path.is_file():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def daftar_toolset(cfg: dict) -> list[str]:
    """Ambil `toolsets:` level atas -- inilah yang dipakai jalur CLI.

    `platform_toolsets.<platform>` adalah kunci BERBEDA dan hanya dibaca jalur
    gateway lewat _get_platform_tools() (hermes_cli/tools_config.py:2646).
    Untuk sesi CLI kita butuh yang level atas.
    """
    nilai = cfg.get("toolsets")
    if not isinstance(nilai, list):
        return []
    return [str(t) for t in nilai if t]


def daftar_disabled(cfg: dict) -> list[str]:
    """Ambil `agent.disabled_toolsets`. Terkonfirmasi dibaca Hermes di
    hermes_cli/tools_config.py:2917 dan cli.py:5514.
    """
    bagian = cfg.get("agent") or {}
    if not isinstance(bagian, dict):
        return []
    nilai = bagian.get("disabled_toolsets")
    if not isinstance(nilai, list):
        return []
    return [str(t) for t in nilai if t]


# ---------------------------------------------------------------------------
# Konstruksi agent
# ---------------------------------------------------------------------------


def bangun_agent(home: Path, nama_profil: str, *, platform: str = "cli",
                 session_id: str | None = None, quiet: bool = True,
                 callbacks: dict | None = None):
    """Bangun AIAgent untuk satu profil.

    URUTAN DI SINI ADALAH INTINYA: HERMES_HOME disetel sebelum run_agent
    diimpor. Jangan pindahkan impor ini ke atas berkas.

    `callbacks` dipetakan langsung ke parameter konstruktor AIAgent. Signature
    yang dipakai Hermes (dibaca dari pemanggilannya, bukan ditebak):
      tool_start_callback(tool_call_id, function_name, display_args)
          -- agent/tool_executor.py:1067
      tool_complete_callback(call_id, tool_name, args, result)
          -- agent/tool_executor.py:1891, gateway/run.py:5620
    """
    direktori = direktori_profil(home, nama_profil)
    os.environ["HERMES_HOME"] = str(direktori)

    cfg = muat_config(direktori / "config.yaml")
    toolsets = daftar_toolset(cfg)
    disabled = daftar_disabled(cfg)

    # Impor SETELAH env disetel. Lihat docstring modul.
    from run_agent import AIAgent  # type: ignore

    kwargs: dict = {
        "enabled_toolsets": toolsets or None,
        "disabled_toolsets": disabled or None,
        "platform": platform,
        "quiet_mode": quiet,
        "max_iterations": 60,
    }
    if session_id:
        kwargs["session_id"] = session_id
    for kunci, fn in (callbacks or {}).items():
        if callable(fn):
            kwargs[kunci] = fn

    return AIAgent(**kwargs), {
        "profil": nama_profil,
        "home": str(direktori),
        "toolsets": toolsets,
        "disabled_toolsets": disabled,
        "session_id": session_id,
    }


# ---------------------------------------------------------------------------
# Pelatihan worker
# ---------------------------------------------------------------------------


def prompt_latih(materi: str) -> str:
    """Susun prompt pelatihan memakai mesin /learn milik Hermes sendiri.

    `agent/learn_prompt.py` adalah satu-satunya penyusun prompt /learn, dipakai
    bersama oleh CLI, gateway, dan dashboard. Kita memanggil fungsi yang sama
    supaya hasil pelatihan identik dengan `hermes /learn` -- bukan menulis
    prompt tandingan yang perilakunya menyimpang.

    Kalau versi Hermes terpasang tidak punya fungsi ini, kita tidak mengarang
    prompt sendiri secara diam-diam: pesannya jelas, karena prompt pelatihan
    yang salah lebih buruk daripada tidak ada pelatihan.
    """
    try:
        from agent.learn_prompt import build_learn_prompt  # type: ignore
    except Exception as e:
        raise RuntimeError(
            f"build_learn_prompt tidak tersedia di Hermes terpasang "
            f"({type(e).__name__}: {e}). Perbarui Hermes atau latih lewat "
            f"`hermes /learn` langsung."
        )
    return build_learn_prompt(materi)


def daftar_skill(direktori: "Path") -> set:
    """Nama skill yang ada di satu direktori, untuk membandingkan sebelum/sesudah.

    Pelatihan yang tidak menghasilkan apa pun harus terlihat sebagai kegagalan,
    bukan sebagai jawaban panjang yang terdengar meyakinkan.
    """
    akar = Path(direktori) / "skills"
    if not akar.is_dir():
        return set()
    return {p.name for p in akar.iterdir() if p.is_dir() and (p / "SKILL.md").is_file()}


# ---------------------------------------------------------------------------
# Penilaian hasil
# ---------------------------------------------------------------------------


def nilai_hasil(hasil: dict) -> tuple[bool, str]:
    """Ubah hasil run_conversation() menjadi (sukses, alasan).

    Kontrak kunci dibaca dari pemakaian nyata di run_agent.py:10042-10052:
    completed, api_calls, messages, final_response.
    """
    completed = bool(hasil.get("completed"))
    api_calls = int(hasil.get("api_calls") or 0)
    pesan = hasil.get("final_response") or ""

    if api_calls == 0:
        return False, "tidak ada satu pun panggilan LLM -- periksa endpoint & API key"
    if not completed:
        return False, f"loop berhenti sebelum selesai ({api_calls} panggilan LLM)"
    if not str(pesan).strip():
        return False, f"selesai tapi jawaban kosong ({api_calls} panggilan LLM)"
    return True, f"selesai -- {api_calls} panggilan LLM"


# ---------------------------------------------------------------------------
# Mode periksa
# ---------------------------------------------------------------------------


def periksa(home: Path, nama_profil: str | None) -> int:
    """Laporkan apakah jembatan bisa mencapai mesin Hermes. Dipakai
    `agentdrop status` supaya kegagalan terlihat SEBELUM task dijalankan.
    """
    laporan = {"interpreter": sys.executable}
    py_hermes = temukan_python_hermes()
    laporan["python_hermes"] = py_hermes
    try:
        import run_agent  # type: ignore
        # Dipakai, bukan sekadar diimpor: kita laporkan apakah kelas mesinnya
        # benar-benar ada, bukan hanya modulnya.
        laporan["run_agent"] = True
        laporan["punya_AIAgent"] = hasattr(run_agent, "AIAgent")
    except Exception as e:  # pragma: no cover - tergantung lingkungan
        laporan["run_agent"] = False
        laporan["kesalahan"] = f"{type(e).__name__}: {e}"
        print(json.dumps(laporan, ensure_ascii=False, indent=2))
        return 1

    if nama_profil:
        direktori = direktori_profil(home, nama_profil)
        cfg = muat_config(direktori / "config.yaml")
        laporan["profil"] = {
            "nama": nama_profil,
            "direktori": str(direktori),
            "config_ada": (direktori / "config.yaml").is_file(),
            "toolsets": daftar_toolset(cfg),
            "disabled_toolsets": daftar_disabled(cfg),
        }
    print(json.dumps(laporan, ensure_ascii=False, indent=2))
    return 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="hermes_bridge",
        description="Jalankan satu task worker lewat mesin Hermes.",
    )
    ap.add_argument("--home", default=os.environ.get("HERMES_HOME_DIR", ""),
                    help="HERMES_HOME utama (induk dari profiles/)")
    ap.add_argument("--profile", required=False, default=None)
    ap.add_argument("--task", default=None)
    ap.add_argument("--session-id", default=None)
    ap.add_argument("--check", action="store_true",
                    help="hanya periksa jembatan, jangan jalankan task")
    ap.add_argument("--json", action="store_true", help="keluarkan JSON")
    args = ap.parse_args(argv)

    home = Path(args.home or os.environ.get("HERMES_HOME_DIR") or
                Path.home() / ".hermes")

    if args.check:
        return periksa(home, args.profile)

    if not args.profile or not args.task:
        ap.error("--profile dan --task wajib diisi")

    try:
        agent, info = bangun_agent(home, args.profile, session_id=args.session_id)
    except Exception as e:
        print(f"bridge: gagal membangun agent: {type(e).__name__}: {e}",
              file=sys.stderr)
        return 2

    if not args.json:
        print(f"profil   : {info['profil']}")
        print(f"toolsets : {', '.join(info['toolsets']) or '(bawaan)'}")
        if info["disabled_toolsets"]:
            print(f"dimatikan: {', '.join(info['disabled_toolsets'])}")
        print("-" * 60)

    hasil = agent.run_conversation(args.task)
    sukses, alasan = nilai_hasil(hasil)

    if args.json:
        keluaran = {
            "sukses": sukses,
            "alasan": alasan,
            "completed": hasil.get("completed"),
            "api_calls": hasil.get("api_calls"),
            "final_response": hasil.get("final_response"),
        }
        print(json.dumps(keluaran, ensure_ascii=False, indent=2))
    else:
        jawaban = str(hasil.get("final_response") or "").strip()
        if jawaban:
            print(jawaban)
        print("-" * 60)
        print(("✓ " if sukses else "✗ ") + alasan)

    try:
        agent.close()
    except Exception:
        pass
    return 0 if sukses else 1


if __name__ == "__main__":
    raise SystemExit(main())
