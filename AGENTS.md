# AGENTS.md — konteks build AgentDrop

**WAJIB dibaca sebelum menulis kode apa pun di repo ini.**

Dokumen ini ada karena satu masalah nyata: lingkungan kerja di-reprovision
berulang kali (tujuh kali sejauh ini), dan setiap kali konteks hilang. Tanpa
berkas ini, pekerjaan berputar: hal yang sama dibangun ulang, keputusan yang
sudah dikunci diperdebatkan lagi, dan jalan buntu dilalui dua kali.

Aturan pakainya:

1. Baca bagian **TUJUAN** dan **KEPUTUSAN TERKUNCI** sebelum menyentuh kode.
2. Sebelum menyelesaikan satu tahap, perbarui **PROGRES** dan **LANGKAH
   BERIKUTNYA**.
3. Kalau menemukan jalan buntu, tulis di **JALAN BUNTU** — jangan cuma
   meninggalkannya.
4. Jangan menghapus entri lama kecuali keputusannya memang dibalik. Tandai
   usang, jangan hapus jejaknya.

---

## TUJUAN

Sistem siap-pakai untuk airdrop farming profesional yang:

- bisa di-clone dari GitHub dan **diinstal seperti framework ke dalam sistem**
  (bukan sekadar menyalin config), sebagaimana `pip install` atau installer
  Node/Docker memasang dependensi lalu menaruh binari di PATH;
- berjalan setelah kredensial diisi, tanpa langkah manual tersembunyi;
- seluruh aktivitasnya **tercatat dan bisa diaudit**, sehingga ketika sesuatu
  rusak, bagian yang salah bisa ditemukan tanpa membaca seluruh alur;
- setiap agent punya **memory loop** supaya tidak mengulang kesalahan yang sama.

Yang **bukan** tujuan: membuat ekstensi wallet sendiri, membuat browser sendiri,
atau menggantikan wallet resmi. Lihat keputusan K7.

---

## KEPUTUSAN TERKUNCI

Jangan perdebatkan ulang ini tanpa alasan baru yang eksplisit.

| # | Keputusan | Alasan singkat |
|---|---|---|
| **K1** | Browser = **Chrome for Testing + CDP**, bukan Camofox | Butuh ekstensi wallet resmi. Camoufox (fork Firefox) tidak punya jalur CDP dan ekosistem wallet-nya tipis. |
| **K2** | **Jangan** pakai Google Chrome branded | Sejak Chrome 137 build branded mengabaikan `--load-extension`. Chromium dan Chrome for Testing tetap mendukungnya. |
| **K3** | Hermes membaca **`.env`** (`HERMES_HOME/.env`, `override=True`) | `hermes_cli/env_loader.py:470-504`. `config.yaml` hanya *merujuk* lewat `${VAR}`. |
| **K4** | Akses **shell dimatikan** di semua worker lewat `agent.disabled_toolsets` | Bundle `hermes-cli` memuat `terminal` + `process` (`toolsets.py:31-35`). Tanpa ini agent membuka browser sendiri lewat shell. |
| **K5** | Log audit dibangun di atas **hook Hermes**, bukan wrapper | Gateway hooks + shell hooks (`VALID_HOOKS`, 77 event). |
| **K6** | Wallet = **MetaMask / OKX / Phantom yang diunduh**, manusia memegang kunci | Lihat K7. |
| **K7** | **TIDAK ADA ekstensi bikinan sendiri** | Provider non-official terdeteksi sebagai klien asing → risiko di-ban proyek; sebagian dApp menolak provider yang bukan wallet resmi; chain baru butuh `wallet_addEthereumChain` yang sudah ditangani wallet resmi. Konsekuensinya: signing daemon + policy engine ikut dihapus karena tidak punya pemanggil lagi. |
| **K8** | Skrip = **`install.sh` sebagai index** yang me-source `lib/*.sh`, plus **satu CLI `agentdrop`** | Operator bingung dengan 11 skrip yang tumpang tindih. |
| **K9** | Gateway dan agent **satu perintah** | Agent berjalan di atas gateway; memisahkannya membingungkan. |
| **K10** | Private key **tidak pernah** masuk `.env` | `.env` tersalin ke setiap profil → satu key jadi ada di tujuh tempat. Pakai `AGENTDROP_KEY_FILE` (berkas 0600). |
| **K11** | **Docker bukan dependensi** | Camofox satu-satunya pemakainya dan sudah dihapus. Chrome for Testing + Xvfb + noVNC jalan langsung di host. |
| **K12** | Knowledge = direktori `knowledge/` **terpisah**, per domain, dibaca **dan ditulis** agent | Berbeda dari `docs/` yang statis dan ditulis manusia. `knowledge/` dikembangkan agent lewat memory loop. |
| **K13** | Prompt system = **`SOUL.md` per profil**, sudah cukup | Tidak perlu lapisan prompt tambahan. Installer hanya memasangnya ke tempat yang benar. |

---

## DEFINISI SCOPE `install.sh`

`install.sh` memasang **framework ke dalam sistem**, bukan menjalankan aplikasi.
Bandingkan dengan installer Python/Node/Docker: mereka memasang dependensi,
menaruh berkas di lokasi sistem, menaruh binari di PATH, lalu berhenti.

MASUK scope `install.sh` (sudah dikonfirmasi operator 2026-08-26):

1. **Dependensi sistem** — python3 + venv, node, hermes, Xvfb/x11vnc/websockify
   untuk GUI browser. **Bukan Docker** (K11).
2. **Pemasangan AgentDrop ke sistem** — salin kode ke lokasi tetap, taruh CLI
   `agentdrop` di PATH (lihat tabel layout di bawah).
3. **Setup skill, memory, knowledge, prompt system**
   - prompt system = `SOUL.md` per profil (K13)
   - skill = per profil menurut `PROFILE_SKILLS`
   - memory = `memory/lessons/` + blok `memory:` di config
   - knowledge = `knowledge/` per domain, dibaca dan ditulis agent (K12)
   - hook audit = shell hook + gateway hook
4. **Kredensial** — tanya token/key, tulis ke tempat yang benar (K10).
5. **Setup browser** — Chrome for Testing (K1/K2), unduh ekstensi wallet (K6).
6. **Verifikasi akhir** — preflight.

KELUAR dari `install.sh` (masuk CLI `agentdrop`):

- menyalakan/mematikan browser dan gateway
- mengumpulkan log
- memasang cron
- burn-in
- membaca log audit

### Acuan: pola installer Hermes

Dibaca langsung dari `https://hermes-agent.nousresearch.com/install.sh`.
AgentDrop mengikuti pola ini, bukan mengarang sendiri:

- **Guard di awal.** `unset PYTHONPATH` dan `PYTHONHOME` — PYTHONPATH yang
  diwarisi bisa membuat pip memasang dari checkout yang salah, sehingga
  instalasi baru terlihat rusak atau basi. `export UV_NO_CONFIG=1`.
- **Deteksi non-interaktif.** `if [ -t 0 ]` — kalau stdin bukan terminal
  (`curl | bash`), `read -p` gagal dengan EOF dan `set -e` mematikan seluruh
  skrip **tanpa pesan**.
- **Layout FHS untuk root.** Kode di `/usr/local/lib/<nama>`, perintah di
  `/usr/local/bin/<nama>`, data tetap di `$HOME/.<nama>`. Hermes menyebutnya
  "matches Claude Code / Codex CLI". Non-root: kode di `~/.<nama>/<repo>`.
- **Opsi yang layak ditiru.** `--skip-setup`, `--skip-browser`, `--no-skills`,
  `--dir PATH`, `--hermes-home PATH`, `--non-interactive`,
  `--ensure DEPS` (hanya pasang dependensi, jangan clone/venv).

### Layout AgentDrop

| Isi | Lokasi (root) | Lokasi (non-root) |
|---|---|---|
| Kode | `/usr/local/lib/agentdrop` | `~/.agentdrop/app` |
| Perintah | `/usr/local/bin/agentdrop` | `~/.local/bin/agentdrop` |
| State (log, profil browser, key) | `~/.agentdrop/` | sama |
| Config Hermes | `~/.hermes/` | sama |

### Struktur `knowledge/` (K12)

Berbeda dari `docs/`: `docs/` ditulis manusia dan statis; `knowledge/`
dikembangkan agent. Satu berkas per domain supaya agent bisa membuka yang
relevan saja, bukan memuat semuanya ke konteks.

```
knowledge/
  chains/<slug>.md      RPC, chain ID, faucet, explorer, gas khas
  projects/<slug>.md    syarat kualifikasi, pola task, jebakan yang ditemui
  patterns/<slug>.md    pola lintas proyek (verifikasi tweet, klaim, dsb)
```

Isi awalnya hanya kerangka + cara mengisinya. Agent yang menambah isinya lewat
`skills/self-improvement`, dan `SOUL.md` merujuk ke sini.

---

## PROGRES

Terakhir diperbarui: 2026-08-26 · commit `5cceaf4` · branch `arena/01a037ea-agentdrop`
Angka di bawah diverifikasi dengan perintah, bukan diperkirakan.

**61 berkas ter-track · 7 profil · 10 skill · 119 pemeriksaan validator lolos (exit 0)**

Selesai dan terverifikasi:

- Struktur agent: 7 profil (`worker-orchestrator` + 6 worker), 10 skill,
  `SOUL.md` per profil, akses shell dimatikan di semua worker (K4).
- **Installer sebagai index** (K8): `install.sh` me-source `lib/*.sh` (6 modul),
  ditambah satu CLI `agentdrop`. `scripts/` turun dari 11 berkas ke 3.
- **Camofox dibersihkan total** — `grep -ril camofox` di luar `docs/` dan
  `AGENTS.md` mengembalikan nol.
- **Ekstensi bikinan sendiri + signing daemon dihapus** (K7).
- Log audit penuh dengan redaksi dua lapis, diuji per pola.
- Memory loop + `knowledge/` (K12).
- `AGENTS.md` ini.

**Dua bug nyata ditemukan saat pembersihan** — keduanya membuat hal yang rusak
terlihat sehat:

1. `worker-orchestrator/SOUL.md` menyuruh agent menjalankan
   `tools/signing_policy.py` yang sudah dihapus. Agent akan memanggil skrip
   yang tidak ada lalu harus berimprovisasi pada keputusan signing — tempat
   terburuk untuk berimprovisasi.
2. `scripts/burn-in.sh` memeriksa Camofox di port 9377 yang tidak ada
   pendengarnya, jadi burn-in selalu gagal di langkah 2 dari 4.
3. `install.sh --verify-only` exit 0 sambil melaporkan 9 kegagalan, karena
   `verify_run || true` menelan statusnya.

Ketiganya sudah diperbaiki.

---

## LANGKAH BERIKUTNYA

1. **Operator menjalankan uji di mesinnya** — lihat `docs/prosedur-uji.md`,
   hasilnya dikumpulkan dengan `agentdrop logs` lalu di-push ke
   `data/audit/<stempel>/`.
2. Yang belum pernah diuji dan hanya bisa diuji di mesin operator:
   - hook yang benar-benar menyala di dalam run Hermes yang hidup
   - Chrome for Testing yang benar-benar memuat ekstensi wallet
   - alur lengkap Telegram → orchestrator → worker → wallet
3. Bersihkan `docs/arsitektur-alur.md` dan `docs/prosedur-uji.md` dari sisa
   Camofox (masih ada; `docs/research.md` dan `docs/meta-2026.md` sengaja
   dibiarkan sebagai catatan historis).
4. Mismatch **E** masih terbuka: `platform_toolsets.telegram` di orchestrator
   belum memuat `delegation`.

## JALAN BUNTU

Jangan diulang.

- **Membuat ekstensi wallet sendiri** — dihapus, lihat K7.
- **Camofox / Camoufox** — fork Firefox, tanpa CDP, ekosistem wallet tipis.
  Seluruh `camofox-plugins/`, `config/camofox/`, `docker-compose.yml`,
  `scripts/start-browser.sh`, `scripts/takeover.sh` sudah dihapus.
- **Signing daemon + policy engine** — dihapus bersama ekstensi (K7). Masih
  bisa dipulihkan dari tag `arsip-sebelum-pembersihan` (`81417dc`) kalau suatu
  saat dibutuhkan: `git checkout arsip-sebelum-pembersihan -- tools/signing_daemon.py`.
- **`re.sub` tanpa `re.MULTILINE`** — `^agent:` tidak pernah cocok, sisipan
  gagal **diam-diam** dan terlihat berhasil. Selalu parse ulang YAML dan assert.
- **Uji redaksi yang hanya memeriksa "secret hilang"** — lolos meski polanya
  dihapus, karena pola base64-panjang jadi jaring pengaman. Uji **marker** tiap
  pola.
- **Pola bot token Telegram dengan `\b` di depan `\d{8,10}`** — di URL
  `.../bot123456789:AA...` karakter sebelum angka adalah huruf, jadi tidak ada
  word boundary dan token lolos.
- **Menempel blok YAML di akhir berkas untuk uji negatif** — ia jadi key
  top-level, bukan di bawah induknya, jadi cek yang diuji tidak pernah jalan.
- **`grep -P '[\x{4e00}-\x{9fff}]'`** — tidak jalan di grep ini. Pakai Python
  `re.search(r'[\u4e00-\u9fff\u3040-\u30ff]', ...)`.
- **Karakter CJK terselip** — sudah terjadi lima kali. Validator
  `check_no_stray_cjk` menjaga config/skills/scripts/README; `docs/research.md`
  sengaja dikecualikan karena mengutip istilah Mandarin.

---

## CATATAN LINGKUNGAN

- **Sandbox di-reprovision tanpa peringatan.** Commit yang belum di-push HILANG.
  Commit **dan push** segera setelah setiap tahap.
- Pemulihan setelah reprovision: `git fetch origin arena/01a037ea-agentdrop`,
  pastikan `git diff --stat FETCH_HEAD HEAD` hanya berisi pekerjaan baru, lalu
  `git reset --soft FETCH_HEAD` dan commit ulang. **Jangan pernah `reset --hard`.**
- `/tmp/venv` hilang setiap reprovision. Buat ulang:
  `python3 -m venv /tmp/venv && /tmp/venv/bin/pip install PyYAML eth-account`.
- `docker`, `hermes`, `Xvfb` **tidak ada** di sandbox. Jadi: launcher browser,
  hook yang menyala di run Hermes hidup, dan pemasangan ekstensi nyata **tidak
  bisa diuji di sini**. Jangan klaim sudah teruji kalau belum.
- `pip3 install` system diblokir PEP 668 — selalu pakai venv.
