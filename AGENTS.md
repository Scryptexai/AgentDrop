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

## PROTOKOL BROWSER — OpenManus + inventaris tool Hermes

Bagian ini ada karena konteksnya hilang dua kali. **Jangan menulis ulang
protokol browser tanpa membaca ini lebih dulu.**

### Warisan OpenManus (`FoundationAgents/OpenManus`)

Tiga hal yang diambil, dan satu yang sengaja ditolak:

1. **Elemen dirujuk, bukan diseleksi.** OpenManus memakai
   `[index]<type>text</type>`; Hermes memakai `ref` dari accessibility tree
   (`@e5`). Prinsipnya sama: **tidak ada CSS selector, tidak ada XPath.**
   UI website airdrop berubah setiap deploy; selector mengunci agent ke satu
   versi tampilan.
2. **`evaluation_previous_goal: Success|Failed|Unknown` wajib di setiap
   langkah.** Di AgentDrop ini jadi `berhasil` / `gagal` / `tidak diketahui`
   plus bukti. Tanpa ini agent menumpuk aksi di atas asumsi dan melaporkan
   keberhasilan palsu.
3. **Progres dihitung eksplisit** ("3 dari 7 task"). Ini yang membedakan
   "sedang mengerjakan langkah 5" dari "sudah 40 putaran di langkah yang sama".

**Yang ditolak:** prompt browser OpenManus menulis *"If captcha pops up, try to
solve it"*. Di AgentDrop CAPTCHA selalu diserahkan ke manusia lewat noVNC.

### Inventaris tool — diverifikasi dari sumber Hermes

`tools/browser_tool.py` + `tools/web_tools.py`, toolset `browser` dan `web`:

```
browser_navigate  browser_snapshot  browser_click   browser_type
browser_scroll    browser_press     browser_back    browser_vision
browser_get_images  browser_console  browser_exec   browser_dialog
browser_cdp       web_search        web_extract
```

Fakta yang sering salah:

- **`browser_scroll(direction=...)` hanya menerima `"up"` atau `"down"`**
  (enum, required). Paling sering dilewati padahal paling sering berhasil —
  tombol Claim/Connect sering di bawah lipatan.
- **`browser_type` mengosongkan field lebih dulu**, lalu mengetik. Bukan untuk
  menambah teks.
- **`browser_press("Enter")` untuk submit form**, lebih tahan perubahan UI
  daripada mencari tombol Submit.
- **Tidak ada `browser_search`.** Pencarian lewat `web_search`.
- **`computer_use` (Set-of-Mark) BUKAN bagian browser** — ia toolset terpisah
  dan **tidak diaktifkan** untuk profil mana pun. Skill yang menyuruh
  memakainya adalah bug; sudah dibersihkan di `browser-operation`,
  `browser-burn-in`, `x-engager`, README, dan `docs/arsitektur-alur.md`.

### Loop otonom: lanjut atau berhenti

Loop berhenti **hanya** pada satu dari empat kondisi:

| Kondisi | Tindakan |
|---|---|
| Task selesai — semua langkah rencana `berhasil` | ringkas + bukti per langkah |
| Butuh manusia — login, CAPTCHA, 2FA, KYC, approval wallet | sebut apa & di mana, lalu tunggu |
| Buntu — 3 pendekatan berbeda gagal di langkah yang sama | lapor langkah, 3 pendekatan, dugaan penyebab |
| Ragu — confidence < 0.7 pada keputusan tak-terurungkan | pertanyaan spesifik |

Bukan alasan berhenti: halaman lambat, satu aksi gagal, tampilan tak terduga.
Bukan alasan lanjut: mengulang aksi sama ketiga kalinya, atau lanjut setelah
verifikasi `tidak diketahui`.

Batas putaran ada di `agent.max_turns` per profil. Mendekatinya adalah tanda
untuk berhenti dan melapor, bukan mempercepat.

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

Terakhir diperbarui: 2026-08-28 · branch `arena/01a037ea-agentdrop`
Angka diverifikasi dengan perintah, bukan diperkirakan.

**7 profil · 10 skill · 13 berkas knowledge · 187 pemeriksaan validator lolos (exit 0)**

Selesai:

- Installer sebagai index (K8) + satu CLI `agentdrop`. `scripts/` 11 → 3.
- Camofox dibersihkan total; extension bikinan + signing daemon dihapus (K7).
- Mismatch E ditutup; `TOOLSET_IDS` dibangun ulang dari sumber Hermes — **34**
  id dari `toolsets.py:TOOLSETS`, isinya diverifikasi identik.
- Kontrak tool browser dikunci — lihat PROTOKOL BROWSER.
- **Workflow eksplisit di ketujuh SOUL.md** (sebelumnya `grep -ci workflow` = 0
  di semua profil).
- **Knowledge base berisi nyata** — `patterns/` 5, `meta/` 1, `chains/` 5.
  `projects/` berisi satu berkas penjelas saja (supaya direktorinya terlacak
  git — direktori kosong tidak dilacak, padahal 13 berkas menyuruh agent
  menulis ke sana); catatan per proyek diisi agent seiring pemakaian.
- Alur ujung-ke-ujung di `docs/arsitektur-alur.md` bagian 1 dan 3.
- **Sweep menyeluruh bersih**: tidak ada satu pun path backtick di repo yang
  menunjuk berkas yang tidak ada.
- **`knowledge/` terhubung ke SEMUA skill** — sebelumnya 22 rujukan di tujuh
  `SOUL.md` dan **nol** di sepuluh `SKILL.md`. Skill adalah prosedur yang
  benar-benar dijalankan, jadi memori lintas-proyek tidak pernah dibaca saat
  bekerja. Tiap skill kini membuka dengan "baca dulu" dan "tulis balik".
- **Peta tool browser dikoreksi**: toolset `browser` punya **14** anggota, dan
  `web_extract` bukan salah satunya — ia milik toolset `web`, yang tidak
  diaktifkan untuk `worker-daily`, `worker-discord`, `worker-x`.
- **Dokumen dibaca ulang dari awal sampai akhir**, bukan di-grep. Ini menemukan
  8 klaim palsu yang lolos dari semua validator (lihat di bawah).
- **Ketujuh `SOUL.md` sudah dibaca penuh** (arc kedua dari teknik yang sama).
  Ini menemukan cacat paling berbahaya sejauh ini — lihat di bawah.
- **Batas wallet ditegaskan**: agent menyiapkan sampai popup muncul, **tidak
  pernah** menekan `Confirm`/`Sign`/`Approve`. Klasifikasi task jadi tiga kelas
  (`auto` / `siapkan` / `human`), bukan dua.
- **Alasan anti-prompt-injection dikoreksi di ketujuh profil.** Sebelumnya:
  "agent memegang wallet" — padahal tidak. Alasan yang benar justru lebih kuat,
  karena manusia menandatangani apa yang agent sodorkan.
- **Angka toolset dikoreksi: 34, bukan 58.** `toolsets.py:TOOLSETS` = 34,
  `tools_config.py:CONFIGURABLE_TOOLSETS` = 26, gabungan 35. Tidak ada sumber
  Hermes yang berisi 58.

### Arc ketiga — hal yang hanya ketahuan dari sumber Hermes

Semua temuan di bawah diverifikasi terhadap `hermes-agent` yang di-clone, bukan
dari ingatan. Clone ulang setelah reprovision:
`git clone --depth 1 https://github.com/NousResearch/hermes-agent.git /tmp/ha`.

- **`gateway.multiplex_profiles: true` wajib, dan tadinya tidak ada.** Hermes
  menyimpan cron job **per profil** (`cron/jobs.py:68`, issue #4707):
  `hermes --profile worker-daily cron create` menulis ke
  `~/.hermes/profiles/worker-daily/cron/jobs.json`. Gateway yang dinyalakan
  `agentdrop start` berjalan dengan `HERMES_HOME=~/.hermes` (profil default),
  jadi ticker-nya membaca `~/.hermes/cron/jobs.json` yang kosong. Komentar di
  `gateway/run.py:31774` menyebut akibatnya persis: profil sekunder
  "**silently ignored** — jobs show as scheduled with a valid `next_run_at` but
  never execute". `cron list` dan `cron status` semuanya terlihat sehat.
  Rantai buktinya: `jobs.py:80` → `hermes_constants.py:114` → `main.py:680`
  (`--profile` **menyetel** `HERMES_HOME`) → `profiles.py:2529`.
- **Konsekuensinya:** jangan jalankan gateway per profil. Docs Hermes
  (`multi-profile-gateways.md:108`) melarang secondary profile menyalakan
  gateway sendiri saat multiplex aktif. README dan `install-cron.sh` sudah
  diluruskan ke `agentdrop start`.
- **`agentdrop run <profil> "<tugas>"** — panggil SATU agent untuk debug, tanpa
  orkestrasi. Lewat gateway Anda tidak bisa tahu worker mana yang rusak.
  Bentuknya `hermes --profile <p> chat -q <tugas>`; `--profile` harus di depan
  subcommand karena di-parse sebelum argparse
  (`_parser.py:22 PRE_ARGPARSE_INHERITED_FLAGS`).
- **`install.sh` sekarang MEMASANG Hermes**, bukan `_die` kalau tidak ada.
  Installer resmi: `curl -fsSL https://hermes-agent.nousresearch.com/install.sh`.
  Dua jebakan: installer Hermes membaca stdin (di bawah `curl | bash` ia EOF dan
  `set -e` mematikan rantai tanpa pesan → stdin diarahkan ke `/dev/null`), dan
  binarinya masuk `~/.local/bin` yang mungkin belum ada di PATH proses ini.
- **Log aktivitas masuk ke DALAM repo** (`data/logs/`, tidak lagi di-gitignore).
  Hook Hermes dipanggil sebagai perintah polos tanpa environment, jadi
  `AGENTDROP_LOG_DIR` tidak pernah sampai ke proses hook — variabel itu dibaca
  di 5 tempat dan di-set di **nol** tempat. `install.sh` sekarang menulis path
  ke `~/.agentdrop/logdir`, dan `tools/audit_log.py` +
  `hooks/.../handler.py` membacanya sebagai fallback.
- **GUI browser jadi syarat keras.** Komentarnya sudah bilang "GUI WAJIB ada"
  tapi kodenya memakai `command -v x11vnc &&` — mesin tanpa x11vnc menjalankan
  Chrome tanpa layar, dan operator bertemu "login tidak bisa" jauh dari
  penyebabnya. Sekarang `_die` dengan perintah apt-nya. Path `--web` noVNC
  juga dicari, bukan dihardcode ke `/usr/share/novnc` (salah path = websockify
  jalan tapi 404, gejalanya identik dengan noVNC rusak).
- **Tiga hand-off antar agent yang hilang.** Pembagian tugas agent 1–5 cocok
  1:1 dengan profil yang ada, tapi sambungannya tidak ada: `worker-daily` tidak
  pernah menyebut `worker-x` (task "buat konten" dikerjakan agent check-in
  tanpa bahan riset); `worker-x` tidak membaca `knowledge/projects/<nama>.md`
  hasil analyzer sebelum bikin konten; `worker-discord` hanya menulis
  `discord-log.json`, tidak ke `knowledge/`. Ketiganya sudah disambung.
- **Dua variabel orphan sisa subsistem yang dihapus:** `SIGNER_PORT`
  (`lib/00-common.sh`, 0 pemakaian) dan `prof` (`agentdrop cmd_start`, dibaca
  tapi tidak pernah dipakai — jadi `agentdrop start worker-daily` diam-diam
  sama saja dengan `agentdrop start`).

### Arc keempat — koreksi operator: noVNC bukan satu-satunya layar

Dipicu laporan operator: **ekstensi bisa diunduh tapi tidak bisa dibuka di
dalam noVNC.** Itu benar, dan bukan keluhan kosmetik — popup ekstensi wallet
sering gagal muncul di dalam sesi VNC, clipboard tidak sinkron, dan koordinat
klik bisa meleset. Untuk login manual dan persetujuan transaksi, itu fatal.

Yang salah adalah kode saya, bukan Chrome-nya. `browser_start` **menimpa
`DISPLAY` tanpa syarat** (dulu baris 178 dan 228) dan tidak pernah memeriksa
apakah mesin sudah punya layar. Jadi di desktop biasa pun Chrome dipaksa masuk
framebuffer virtual dan hanya bisa dicapai lewat noVNC.

Chrome for Testing adalah **aplikasi desktop penuh** — logo Chrome dengan
tulisan "Test" di kotak hitam, jendela sendiri (developer.chrome.com,
`docs/chrome_for_testing`). Ia tidak butuh VNC kalau mesin punya layar.

Perbaikan:

- `browser_real_display()` mendeteksi layar asli. Kalau `xdpyinfo` ada,
  DISPLAY diverifikasi; kalau tidak, X lokal dipastikan dari socketnya
  (`:N` → `/tmp/.X11-unix/XN`). DISPLAY mati **ditolak**, bukan dipercaya.
- `BROWSER_MODE=auto|native|vnc` di `.env`, atau `agentdrop browser --native|--vnc`.
  `auto` memakai layar mesin kalau ada, jatuh ke noVNC kalau tidak.
- Blok Xvfb + x11vnc + websockify sekarang **bersyarat** — hanya di jalur VNC.
  `lib/10-deps.sh` dan `browser_status()` ikut sadar layar, supaya tidak
  memperingatkan Xvfb di desktop biasa.
- **18 rujukan dokumen disisir.** README, `docs/prosedur-uji.md`, dan
  `install.sh` semuanya menjanjikan noVNC sebagai satu-satunya jalan masuk;
  sekarang menyebut jendela asli sebagai jalur utama dan noVNC untuk mesin
  tanpa layar.

**Yang tertangkap oleh uji, bukan oleh pembacaan:** versi pertama
`browser_real_display` mempercayai DISPLAY buta ketika `xdpyinfo` tidak
terpasang. Sandbox ini tidak punya `xdpyinfo`, jadi uji enam keadaan
langsung menunjukkannya — `DISPLAY=:77` yang mati diterima. Diperbaiki dengan
pemeriksaan socket. Dua kali harness uji saya sendiri yang salah sebelum itu
(delimiter `:` bertabrakan dengan nilai DISPLAY; `touch` membuat berkas biasa,
bukan socket) — pola lama: **kalau dua pemeriksaan saya tidak setuju, yang
dicurigai adalah pemeriksaannya.**

### Bug pertama yang ketahuan dari mesin operator

`agentdrop browser` di mesin operator mencetak:

```
lib/40-browser.sh: line 313: [[: 0
0: syntax error in expression (error token is "0")
```

Penyebabnya `grep -c ... || echo 0`. **`grep -c` mencetak `0` DAN keluar dengan
status 1** saat tidak ada kecocokan, jadi `echo 0` ikut jalan dan menempelkan
nol kedua — `n` menjadi `$'0\n0'`, dan `[[ "$n" -gt 0 ]]` gagal. `|| echo 0`
itu sendiri disengaja (menahan status untuk `set -euo pipefail`), tapi caranya
salah: yang benar `|| true` lalu `${n:-0}`.

Empat tempat, bukan satu: `lib/40-browser.sh:312` dan `:337`,
`scripts/collect-logs.sh:152` dan `:153`. Keempatnya diperbaiki.

**Kenapa 180 pemeriksaan validator melewatkannya:** tidak ada satu pun yang
membandingkan keluaran `grep -c` secara numerik. Ditambahkan pemeriksaan di
`check_shell` yang menolak pola `grep -c ... || echo 0` pada baris non-komentar.
Diuji dengan menyuntikkan pola buruk ke `collect-logs.sh` — tertangkap di
baris 154 — lalu dipulihkan dan lolos.

Pemeriksaan itu sempat menangkap **komenarnya sendiri** yang mendokumentasikan
pola tersebut, jadi baris yang diawali `#` dilewati.

Pelajarannya: **verifikasi saya tidak pernah menjalankan `agentdrop browser`
sungguhan** karena sandbox tidak punya display. Uji enam keadaan display
menangkap bug logika layar, tapi tidak ada yang menjalankan cabang
"ekstensi terlihat lewat CDP". Cabang yang tidak pernah dieksekusi adalah
tempat bug bersembunyi.

### Penyebab sebenarnya "popup ekstensi tidak bisa dibuka"

Operator melaporkan popup tetap tidak bisa dibuka **setelah** perbaikan layar.
Jadi diagnosis saya sebelumnya salah: ini tidak pernah soal VNC.

Penyebabnya `--load-extension` berubah perilaku sejak **Chrome 126**. Tanpa
flag pendamping, Chrome memperlakukan ekstensi itu sebagai *sementara*:
halamannya bisa dibuka, tapi ekstensi **tidak ditulis ke Secure Preferences**
profil. Akibatnya service worker tidak pernah jalan, content script tidak
disuntikkan, dan **popup tidak bisa dibuka** — semuanya tanpa pesan error.
MetaMask, OKX, dan Phantom ketiganya MV3 dengan service worker, jadi ketiganya
kena.

Perbaikannya satu flag: `--enable-unsafe-extension-debugging`. Dengan flag itu
Chrome memperlakukan ekstensi `--load-extension` sebagai instalasi sungguhan.
Aman di sini karena CDP diikat ke `127.0.0.1` (`--remote-debugging-address`),
jadi permukaan serangnya lokal.

Dua sumber independen: dev.to/toyama0919 (Chrome 126+ broke extension dev
setup) dan RFC chromium-extensions `aEHdhDZ-V0E` (Oliver Dunk, tim Chrome).

**Koreksi atas klaim saya sendiri.** Saya menulis di `lib/40-browser.sh` bahwa
"popup ekstensi bisa dibuka" di jendela asli, dan di pesan peringatan bahwa
hilangnya target `chrome-extension://` di `/json` "BUKAN hal normal" sejak
Chrome 126. Keduanya overklaim:

- Yang pertama belum pernah saya uji — sandbox tidak punya display.
- Yang kedua salah secara faktual: service worker MV3 memang sering tidak
  terdaftar di `/json` walau ekstensinya sehat. Jadi `/json` **bukan bukti**
  ke arah mana pun.

Bukti yang sah hanya satu: `window.ethereum` dan `window.solana` di console
jendela browser. Pesan peringatannya sekarang mengatakan itu.

**Pelajaran:** saya punya dua arc yang memperbaiki gejala (layar) sementara
penyebabnya ada di tempat lain (flag Chrome). Keduanya lolos validator karena
validator tidak menjalankan Chrome. **Klaim "ini akan bekerja" yang tidak pernah
dieksekusi adalah klaim, bukan hasil.**

### Penyebab sebenarnya Chrome tidak pernah di-restart

Operator melaporkan browser tetap tidak terbuka sesudah perbaikan flag. Bukti
kuncinya ada di keluaran mereka sendiri dan saya lewatkan dua kali:
**websocket UUID-nya identik di tiga run** —
`eb9fea55-5005-4915-aef3-e96ee5a535f6`. UUID itu dihasilkan sekali per proses
browser. Sama berarti **Chrome tidak pernah di-restart**, jadi tidak satu pun
perbaikan flag pernah dipakai.

Mekanismenya: Chrome memakai **ProcessSingleton** pada `--user-data-dir`. Kalau
sudah ada instance dengan profil yang sama, peluncuran kedua hanya memberi
sinyal ke proses lama lalu **keluar sendiri** — tanpa jendela baru, tanpa pesan
error. Port CDP tetap dijawab proses LAMA, dan `browser_ws` hanya memeriksa
port, bukan proses, jadi ia melaporkan "CDP siap" dan kita percaya.

Tiga hal yang hilang di `browser_start`:

1. Tidak ada pemanggilan `browser_stop` sebelum launch (`grep -c kill` = 0).
2. Tidak ada `pkill` untuk Chrome yang dimulai di luar agentdrop.
3. Tidak ada pembersihan `SingletonLock`/`SingletonCookie`/`SingletonSocket`.

Perbaikan: hentikan Chrome lama, tunggu **prosesnya** mati, bersihkan singleton,
lalu verifikasi dua hal sesudah launch — proses baru masih hidup (`kill -0`),
dan **UUID websocket berubah**. UUID yang tidak berubah berarti yang menjawab
masih Chrome lama.

**Uji dengan Chrome tiruan menemukan cacat di perbaikan saya sendiri.** Versi
pertama menunggu *port* berhenti menjawab, bukan *prosesnya* mati. Chrome lama
terbukti sudah mati, tapi kodenya tetap `_die` — karena port masih dijawab
sebentar. Logikanya sama kelirunya dengan bug aslinya. Diganti menunggu
`pgrep -f -- "--user-data-dir=..."` kosong.

**Kesalahan harness yang berulang tiga kali:** pola `pkill -f`/`pgrep -f`
mencocokkan **baris perintah shell saya sendiri**, jadi `kill` membunuh shell
yang sedang menjalankan uji. Gejalanya: perintah selesai dengan keluaran kosong
dan exit -1. Solusinya kelas karakter — `user-data-di[r]=...` — supaya pola
tidak cocok dengan dirinya sendiri. Ini contoh keempat dari pola lama: **kalau
pemeriksaan saya bertingkah aneh, yang dicurigai pemeriksaannya.**

### install.sh gagal sebelum sempat membuat profil dan skill

Operator melaporkan: tidak ada profil agent yang terbuat, skill juga tidak.
Keluhan itu benar, dan penyebabnya urutan stage.

`stage_deps` berjalan **pertama**, dan di dalamnya ada **8 panggilan `_die`**
(`_die() { _err "$*"; exit 1; }` di `lib/00-common.sh:24`). Stage itu mengunduh
installer Hermes dan memasang PyYAML lewat pip — dua langkah yang paling sering
gagal: jaringan, proxy, PEP 668, disk penuh. Begitu salah satunya gagal, install
berhenti dan `stage_setup` **tidak pernah tercapai**. Padahal `stage_setup`-lah
yang memanggil `hermes_install`, satu-satunya tempat profil dan skill disalin.

Jadi "install gagal" dan "profil kosong" adalah satu kejadian yang sama.

Perbaikannya urutan, bukan logika. Profil, skill, config, hook, dan memory
semuanya **murni salin-berkas dari repo** — diverifikasi: nol rujukan
`curl`/`npx`/`pip`/`venv`/`python` di `stage_setup`. Tidak ada alasan
menaruhnya di belakang langkah berjaringan. Urutan baru:

```
stage_install_code → stage_credentials → stage_setup → stage_deps → stage_browser → stage_verify
```

**Diuji sungguhan, bukan dibaca.** `install.sh --non-interactive --skip-browser`
dijalankan dengan `HOME` tiruan di sandbox yang egress-nya diblokir, sehingga
unduhan Hermes gagal dengan `SSL_ERROR_SYSCALL`. Hasilnya:

```
exit code: 1                     (Hermes memang gagal)
profil : 7 dari 7                (tetap terbuat)
skill  : 10 dari 10              (tetap terbuat)
config : ADA
```

Dan urutan barunya terlihat di log: `Config utama` baris 21, `Profil worker`
baris 23, `Memasang Hermes` baris 56.

**Catatan tentang diagnosis saya sendiri.** Dugaan pertama saya adalah
`hermes_install` tidak pernah dipanggil. Itu salah — `grep` menunjukkan ia
dipanggil di `install.sh:167`. Uji pertama saya juga menyesatkan: log mencetak
"✓ worker-orchestrator — 5 skill" untuk ketujuh profil, tapi direktori tujuan
kosong. Penyebabnya harness saya menyetel `HERMES_HOME_DIR` **sebelum**
me-source `lib/00-common.sh`, yang menimpanya di baris 9
(`HERMES_HOME_DIR="${HERMES_HOME:-$HOME/.hermes}"`). Berkasnya ada, hanya di
tempat lain. **Log yang sukses dan disk yang kosong harus diselesaikan dulu
sebelum menyimpulkan apa pun.**

### Yang kita bangun tidak seluruhnya terpasang — dan validator tidak melihatnya

Operator memperjelas keluhannya: bukan Hermes-nya, melainkan **skill, knowledge,
profil, memory loop, prompt system** — yang kita bangun — yang tidak terpasang.
Saya uji dengan menjalankan `install.sh` sungguhan lalu menghitung apa yang
benar-benar mendarat dibanding inventaris repo. Hasilnya menemukan tiga cacat.

**1. `memory/` tidak pernah disalin.** Daftar di `stage_install_code`
(`install.sh:128`) adalah `lib tools skills config hooks agent-hooks knowledge
AGENTS.md` — `memory` tidak ada. Jadi `memory/lessons/README.md` tidak pernah
sampai ke lokasi kerja.

**2. `memory/lessons/` tidak pernah dibuat per profil.** `hermes_install`
membuat `$dst/memories`, `$dst/logs`, `$dst/cron` — bukan
`$dst/memory/lessons`. Padahal **ketujuh SOUL.md** menyuruh agent membaca
`memory/lessons/<profil-anda>.md` sebelum mengerjakan task, dan skill
`self-improvement` menyuruh menulis ke sana. cwd agent adalah HERMES_HOME
profil itu, jadi path relatif tersebut menunjuk ke direktori yang tidak pernah
ada. Langkah pertama setiap agent adalah membaca berkas yang tidak ada — dan
memory loop yang jadi alasan K12 tidak pernah benar-benar berputar.

**3. `hermes_install_memory()` hanya `mkdir`, tidak menyalin apa pun**, dan
mkdir-nya ke `$REPO_ROOT/memory/lessons` — lokasi yang tidak dibaca agent.

**4. Akar kenapa ini lolos 180 pemeriksaan.** Daftar berkas shell validator
(`tools/validate_config.py:1178`) hanya `scripts/*.sh` + `install.sh`.
**Enam berkas `lib/*.sh` dan CLI `agentdrop` tidak pernah diperiksa sama
sekali** — padahal di situlah mayoritas logika installer berada. Ini juga
sebabnya bug `grep -c || echo 0` di `lib/40-browser.sh` lolos, dan sebabnya
pemeriksaan memory/lessons yang pertama saya tulis **tidak pernah berjalan**.

Perbaikan:

- `memory` masuk daftar salinan; `mkdir -p "$dst/memory/lessons"` per profil;
  `hermes_install_memory` menyalin README dan membuat 7 berkas profil kosong di
  `$STATE_DIR/memory/lessons/`.
- Daftar periksa validator jadi `scripts/*.sh` + `lib/*.sh` + `install.sh` +
  `agentdrop` → **180 menjadi 187 berkas**.
- Pemeriksaan baru: `install.sh` harus memuat `memory` di daftar salinan, dan
  `lib/30-hermes.sh` harus punya `mkdir` untuk `$dst/memory/lessons`.

**Pemeriksaan pertama saya terlalu lemah dan saya menangkapnya dengan uji.**
Versi awal mencari "ada `mkdir memory/lessons` di mana pun", jadi ia tetap lolos
ketika mkdir per-profil dihapus — karena ada mkdir lain untuk `$STATE_DIR`.
Diperketat ke `\$dst/memory/lessons`, disuntikkan cacatnya, dan sekarang
tertangkap. **Pemeriksaan yang belum pernah dilihat gagal adalah pemeriksaan
yang belum teruji.**

Diuji ulang end-to-end dengan `HOME` tiruan (Hermes gagal karena egress sandbox
diblokir, jadi jalur gagalnya yang teruji):

```
profil                    repo=7   terpasang=7
SOUL.md (prompt system)   repo=7   terpasang=7
skill                     repo=10  terpasang=10
knowledge                 repo=13  terpasang=13
memory/lessons per profil repo=7   terpasang=7
memory loop (kerja)       repo=7   terpasang=7
config.yaml profil        repo=7   terpasang=7
```

### Install berhenti diam-diam di "==> Model" — dan profil tidak pernah terbuat

Operator menjalankan `./install.sh` dan keluarannya berhenti tepat sesudah
`==> Model`, tanpa pesan error. `~/.hermes/profiles/` kosong.

Penyebabnya satu baris di `_ask_secret` (`lib/20-credentials.sh`):

```sh
[[ -n "$v" ]] && { _env_set "$var" "$v"; _ok "$var diisi"; }
```

Itu baris **terakhir** fungsi. Kalau pengguna menekan Enter tanpa mengisi kunci
API, `$v` kosong, ujiannya gagal, bentuk `&&` mengembalikan **1**, dan fungsi
ikut mengembalikan 1. Di bawah `set -euo pipefail` pemanggilnya mati **tanpa
pesan apa pun**.

Yang membuat ini jahat: prompt-nya sendiri menulis *"atau kosongkan lalu isi di
.env"* — jadi mengosongkan adalah jalur yang sah, dan justru jalur itulah yang
mematikan pemasangan. Karena `stage_credentials` berjalan sebelum
`stage_setup`, profil, skill, dan memory loop tidak pernah terbuat.

**Perbaikan urutan kemarin tidak cukup.** Saya sudah memindah `stage_deps` ke
belakang `stage_setup`, tapi `stage_credentials` masih di depannya dan masih
punya jalur yang mematikan. Menggeser satu stage tidak menyelesaikan masalah
kalau stage lain di depan masih bisa mematikan.

Perbaikan: `if/then` + `return 0` eksplisit.

**Diuji dengan pty sungguhan**, karena tanpa tty fungsi keluar lebih awal di
penjaga `[[ ! -t 0 ]]` dan bug-nya tidak terlihat sama sekali:

| | sesudah `==> Model` |
|---|---|
| kode baru (`if/then`) | lanjut → Wallet → `LANJUT KE STAGE BERIKUTNYA` |
| pola lama (`&&`) | **mati diam-diam** |

Uji pertama saya **tidak** mereproduksi bug karena stdin-nya bukan tty —
`_ask_secret` keluar di penjaga sebelum mencapai `read`. Kondisi operator
justru tty. **Kalau uji tidak meniru kondisi nyata, uji itu tidak menguji apa
pun.** Diperbaiki dengan `script -qec` untuk mengalokasikan pty.

Diperiksa juga apakah pola ini ada di tempat lain: disisir semua baris terakhir
fungsi di `lib/*.sh`, `install.sh`, `agentdrop` — hanya satu, dan sudah
diperbaiki. Uji terpisah menunjukkan pola `&&` di **tengah** fungsi aman
(exit 0); hanya baris terakhir yang berbahaya.

Pemeriksaan validator ditambahkan: menolak baris terakhir fungsi berpola
`[[ ... ]] &&`. Diuji dengan menyuntikkan pola lama — tertangkap di
`lib/20-credentials.sh:51` — lalu dipulihkan dan lolos.

Uji akhir end-to-end (`install.sh` sungguhan, `HOME` tiruan, kunci model kosong):

```
Config utama → Profil worker → Skill di HERMES_HOME → Memory lessons → Memasang Hermes
profil         : 7 dari 7
memory/lessons : 7 dari 7
skill          : 10 dari 10
```

### Penyebab SEBENARNYA install mati di "==> Model" — sesudah tiga diagnosis meleset

Operator melaporkan install masih berhenti di tempat yang sama sesudah tiga
perbaikan. Tiga diagnosis saya sebelumnya **semuanya salah**, dan semuanya salah
dengan cara yang sama: menyasar baris yang tidak pernah dieksekusi.

Penyebab sebenarnya ada di baris PERTAMA `_ask` dan `_ask_secret`:

```sh
cur="$(grep -E "^${var}=" "$ENV_FILE" 2>/dev/null | head -1 | cut -d= -f2-)"
```

`install.sh` berjalan dengan `set -euo pipefail`. **grep yang tidak menemukan apa
pun keluar dengan 1.** Dengan `pipefail` status itu menular ke seluruh pipeline,
lalu ke assignment-nya, lalu `set -e` mematikan installer **tanpa pesan apa
pun**.

Ini menjelaskan pola yang sebelumnya tidak masuk akal:

| variabel | ada di `.env` operator? | grep | hasil |
|---|---|---|---|
| `TELEGRAM_BOT_TOKEN` | ya | cocok, exit 0 | lolos |
| `TELEGRAM_HOME_CHANNEL` | ya | cocok, exit 0 | lolos |
| `OPENROUTER_API_KEY` | **tidak** | gagal, exit 1 | **mati** |

Prompt kuncinya bahkan tidak sempat tercetak, karena matinya di baris pertama
fungsi — sebelum `read`. Itu petunjuk yang ada di keluaran operator sejak awal
dan saya lewatkan tiga kali.

**Kenapa tiga perbaikan saya meleset:**

1. Urutan stage — benar sebagai perbaikan, tapi tidak menyentuh penyebabnya.
2. `[[ -n "$v" ]] && {...}` di baris terakhir `_ask_secret` — cacat nyata, tapi
   baris itu **tidak pernah tercapai** karena fungsinya mati di baris pertama.
3. Uji pty saya "berhasil" karena `.env` uji saya **memuat** baris
   `OPENROUTER_API_KEY=` (kosong tapi ada), sehingga grep-nya cocok. Kondisi
   operator: barisnya tidak ada sama sekali. **Uji saya tidak meniru kondisi
   yang dilaporkan.**

Perbaikan: `|| true` di dalam `$( )` pada ketiga tempat — dua di
`lib/20-credentials.sh`, satu di `lib/40-browser.sh` (sisa perbaikan
ProcessSingleton saya sendiri, `pgrep` yang gagal saat tidak ada Chrome lama).

**Dibuktikan dengan perbandingan langsung**, `.env` identik dengan milik
operator (Telegram terisi, `OPENROUTER_API_KEY` tidak ada):

```
kode lama : ==> Kredensial → Telegram → ==> Model → MATI (exit 1)
kode baru : ==> Kredensial → Telegram → ==> Model → Wallet → LANJUT (exit 0)
```

Uji end-to-end `install.sh` sungguhan dengan `.env` itu:

```
Memasang kode → Kredensial → Config utama → Profil worker
  → Skill di HERMES_HOME → Memory lessons → Memasang Hermes
profil 7/7 · memory/lessons 7/7 · skill 10/10 · knowledge 13/13
```

**Pemeriksaan validator untuk kelas bug ini.** Versi pertama regex-nya
memakai `[^"]*`, yang berhenti di tanda kutip dalam `grep -E "^${var}="`,
sehingga `\|` tidak pernah tercapai dan pemeriksaan **tidak pernah menangkap
apa pun** — diuji dengan menghapus `|| true` dan melihatnya lolos. Diganti
`.*`, dan sekarang menangkap kedua baris.

**Pelajaran yang paling mahal dari arc ini:** saya tiga kali memperbaiki gejala
karena tidak pernah mereproduksi kondisi yang dilaporkan operator. Uji yang
`.env`-nya berbeda dari `.env` operator bukan uji untuk bug operator.

### Ekstensi dari Chrome Web Store, bukan unduh CRX otomatis

Operator meminta pemasangan ekstensi tidak otomatis — pakai yang ada di Chrome
Web Store. Permintaan itu benar secara teknis, bukan sekadar selera.

Memasang dari Web Store lebih baik daripada menyuntik CRX:

- ekstensi terdaftar **sungguhan** di profil (Secure Preferences), bukan
  sementara seperti `--load-extension` — yang sejak Chrome 126 membuat service
  worker tidak jalan dan popup tidak bisa dibuka
- ikut diperbarui otomatis oleh Chrome
- versinya yang ditinjau Google, bukan CRX yang kita ambil sendiri
- tidak ada mesin ekstraksi CRX3 yang bisa salah

Perubahan:

- `store:` URL ditambahkan untuk 5 wallet di `config/extensions.yaml`
  (format diverifikasi: `https://chromewebstore.google.com/detail/<id>`)
- `browser_print_store_links()` mencetak tabel wallet + tautan
- `stage_browser` tidak lagi mengunduh; hanya mencetak tautan
- `agentdrop extensions` default mencetak tautan; `--sideload` menghidupkan
  jalur CRX lama untuk mesin tanpa akses ke Web Store

### Dua ✗ di `agentdrop status` operator

**`scripts/collect-logs.sh tidak ada`.** Ini lebih serius dari keluhan
validator: `agentdrop:161` memanggil `bash "$ROOT/scripts/collect-logs.sh"`, dan
`$ROOT` adalah **direktori terpasang**, bukan repo. `scripts` tidak ada di
daftar salinan `stage_install_code` — jadi **`agentdrop logs` rusak di mesin
operator**, bukan hanya validatornya yang mengeluh. Ini cacat yang sama
bentuknya dengan `memory` yang hilang: daftar salinan tidak lengkap.

**5 error CJK di `extensions/installed/okx-wallet/...`.** False positive.
Direktori itu di-gitignore dan berisi kode pihak ketiga yang kita unduh; OKX
membawa string CJK di bundle minified-nya dan itu memang milik mereka.
Menyisirnya menghasilkan 5 error yang tidak bisa diperbaiki siapa pun, dan
menutupi error yang nyata.

`_own_extension_js()` kini mengecualikan apa pun di bawah `installed/`.
**Diuji dengan dua berkas CJK** — satu di `extensions/installed/okx-wallet/`,
satu di `extensions/mine/` — dan hanya milik kita yang tertangkap. Berkas uji
dihapus sesudahnya.

Uji end-to-end `install.sh` sesudah semua perubahan:

```
profil 7/7 · memory/lessons 7/7 · skill 10/10 · scripts/collect-logs.sh tersalin
```

### Kelas bug yang berulang — dan cara menangkapnya

**Memberi tahu agent memakai sesuatu yang tidak ada — atau melarang/mewajibkan
sesuatu yang bertentangan dengan rancangan.** Sepuluh kali:

1. `SOUL.md` orchestrator → `tools/signing_policy.py` yang sudah dihapus
2. Tiga skill → `computer_use(mode='som')`, toolset yang tidak diaktifkan
3. `platform_toolsets.telegram` → `delegate_task`, bukan id toolset
4. Empat workflow → "cek pengetahuan" tanpa menyebut berkas mana
5. Tiga skill → `scripts/takeover.sh` yang sudah dihapus
6. **Tujuh berkas menjelaskan aturan verifikasi-URL lewat mekanisme Camofox**
   (`adopt_existing_tab`, `session_key`): enam `SKILL.md` (airdrop-intake,
   browser-burn-in, browser-operation, daily-executor, discord-engager,
   quest-executor) dan `SOUL.md` orchestrator. Kuncinya nyata di Hermes tapi
   hidup di `browser.camofox.*`, jadi tidak berlaku untuk CDP. Aturannya benar,
   penjelasannya salah. Lima ditemukan lebih dulu; **tiga lagi** lolos karena
   kata "camofox" tidak muncul di baris itu — hanya perilakunya.

   *(Angka ini sendiri sempat salah tulis sebagai "delapan skill". Perhitungan
   5 + 3 tidak mengurangi `browser-burn-in` yang muncul di kedua commit, dan
   menyebut `SOUL.md` sebagai skill. Diperbaiki dengan `git show --name-only |
   sort -u` — **hitung berkas unik dari git, jangan jumlahkan dua daftar**.)*
7. **`browser-operation` menyajikan `web_extract` di tabel tool browser.** Ia
   bukan anggota toolset `browser`. Karena skill itu dipasang ke semua profil
   sementara toolset `web` hanya di empat, tiga agent ditawari tool yang tidak
   bisa mereka panggil.

8. **🔴 Tabel klasifikasi orchestrator menyerahkan SEMUA signature ke agent.**
   Dua barisnya: `auto:wallet` → "agent, lewat policy engine"; `human:wallet` →
   "**hanya** kalau policy engine menjawab `ESCALATE`/`DENY`". Policy engine
   sudah dihapus, jadi syarat yang membuat sebuah aksi menjadi milik manusia
   adalah panggilan ke sesuatu yang tidak akan pernah menjawab. Dibaca harfiah:
   `human:wallet` tidak pernah terpicu, semua aksi wallet jatuh ke agent, dan
   **agent menandatangani sendiri** — kebalikan persis dari rancangan.
   Beberapa baris di bawahnya (tabel baris 152, prosa baris 170), berkas yang
   sama mengatakan hal yang benar.
   **Berkas yang berkontradiksi dengan dirinya lebih berbahaya daripada yang
   sekadar salah**, karena setengah mana yang lebih dipercayai agent menentukan
   apakah kunci tetap di tangan manusia.

9. **Aturan keras melarang langkah yang justru ditugaskan.** "Tidak ada
   transaksi. Tidak ada bridging." Padahal mengisi form bridge adalah yang
   memunculkan popup. Titik berhentinya benar; kata-katanya melarang pekerjaan.

10. **Template output tidak punya field yang workflow-nya sendiri wajibkan.**
    `worker-analyzer` menulis "VERDICT → dengan confidence eksplisit", tapi
    template yang disalin agent berhenti di `Evidence`. Agent mengikuti
    template, bukan kalimat yang menjelaskan template — jadi confidence hilang,
    dan ambang 0.7 yang memicu review manusia ikut mati.

**Yang menangkap 5, 6, dan 7 bukan validator, melainkan sweep**: jalankan
pencarian atas semua path backtick di repo dan cek keberadaannya satu per satu.
Validator [21] hanya memeriksa rujukan `knowledge/`. **Jalankan sweep itu setiap
kali menghapus berkas.**

### Teknik kedua: baca dokumen dari awal sampai akhir

Lima commit berturut-turut (`de994ba`…`ff31472`) semuanya memperbaiki klaim yang
**tidak akan pernah tertangkap grep**, karena tidak ada kata kunci yang salah —
hanya isinya yang basi. Yang ditemukan:

| Dokumen | Klaim palsu | Kenyataan |
|---|---|---|
| `docs/prosedur-uji.md` | preflight memeriksa "daemon" | daemon dihapus; `lib/50-verify.sh` punya 5 bagian |
| `docs/prosedur-uji.md` | "47 policy + 25 daemon + 9 plugin" | **nol** suite test tersisa |
| `docs/prosedur-uji.md` | "154 checks" | 179 |
| `README.md` | "119 pemeriksaan" | 179 |
| `README.md` | "Suite test: 47 + 25 + 9" | nol |
| `arsitektur-alur.md` | "tiga selesai, tiga terbuka" | lima selesai, satu terbuka |
| `arsitektur-alur.md` | heading B "MASIH TERBUKA" padahal isinya "ditutup dengan menghapusnya" | kontradiksi internal |
| `arsitektur-alur.md` | entri A: policy engine memutuskan wallet | policy engine dihapus |

**Pelajarannya: dokumen yang sudah ditambal beberapa kali harus dibaca ulang
utuh, bukan di-grep.** Grep mencari kata yang salah; yang basi adalah angka dan
mekanisme yang kedengarannya masuk akal.

**Catatan penting soal grep sendiri.** Saat memverifikasi jadwal cron, grep saya
melaporkan 3 job lalu 5 — keduanya salah. Polanya melewatkan bentuk mingguan
`0 21 * * 0`, lalu menghitung definisi fungsi `create_job() {`. Ada **4** job,
dan dokumennya benar. **Sebuah selisih bisa berarti dokumennya salah ATAU
pemeriksaannya salah. Pastikan yang mana sebelum menulis apa pun.**

---

## LANGKAH BERIKUTNYA

Semua yang bisa dikerjakan tanpa Hermes + Chrome terpasang **sudah selesai**.
Yang tersisa hanya bisa diuji di mesin operator:

1. **Operator menjalankan uji** — `docs/prosedur-uji.md`, hasil dikumpulkan
   dengan `agentdrop logs` lalu di-push ke `data/audit/<stempel>/`.
2. Yang belum pernah terbukti di lingkungan mana pun:
   - hook yang benar-benar menyala di dalam run Hermes yang hidup
   - Chrome for Testing yang benar-benar memuat ekstensi wallet
   - alur lengkap Telegram → orchestrator → worker → wallet
3. `knowledge/projects/` berisi `README.md` penjelas saja; catatan per proyek
   diisi agent seiring pemakaian.
   RPC di `knowledge/chains/` dicantumkan tapi **ditandai belum diverifikasi** —
   periksa dengan `eth_chainId` sebelum dipakai.
4. Kalau ada yang rusak: `agentdrop audit doctor` lebih dulu.

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

---

## Arc 12 — `agentdrop status` mati dengan traceback, dan 87 skill di UI Hermes

Dua laporan operator, dua sifat yang berbeda: yang pertama cacat nyata, yang
kedua **bukan** seperti yang dilaporkan — tapi menyembunyikan cacat lain.

### 1. `FileNotFoundError: ~/.agentdrop/app/install.sh`

Validator dijalankan `lib/50-verify.sh:74` dari `$REPO_ROOT`, dan sesudah
install `$REPO_ROOT` adalah **lokasi terpasang**, bukan repo. Validator
membaca `install.sh`, `README.md`, `.gitignore`, `.env.example` — tidak
satunya pun ikut disalin. Hasilnya traceback Python mentah di layar operator.

**Yang diperbaiki bukan empat berkas itu, tapi bentuk daftarnya.** Daftar
allow yang menyebut satu per satu apa yang disalin sudah gagal **empat
kali**, selalu dengan pola yang sama: ada yang membaca berkas dari `$ROOT`,
dan tidak ada yang menambahkannya ke daftar.

| # | yang hilang | akibat |
|---|---|---|
| 1 | `memory` | memory/lessons tidak pernah terbuat |
| 2 | `lib` | tidak pernah tervalidasi, cacat lolos 180 checks |
| 3 | `scripts` | `agentdrop logs` mati di runtime |
| 4 | `install.sh` + 3 lainnya | traceback ini |

Daftarnya **dibalik**: salin seluruh repo sebagai cermin (`tar` dengan
`--exclude`), kecualikan yang memang tidak boleh ikut (`.git`, `.env`,
cache, `extensions/installed`, sesi browser hidup). Berkas baru kini ikut
dengan sendirinya — kelas cacat M mati secara struktural, bukan ditambal.

**Jebakan di sini:** pemeriksaan validator yang menjaga daftar itu mencari
`for item in ...`. Sesudah loop-nya hilang, regex tidak cocok lagi, dan
karena dipagari `if m and ...` pemeriksaan itu **berhenti menyala tanpa
suara**. Validator tetap bilang 187 lolos. Pemeriksaan yang belum pernah
terlihat gagal bukanlah pemeriksaan — ini keenam kalinya.

### 2. "Skill tidak ada di Hermes" — klaimnya salah, tapi ada cacat di baliknya

Operator menempel daftar **87 skill** dari UI Hermes dan menyimpulkan skill
kita tidak terpasang. Diuji: **kesepuluh skill AgentDrop ada di daftar itu.**
Klaimnya tidak benar.

Yang benar: 87 = 10 milik kita + **77 bawaan Hermes**. Diverifikasi ke
sumbernya (`git clone hermes-agent`): repo itu punya 201 `SKILL.md` di
`skills/` + `optional-skills/`, dan **77/77** nama asing di daftar operator
cocok dengan bawaan Hermes. Bukan sisa pemasangan kita yang rusak.

**Cacat nyatanya:** toolset untuk skill-skill itu memang sudah mati di semua
profil (diverifikasi: `terminal`, `code_execution`, `computer_use` tidak
diaktifkan di satu profil pun), tapi **manifest skill tetap masuk ke konteks
agent**. Jadi agent bisa memutuskan mengikuti prosedur yang kita larang —
termasuk `computer-use`, yang justru ditolak validator kita sendiri di [20].
Dan 77 dokumen prosedur asing yang terbaca agent adalah permukaan
prompt-injection yang tidak perlu.

Ditutup dengan mekanisme resmi Hermes: `skills.disabled` di `config.yaml`
(dibaca `agent/skill_utils.py:446 get_disabled_skill_names()`, dipakai
`agent/prompt_builder.py:1814` untuk menyaring manifest). Sembilan skill
dimatikan: `computer-use`, `xurl`, `python-debugpy`, `node-inspect-debugger`,
`claude-code`, `codex`, `opencode`, `himalaya`, `google-workspace`.

**Harus di 8 berkas, bukan 1.** Profil adalah HERMES_HOME terpisah penuh dan
tidak mewarisi config utama — menaruhnya hanya di `config.yaml` utama tidak
berpengaruh apa pun pada worker. `hermes-agent` sengaja TIDAK dimatikan:
itu satu-satunya isi `ESSENTIAL_SKILLS` (`skill_utils.py:443`) dan Hermes
mengurangkannya dari daftar disabled mana pun, jadi menuliskannya hanya
memberi rasa aman palsu.

Dikunci pemeriksaan `[22]`, diuji dengan tiga suntikan: buang seksi
`skills` dari satu profil, buang satu nama dari config utama, dan matikan
`hermes-agent`. Ketiganya tertangkap.

**Pelajaran:** ketika laporan operator tidak cocok dengan bukti, keduanya
bisa benar sebagian. Skill memang terpasang (klaim operator salah), tapi
UI yang menampilkan 87 memang menandakan sesuatu yang belum kita kunci
(laporan operator benar soal gejalanya). Jangan berhenti di "klaimnya
keliru" — cari tahu apa yang sebenarnya dilihat orang itu.


---

## Arc 13 — Model custom tidak termuat: `provider: "auto"` tidak menyelesaikan ke apa pun

Laporan operator: *"model setiap worker tidak termuat custom model, semua model
dan provider bawaan hermes saja yg tersedia atau terlihat."*

Kuncinya **sah** — `model.default`, `model.provider`, `model.base_url` semuanya
dibaca Hermes (34/50/29 kemunculan di `hermes_cli/`). Yang salah adalah
**nilainya**.

Dua baris sumber yang menentukan:

1. `hermes_cli/auth.py:2268`
   ```python
   if normalized != "auto": ...
   ```
   `model.provider` hanya dipakai kalau nilainya ada di `PROVIDER_REGISTRY` —
   37 nama (`nous`, `openai-codex`, `openai-api`, `copilot`, `gemini`,
   `anthropic`, ...). **`"auto"` tidak ada di sana.** Dan `"openrouter"` pun
   tidak: openrouter ditangani *early-return* terpisah di `auth.py:2262`.
   Jadi `provider: "auto"` tidak pernah menyelesaikan ke OpenRouter — ia jatuh
   ke deteksi env / `auth.json`.

2. `hermes_cli/config.py:2990` — Hermes memperingatkan hal ini sendiri:
   > merged `model.provider` default (often `"auto"`, **which runtime
   > resolution treats as authoritative and would otherwise route the model
   > through the wrong active provider**)

Karena provider tidak pernah jadi `openrouter`, katalog model yang dibangun
`hermes_cli/model_catalog.py` **per-provider** tidak menunjuk OpenRouter.
Itulah sebabnya UI hanya menampilkan model dan provider bawaan Hermes —
persis yang dilihat operator.

**Perbaikan:** `provider: "auto"` → `provider: "openrouter"` di **8 berkas**
(config utama + 7 profil; profil tidak mewarisi config utama). Komentar lama
yang menganjurkan `"auto"` ikut diganti — komentar yang salah lebih berbahaya
daripada tidak ada komentar, karena orang berikutnya akan mempercayainya.

Dikunci pemeriksaan `[23]`, diuji tiga suntikan: `provider: "auto"` di satu
profil (cacat asli operator), `provider: "gemini"` yang tidak cocok dengan
`base_url` OpenRouter, dan `model.default` tanpa prefix `provider/`.
Ketiganya tertangkap.

**Pelajaran:** nilai `"auto"` terasa aman karena terdengar seperti "biarkan
sistem memilih". Di sini ia justru berarti *"tidak memilih apa pun"* — dan
kegagalannya tidak bersuara, hanya diam-diam memakai provider lain. Kalau sebuah
config punya field yang menentukan sumber data, nilai `auto` di field itu
harus diverifikasi ke kode yang membacanya, bukan diasumsikan.

---

## Arc 14 — `browser_navigate` tidak ada di sesi: `browser.backend` kosong berarti Hermes memilih sendiri

Laporan operator: skill `x-engager` dan `browser-operation` termuat, tapi
`browser_navigate` **tidak tersedia di sesi**, dan tidak ada tool browser sama
sekali. Padahal `browser` ada di `toolsets:` worker-x.

Bukan toolset yang salah. Yang mengganti daftar tool adalah field lain.

`tools/browser_use_cli.py:216` `is_browser_use_cli_mode()`:

```
backend terisi -> mode = (backend == "browser-use")
backend KOSONG -> mode = (_find_cli() is not None)
```

Dan docstring modul yang sama, baris 3:

> When `browser.backend` is `"browser-use"`, the model gets `browser_exec` tool
> **instead of** default browser tools

Jadi `backend: ""` bukan berarti "pakai tool bawaan". Ia berarti **"aktifkan
Browser Use kalau CLI-nya atau `uvx` kebetulan terpasang di mesin."** Satu paket
`uvx` yang tidak berhubungan sudah cukup untuk mencabut `browser_navigate`,
`browser_click`, `browser_type`, `browser_scroll` dari agent dan menggantinya
dengan **satu** tool `browser_exec`.

Semua SKILL.md dan SOUL.md AgentDrop menyebut `browser_*`. Kalau mode itu aktif,
seluruh prosedur merujuk tool yang tidak ada — persis yang dilaporkan operator.

**Yang membuat cacat ini bertahan:** komentar kita sendiri di
`config/hermes/config.yaml` menulis

```
# Kosong = built-in browser tools. Jangan diisi "browser-use".
```

Itu **terbalik**. Kosong justru membiarkan Hermes memilih, dan pilihannya bisa
Browser Use. Karena komentarnya dipercaya, ketujuh profil tidak pernah menyetel
field ini sama sekali — jadi tidak ada satu pun yang terlindungi.

Ini instance ke-sekian dari kelas yang sama: komentar yang salah lebih berbahaya
daripada tidak ada komentar, karena orang berikutnya mempercayainya dan tidak
pernah memeriksa ulang.

**Perbaikan:** `browser.backend: "off"` eksplisit di **8 berkas**. `"off"` adalah
`BACKEND_DISABLED` di `browser_use_cli.py:181` dan memaksa built-in tools.
Perhatikan YAML 1.1 mem-parse `off` tanpa kutip sebagai `False` — Hermes justru
mengharapkan itu (`get_browser_backend()` memetakan `False` -> `BACKEND_DISABLED`),
tapi kita tulis `"off"` berkutip supaya tidak ambigu bagi pembaca.

Dikunci pemeriksaan `[24]` (sekaligus memaksa `cdp_url` tetap loopback), diuji
tiga suntikan: hapus `backend` dari satu profil (cacat asli operator), kosongkan
di config utama, dan set `"browser-use"`. Ketiganya tertangkap.

**Pelajaran:** nilai kosong pada field yang memilih *implementasi* hampir selalu
berarti "sistem yang memilih", bukan "pakai default yang saya bayangkan". Kalau
sebuah config punya field semacam itu, nilai kosongnya harus dibaca dari kode
yang memutuskannya — dan kalau kita ingin perilaku tertentu, field itu harus
diisi eksplisit di **setiap** berkas config, bukan hanya di yang utama.

---

## Arc 15 — Penolakan gateway multiplexer: ini benar, tapi jalurnya lewat dashboard web

Operator menempel keluaran yang muncul **dua kali**:

```
✗ The default gateway is running as a profile multiplexer and already serves
  profile 'worker-x'.
```

**Ini bukan cacat AgentDrop.** Tidak ada satu pun berkas kita yang memanggil
`gateway` dengan `--profile` — diverifikasi dengan grep di `agentdrop`,
`lib/*.sh`, dan `scripts/*.sh`. `agentdrop start` memanggil
`hermes gateway start` polos.

Rantainya ada di sisi Hermes, dan saya telusuri sampai ujung:

1. `hermes_cli/web_server.py:4815`
   ```python
   def _gateway_subcommand(profile, verb):
       return _profile_cli_args(profile) + ["gateway", verb]
   ```
   Dashboard web menyusun perintah gateway **dengan profil yang sedang aktif di
   UI**. Kalau Anda membuka dashboard sebagai `worker-x` lalu menekan Restart
   Gateway, yang dijalankan adalah `hermes --profile worker-x gateway restart`.

2. `hermes_cli/gateway.py:6131` menolaknya. Komentarnya sendiri:
   *"named-profile `hermes gateway run` is always a misconfiguration"*.

3. Label `=== gateway-restart started ===` di log operator juga dari
   `web_server.py:4545` (`"gateway-restart": "gateway-restart.log"`), yang
   memastikan sumbernya dashboard, bukan CLI.

**Muncul dua kali** karena dashboard memanggil aksi restart dari dua tempat —
satu untuk restart, satu untuk memeriksa status sesudahnya
(`web_server.py:4912` dan `4933`).

Alasan penolakannya masuk akal dan bukan sekadar aturan: dua gateway pada satu
profil berarti **dua poller pada satu bot token** dan bentrok port.

### Yang diperbaiki di sisi kita

Bukan kodenya — kodenya sudah benar. Yang diperbaiki adalah **pengetahuan yang
hilang**:

- README sudah melarang `hermes --profile <worker> gateway run`, tapi tidak
  menyebut jalur dashboard. Padahal justru itu yang kena. Ditambahkan, lengkap
  dengan rantai file:barisnya dan alasan pesannya muncul dua kali.
- `agentdrop cmd_start` diberi komentar yang menjelaskan kenapa ia sengaja
  tidak meneruskan `--profile`, supaya orang berikutnya tidak "merapikannya"
  dengan menambahkan flag itu.
- Pemeriksaan `[25]` mengunci polanya di semua shell: `hermes ... --profile ...
  gateway` dalam urutan argumen mana pun. Diuji tiga suntikan — dua urutan
  argumen di `agentdrop`, dan satu di `scripts/burn-in.sh`. Ketiganya tertangkap.

**Pelajaran:** ketika sebuah pesan error menyebut konfigurasi kita sebagai
penyebab, periksa dulu apakah kode kita benar-benar melakukannya. Di sini
tuduhannya mengarah ke `multiplex_profiles`, dan config itu memang kita set — tapi
pemanggil yang salah adalah dashboard Hermes, bukan kita. Memperbaiki config
untuk memuaskan pesan itu justru akan merusak cron.

---

## Arc 16 — `~` di tengah command hook: `expanduser` hanya bekerja di awal string

Laporan operator, dan kali ini diagnosisnya tepat:

```
python3: can't open file '/home/nurkahfi/AgentDrop/~/.agentdrop/agent-hooks/audit-log.py'
```

Path itu membuktikan sendiri apa yang terjadi: `~` **literal** ditempel ke cwd.
Akibatnya besar — hook gagal, dan **seluruh tool browser ikut terblokir**.

### Kenapa `~` tidak ter-expand

56 baris di 7 profil menulis:

```yaml
- command: "python3 ~/.agentdrop/agent-hooks/audit-log.py"
```

Hermes *memang* memanggil `os.path.expanduser` — `agent/shell_hooks.py:555`:

```python
argv = split_command_line(os.path.expanduser(spec.command))
```

Tapi `expanduser` hanya meng-expand `~` di **awal string**. Di sini `~` ada di
token **kedua**, sesudah `python3 `. Jadi ia lolos apa adanya. Lalu
`split_command_line()` memakai `shlex.split` dan `subprocess.Popen` dipanggil
dengan `shell=False` (baris 581) — tidak ada shell yang meng-expand-nya. Python
memperlakukannya sebagai path **relatif terhadap cwd agent**.

Direproduksi di sandbox, kata per kata sama dengan error operator:

```
argv  : ['python3', '~/.agentdrop/agent-hooks/audit-log.py']
rc    : 2
stderr: python3: can't open file '/home/user/AgentDrop/~/.agentdrop/.../audit-log.py'
```

### Perbaikan

Repo tidak bisa hardcode `/home/<user>` — config ini di-commit dan dipakai semua
orang. Jadi dipakai placeholder yang **dirender saat install**:

- config: `python3 __AGENTDROP_HOOK__`
- `lib/30-hermes.sh` merendernya dengan `sed` menjadi `$STATE_DIR/agent-hooks/audit-log.py`
  saat menyalin config ke profil, dan memperingatkan kalau placeholder tersisa.

Diuji dengan menjalankan hook **persis seperti Hermes memanggilnya**
(`shlex.split(os.path.expanduser(cmd))`, `shell=False`, cwd = repo):
versi lama `rc=2` dengan pesan error operator, versi baru `rc=0`.

Dikunci pemeriksaan `[26]`: menolak `~` di command hook (regex diuji terhadap
lima kasus, termasuk `~` di awal string yang memang ditangani `expanduser`), dan
memastikan `lib/30-hermes.sh` benar-benar merender placeholder-nya — tanpa itu
hook akan memanggil berkas bernama harfiah `__AGENTDROP_HOOK__`. Dua suntikan
diuji: kembalikan `~` ke satu profil, dan hapus renderer-nya. Keduanya tertangkap.

Pemeriksaan lama yang mencari teks `audit-log.py` di config juga diperbarui —
tanpa itu ia akan melaporkan 56 error palsu sesudah placeholder masuk.

**Pelajaran:** `expanduser` bukan "shell". Ia hanya menangani satu pola di satu
posisi. Kalau sebuah command disimpan sebagai string dan dijalankan dengan
`shell=False`, **tidak ada** ekspansi `~`, `$VAR`, glob, atau pipe — semuanya
harus sudah berupa nilai literal yang benar. Untuk path yang bergantung mesin,
render saat install; jangan mengandalkan ekspansi runtime.

---

## Arc 17 — Milestone pertama tercapai, dan jawaban atas "kenapa lama"

**Post pertama benar-benar terbit.** worker-x membuka X, menyusun post,
menerbitkannya, dan memverifikasinya muncul di timeline serta halaman profil —
lengkap dengan screenshot dan timestamp. Ini milestone nyata pertama.

Dua hal yang belum sempurna, dan keduanya perlu dicatat jujur:

1. **URL post tidak diambil.** Agent menekan "Copy link" lalu koneksi CDP putus
   sebelum clipboard terbaca. Mengandalkan clipboard adalah pilihan rapuh:
   butuh izin, butuh fokus window, dan tidak meninggalkan jejak di snapshot.
   Yang andal adalah membaca URL dari bilah alamat sesudah membuka permalink —
   itu sudah ada di snapshot, tidak butuh izin apa pun.
2. **CDP putus di tengah task.** `Browser connection lost (CDP WebSocket
   refused)`. Perlu diselidiki terpisah; dugaan awal Chrome-nya restart sehingga
   UUID websocket berubah, tapi ini **belum diverifikasi** — jangan dianggap
   kesimpulan.

### Kenapa lama: diukur, bukan ditebak

Tiga kandidat diperiksa, dan hasilnya tidak seperti dugaan:

| kandidat | hasil | bukti |
|---|---|---|
| 8 hook audit per tool | **bukan** penyebab | diukur: 20.4 ms/panggilan, 20 tool = **0.81 detik** total |
| `record_sessions: true` | **bukan** per-aksi | `browser_tool.py:5007` dipanggil sekali per `task_id`, ada guard `if task_id in _recording_sessions: return` |
| `snapshot_threshold: 20000` | **ini yang nyata** | `browser_tool.py:285-289`: angka ini "per-page budget" yang masuk ke KONTEKS MODEL di setiap snapshot |

Jadi penyebab terbesar yang bisa kita kendalikan adalah **ukuran konteks**, dan
sisanya adalah hal yang memang inherent: setiap aksi browser = satu putaran LLM
penuh (snapshot → putuskan → aksi → verifikasi). Tujuh langkah yang dilakukan
agent berarti sedikitnya tujuh putaran, masing-masing membayar seluruh riwayat
percakapan. Itu biaya arsitektur agent, bukan kemacetan.

**Penyebab yang paling mungkin justru di luar repo:** latency provider. Model
kita `anthropic/claude-sonnet-4` lewat OpenRouter — dua lompatan jaringan
(agent → OpenRouter → Anthropic) sebelum token pertama. Dari sandbox tidak bisa
diukur, jadi ini **dugaan, bukan temuan**.

### Yang diubah

- `snapshot_threshold` 20000 → **15000** (default Hermes) di 8 berkas. Kita
  pernah menaikkannya dengan alasan "halaman dashboard airdrop panjang" **tanpa
  mengukur**. Snapshot yang terpotong tetap disimpan utuh ke `cache/web` dan
  bisa dibaca lewat `read_file`, jadi menaikkan threshold hampir tidak pernah
  jawabannya.
- `record_sessions` true → **false**. Bukan biaya per-aksi, tapi menulis WebM
  per sesi dan menyimpannya 72 jam — disk terbuang untuk rekaman yang tidak
  ditonton siapa pun.
- Komentar lama yang menyuruh "Naikkan untuk halaman dashboard airdrop yang
  panjang" diganti. Komentar itu justru nasihat yang membuat lambat, dan akan
  diikuti orang berikutnya.
- Pemeriksaan `[27]` menolak `snapshot_threshold` di atas 15000. Diuji dengan
  mengembalikan 20000 — tertangkap.

**Pelajaran:** "naikkan limitnya" terasa seperti perbaikan dan tidak pernah
terasa seperti biaya. Untuk angka yang masuk ke konteks model, kenaikannya
dibayar **di setiap putaran**, bukan sekali. Ukur dulu; dan kalau sebuah angka
punya default dari upstream, default itu adalah posisi awal yang sudah
dipikirkan orang lain.

---

## Arc 18 — Bedah klaim arsitektur Manus/OpenManus: mana yang sudah ada, mana yang tidak bisa

Operator membawa analisis teknis mendalam soal arsitektur Manus/OpenManus dan
usulan upgrade. Sebelum menulis kode apa pun, setiap klaim diverifikasi ke
sumber — `hermes-agent` di GitHub dan repo kita sendiri. Hasilnya: **sebagian
besar sudah kita miliki**, satu bertentangan dengan keputusan terkunci, dan
satu klaim kecepatan keliru secara aritmetika.

### Yang SUDAH ada (tidak perlu dibangun ulang)

| klaim analisis | kenyataan di stack kita | bukti |
|---|---|---|
| "Pakai DOM extraction, bukan screenshot tiap step" | `browser_snapshot` memakai **accessibility tree** (ariaSnapshot), teks murni. `browser_vision` adalah tool **terpisah** yang dipanggil hanya saat perlu | `tools/browser_tool.py:11,22`; `browser_snapshot` :4127 vs `browser_vision` :5130 |
| "Gunakan file system sebagai extended context" | Sudah: **truncate-and-store**. Snapshot di atas threshold disimpan utuh ke `cache/web` dan agent membacanya lewat `read_file` | `browser_tool.py:287,297,3741`; deskripsi tool :2556 |
| "Implementasikan KV-cache optimization" | Hermes sudah mengirim `prompt_cache_key` dan melacak `cached_tokens`/`creation_tokens`. Bahkan punya **cache scope yang stabil melintasi rotasi kompresi** (`resolve_prompt_cache_scope` memetakan session id ke akar lineage-nya) | `agent/transports/chat_completions.py:53`, `anthropic.py:230`, `agent/prompt_cache_scope.py:1-13` |
| "Implementasikan recitation (todo.md)" | Toolset `todo` sudah ada dan sudah diaktifkan di 5 dari 7 profil | `tools/todo_tool.py`; `toolsets:` di config profil |
| "Multi-agent dengan Orchestrator" | Sudah: `worker-orchestrator` dengan toolset `delegation` | `config/hermes/profiles/worker-orchestrator/` |

Menulis ulang salah satu dari ini berarti membangun yang sudah ada, dengan
risiko regresi.

### Yang keliru

**"Adopsi Playwright (bukan CDP raw) — lebih cepat."** Ini membalik sebab-akibat.
Hermes menggerakkan browser lewat `agent-browser`, dan mode CDP kita **adalah**
cara Hermes menempel ke Chromium yang sudah jalan. Playwright bukan alternatif
untuk CDP; Playwright sendiri berbicara CDP ke Chromium. Kita memakai CDP bukan
karena tidak tahu ada Playwright, tapi karena **Chrome for Testing harus tetap
satu proses yang memegang ekstensi wallet dan sesi login** — meluncurkan browser
kedua berarti kehilangan keduanya, dan `--load-extension` diabaikan di build
branded sejak Chrome 137.

**"Tool masking (logit masking), bukan removal."** Hermes **tidak punya** logit
masking — `git grep logit_bias|logit_mask` di seluruh repo Hermes: nol
kemunculan. Yang ada adalah `agent.disabled_toolsets`, yaitu **removal**,
dikurangkan paling akhir (`tools_config.py:2600,2899`). Jadi teknik spesifik itu
tidak tersedia bagi kita tanpa memfork Hermes.

**"Bisa bergerak dari 5-15 menit ke hitungan detik."** Ini yang paling perlu
diluruskan, karena bisa mengarahkan seluruh usaha ke tempat yang salah.

Task post X yang berhasil kemarin melakukan 7 langkah. Setiap aksi browser
adalah **satu putaran LLM penuh** (snapshot → putuskan → aksi → verifikasi).
Jadi lantainya:

```
waktu_minimum = jumlah_aksi × latensi_provider
              = 7 × 3..12 detik
              = 21..84 detik
```

"Hitungan detik" hanya tercapai kalau **jumlah putaran** yang dipangkas, bukan
kalau tiap putaran dipercepat. Dan memangkas putaran berarti mengurangi
verifikasi — yang justru alasan agent ini bisa dipercaya. Tidak ada optimasi
arsitektur yang menghapus lantai itu selama satu aksi = satu putaran.

### Yang bertentangan dengan keputusan terkunci

**"CodeAct — agent menulis dan mengeksekusi Python on-the-fly."** Ini
bertentangan langsung dengan:

- `agent.disabled_toolsets: [terminal, code_execution]` di **ketujuh** profil
- K7 (tidak ada tooling bikinan sendiri di jalur wallet)
- guardrail "agent memanggil tool native, tidak pernah mengetik CLI"

Alasannya bukan estetika. Agent ini menggerakkan browser yang **memegang
wallet**. Memberinya kemampuan menjalankan Python arbitrer berarti satu prompt
injection di halaman airdrop — dan halaman airdrop justru permukaan yang
paling sering menyuntik instruksi — bisa berubah menjadi eksekusi kode di mesin
operator, dengan akses ke profil Chrome yang berisi sesi login. Kecepatan yang
ditawarkan CodeAct tidak sebanding dengan itu.

**Kalau operator tetap menginginkan CodeAct, itu keputusan sadar yang harus
diambil eksplisit, bukan diselipkan sebagai "optimasi".**

### Satu hal yang genuinely layak dikerjakan

Dari seluruh analisis, hanya satu yang belum kita punya dan tidak melanggar apa
pun: **memangkas jumlah putaran**, bukan kecepatannya. Konkret:

- `browser_navigate` **sudah** mengembalikan snapshot ringkas (`browser_tool.py:2556`).
  Jadi `browser_snapshot` segera sesudah `navigate` adalah satu putaran yang
  terbuang.
- Skill kita menyuruh verifikasi state sesudah tiap aksi. Untuk aksi yang
  hasilnya terlihat di snapshot berikutnya (mis. mengetik lalu mengirim),
  verifikasinya bisa digabung, bukan dipisah jadi putaran sendiri.

Itu perubahan di **SKILL.md**, bukan di arsitektur. Murah, bisa diukur, dan
tidak menyentuh batas keamanan mana pun.
