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
| **K7** | **TIDAK ADA ekstensi bikinan sendiri.** Keputusan ini tentang *ekstensi*, bukan tentang siapa yang menekan `Confirm` — lihat K14 | Provider non-official terdeteksi sebagai klien asing → risiko di-ban proyek; sebagian dApp menolak provider yang bukan wallet resmi; chain baru butuh `wallet_addEthereumChain` yang sudah ditangani wallet resmi. Konsekuensinya: signing daemon + policy engine ikut dihapus karena tidak punya pemanggil lagi. |
| **K8** | Skrip = **`install.sh` sebagai index** yang me-source `lib/*.sh`, plus **satu CLI `agentdrop`** | Operator bingung dengan 11 skrip yang tumpang tindih. |
| **K9** | Gateway dan agent **satu perintah** | Agent berjalan di atas gateway; memisahkannya membingungkan. |
| **K10** | Private key **tidak pernah** masuk `.env` | `.env` tersalin ke setiap profil → satu key jadi ada di tujuh tempat. Pakai `AGENTDROP_KEY_FILE` (berkas 0600). |
| **K11** | **Docker bukan dependensi** | Camofox satu-satunya pemakainya dan sudah dihapus. Chrome for Testing + Xvfb + noVNC jalan langsung di host. |
| **K12** | Knowledge = direktori `knowledge/` **terpisah**, per domain, dibaca **dan ditulis** agent | Berbeda dari `docs/` yang statis dan ditulis manusia. `knowledge/` dikembangkan agent lewat memory loop. |
| **K13** | Prompt system = **`SOUL.md` per profil**, sudah cukup | Tidak perlu lapisan prompt tambahan. Installer hanya memasangnya ke tempat yang benar. |
| **K14** | **Signing otomatis untuk semua pekerja.** Agent menekan `Confirm`/`Sign`/`Approve` sendiri; kelas `human:wallet` **dihapus** | Keputusan operator 2026-08-29. Aritmetikanya: 10 proyek/hari × 10-20 task chain = ~200 approval/hari — menyerahkannya ke manusia membuat sistem tidak berguna, padahal tujuannya berjalan saat operator offline. **Kunci tetap dipegang manusia** (K10); yang berpindah hanya tombol di popup. Pengganti lapisannya: baca isi popup sebelum menekan, catat setiap approval (fungsi/kontrak/jumlah/chain), `approve` unlimited boleh tapi dicatat untuk revoke, ketidakcocokan halaman↔popup dicatat sebagai peringatan bukan penghenti. **Tetap `human`:** CAPTCHA, 2FA, OTP, KYC. **Tetap dilarang:** private key/seed, dan transaksi yang mengirim dana keluar kecuali task memintanya eksplisit. |

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
  diaktifkan untuk `pekerja-harian`, `pekerja-discord`, `pekerja-x`.
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
  `hermes --profile pekerja-harian cron create` menulis ke
  `~/.hermes/profiles/pekerja-harian/cron/jobs.json`. Gateway yang dinyalakan
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
  1:1 dengan profil yang ada, tapi sambungannya tidak ada: `pekerja-harian` tidak
  pernah menyebut `pekerja-x` (task "buat konten" dikerjakan agent check-in
  tanpa bahan riset); `pekerja-x` tidak membaca `knowledge/projects/<nama>.md`
  hasil analyzer sebelum bikin konten; `pekerja-discord` hanya menulis
  `discord-log.json`, tidak ke `knowledge/`. Ketiganya sudah disambung.
- **Dua variabel orphan sisa subsistem yang dihapus:** `SIGNER_PORT`
  (`lib/00-common.sh`, 0 pemakaian) dan `prof` (`agentdrop cmd_start`, dibaca
  tapi tidak pernah dipakai — jadi `agentdrop start pekerja-harian` diam-diam
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
"✓ pekerja-koordinator — 5 skill" untuk ketujuh profil, tapi direktori tujuan
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
    `pekerja-riset` menulis "VERDICT → dengan confidence eksplisit", tapi
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
sekali. Padahal `browser` ada di `toolsets:` pekerja-x.

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
  profile 'pekerja-x'.
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
   UI**. Kalau Anda membuka dashboard sebagai `pekerja-x` lalu menekan Restart
   Gateway, yang dijalankan adalah `hermes --profile pekerja-x gateway restart`.

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

**Post pertama benar-benar terbit.** pekerja-x membuka X, menyusun post,
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
| "Multi-agent dengan Orchestrator" | Sudah: `pekerja-koordinator` dengan toolset `delegation` | `config/hermes/profiles/pekerja-koordinator/` |

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

---

## Arc 19 — Koreksi: angka "3–12 detik per putaran" itu saya karang

Operator menolak jawaban saya soal kecepatan, dan penolakannya benar.

Saya menulis bahwa task post X punya lantai 21–84 detik karena "7 aksi ×
3–12 detik per putaran". **Angka 3, 6, dan 12 detik itu tidak pernah saya
ukur.** Saya memberinya label optimis/realistis/pesimis supaya terlihat
terukur. Itu persis kegagalan yang berulang kali saya koreksi dari pekerjaan
sendiri: dugaan yang disajikan dengan nada temuan.

Kesimpulan yang dibangun di atasnya ikut gugur. Saya menulis "tidak ada
optimasi arsitektur yang menghapus lantai itu" — padahal kalau Manus
menyelesaikan task kompleks dalam 1–5 menit, lantai itu jelas bukan hukum
alam. Yang benar: **jumlah putaran per task adalah variabel utama**, dan itu
bisa jauh lebih rendah dari yang kita lakukan sekarang.

Fakta yang dilaporkan operator dan tidak saya bantah:
- 1 task sederhana = 15 menit
- 20 menit untuk task connect wallet, dan tombol connect **belum diklik**
- proyeksi 2–6 jam per proyek

Yang belum saya ukur: **ke mana perginya 15 menit itu.** Tanpa itu, "provider
lambat" dan "prosedur kita boros giliran" sama-sama terdengar masuk akal.

### Instrumennya sudah ada, alat bacanya belum

Log audit ternyata sudah menyimpan yang dibutuhkan:
- `ts` di setiap baris (`tools/audit_log.py:156,191`)
- `ms` dari `duration_ms` di setiap `post_tool_call` (`agent-hooks/audit-log.py:119`)

Jadi pemecahannya bisa **dihitung**, bukan diperkirakan:

```
waktu_dalam_tool = jumlah ms pada post_tool_call
waktu_luar_tool  = rentang dinding - waktu_dalam_tool
                   (= model berpikir + round-trip provider)
jumlah putaran   = jumlah pre_tool_call
```

Ditambahkan `agentdrop audit timing`. Diuji dengan TIGA log sintetis yang
masing-masing harus memberi putusan berbeda:

| kasus | putaran | alat menyimpulkan |
|---|---|---|
| 40 putaran, tool 0.8s, jeda 20s | 40 | "putaran banyak DAN waktu di luar tool → pangkas prosedurnya, bukan providernya" |
| 6 putaran, tool 0.9s, jeda 90s | 6 | "sedikit putaran, waktu dominan di luar tool → kandidat kuat latensi PROVIDER" |
| 12 putaran, tool 45s, jeda 3s | 12 | "waktu dominan DI DALAM tool → browser/CDP yang lambat, bukan model" |

Ketiganya benar. Alat ini yang akan menjawab pertanyaan operator dengan angka
dari mesinnya sendiri, bukan dari dugaan saya.

**Pelajaran, dan ini yang kedua kalinya di arc yang berdekatan:** kalau tidak
bisa mengukur, jangan menyajikan angka. Lebih baik mengatakan "saya tidak tahu,
ini alat untuk mengetahuinya" daripada memberi rentang yang terdengar hasil
pengukuran. Operator berhak atas fakta; kalau faktanya belum ada, tugas saya
membuat alat yang menghasilkannya.

---

## Arc 20 — Provider custom hilang tiap install, dan fakta OpenManus dari kodenya

### 1. `install.sh` menghapus provider custom operator

Operator melaporkan dua hal yang ternyata satu akar: provider custom hanya
terdaftar di pekerja-x, dan **ia tidak bisa pull update** karena install ulang
membuang setelan provider di Hermes.

Akar: `lib/30-hermes.sh:27` menyalin `config/hermes/config.yaml` dari repo ke
`~/.hermes/config.yaml` **tanpa syarat**, dan `:64` melakukan hal yang sama ke
tiap profil. Selama model di-hardcode di config repo, setiap `./install.sh`
menimpa apa pun yang sudah disetel operator lewat dashboard.

Perbaikan: model **tidak lagi di-hardcode**. Kedelapan config merujuk `.env`:

```yaml
model:
  default:  "${AGENTDROP_MODEL}"
  provider: "${AGENTDROP_PROVIDER}"
  base_url: "${AGENTDROP_BASE_URL}"
```

Ini aman karena Hermes meng-expand `${VAR}` di config.yaml
(`hermes_cli/config.py:2723-2740` `_expand_env_vars`) dan `.env` di-load dengan
`override=True` **sebelum** config dibaca (`env_loader.py:117,348`). Installer
menyalin config tapi **tidak pernah menyentuh `.env`**, jadi setelan operator
selamat.

**Jebakan yang harus diingat:** variabel yang tidak ada di environment
dibiarkan **verbatim** (`config.py:2767`: `return os.environ.get(inner, raw)`) —
tidak ada sintaks default. Tanpa penjaga, `model.default` jadi string
`"${AGENTDROP_MODEL}"` apa adanya dan setiap worker gagal dengan pesan yang
tidak menyebut penyebabnya. Karena itu `credentials_ensure_model_vars()`
mengisi ketiganya kalau belum ada, dan **dipanggil dari kedua jalur** —
interaktif dan `--non-interactive`. Versi pertama hanya memasangnya di jalur
interaktif; itu akan menghasilkan config rusak pada `--non-interactive` dengan
`.env` lama.

Diuji end-to-end: `.env` lama tanpa `AGENTDROP_*` → terisi default. Lalu diisi
nilai custom (`deepseek/deepseek-chat`, `custom`, `https://api.contoh-saya.dev/v1`)
dan **install ulang** → ketiganya bertahan, 7/7 profil merujuk `.env`.

Validator `[23]` diperbarui: yang diperiksa bukan lagi "provider-nya
openrouter" tapi "rujukannya konsisten dan `.env.example` memberi default".
Tiga suntikan diuji: campur literal dengan rujukan, hapus default dari
`.env.example`, dan kembalikan `provider: "auto"` (regresi arc 13). Ketiganya
tertangkap.

### 2. Fakta OpenManus dari repo aslinya — bukan asumsi

Operator meminta saya memeriksa langsung, dan hasilnya **mengoreksi analisis
yang ia bawa sendiri**.

**Klaim: "1 task di-pecah ke beberapa agent yang berjalan paralel."**

Dari `FoundationAgents/OpenManus`, `app/flow/planning.py:94-131`:

```python
while True:
    self.current_step_index, step_info = await self._get_current_step_info()
    if self.current_step_index is None:
        result += await self._finalize_plan(); break
    executor = self.get_executor(step_type)          # SATU agent
    step_result = await self._execute_step(executor, step_info)   # await
```

**Berurutan, bukan paralel.** `asyncio.gather` di seluruh repo hanya muncul di
tiga tempat, semuanya di level TOOL, bukan agent:
`tool/chart_visualization/data_visualization.py:126,174` dan
`tool/web_search.py:340`. Tidak ada satu pun agent yang di-gather.

`get_executor()` (`planning.py:77-92`) memilih **satu** agent per step. Jadi
arsitekturnya memang multi-agent, tapi eksekusinya serial — sama seperti kita.

**Yang benar-benar membuat OpenManus cepat** ada di `app/agent/toolcall.py:142`:

```python
for command in self.tool_calls:      # BANYAK tool dalam SATU giliran LLM
    result = await self.execute_tool(command)
```

Satu giliran LLM bisa menghasilkan beberapa tool call, dan semuanya
dieksekusi dalam giliran itu. **Di sinilah putaran dipangkas** — bukan dari
paralelisme antar-agent.

### 3. Apakah Hermes bisa begitu? Sebagian

Hermes punya batch planner (`agent/tool_dispatch_helpers.py`), tapi tool yang
boleh berjalan paralel dibatasi `_PARALLEL_SAFE_TOOLS` (baris 48-61):
`read_file`, `search_files`, `web_search`, `web_extract`, `session_search`,
`skill_view`, `skills_list`, `image_generate`, `vision_analyze`, `ha_*`.

**`browser_*` tidak ada di daftar itu.** Aturan di baris 175-176 eksplisit:
*"Anything not in `_PARALLEL_SAFE_TOOLS` and not an opted-in MCP tool →
barrier."* Dan `supports_parallel_tool_calls` hanya berlaku untuk MCP server
(`tools/mcp_tool.py:7698`), bukan tool browser bawaan.

Jadi untuk aksi browser, Hermes memang satu tool per giliran. **Tapi** model
tetap bisa mengeluarkan beberapa tool call sekaligus, dan Hermes
mengeksekusinya dalam satu giliran sebagai segmen sequential — yang menghemat
adalah **giliran LLM-nya**, bukan waktu eksekusi tool. Itu artinya penghematan
terbesar tetap pada hal yang sama: **jangan membuat agent mengambil snapshot
atau verifikasi yang tidak perlu**, karena tiap putaran browser adalah satu
giliran LLM penuh yang tidak bisa diparalelkan.

**Pelajaran:** dua hal yang saya sampaikan sebelumnya perlu dikoreksi. Analisis
operator soal paralelisme antar-agent tidak didukung kode OpenManus — yang
membuat cepat adalah banyak tool per giliran. Dan jawaban saya sebelumnya
("tidak ada optimasi yang menghapus lantai itu") juga salah: lantainya bisa
diturunkan dengan memangkas putaran, persis seperti yang OpenManus lakukan.

---

## Arc 21 — HTTP 402: ceiling native 64.000 token, dan model per worker

### Kegagalan sebenarnya bukan "kehabisan kredit"

Pesan OpenRouter menyebutkan dua hal sekaligus, dan hanya satu yang benar:

```
HTTP 402: You requested up to 64000 tokens, but can only afford 2666.
```

Kredit memang tipis. Tapi **yang membuat permintaan ditolak adalah angka
64.000**, dan angka itu bukan pilihan kita — itu ceiling native model.
`agent/anthropic_adapter.py:175` memberi `claude-sonnet-4` nilai `64_000`.
Config kita tidak menyetel `model.max_tokens` karena komentar di
`config/hermes/config.yaml` berkata:

> "Biarkan tidak diset untuk memakai ceiling native model."

Komentar itu benar secara teknis dan **salah secara praktis**. Dengan ceiling
native, akun ber-kredit terbatas tidak bisa menjalankan agent sama sekali —
bukan lambat, tapi gagal di panggilan pertama. Komentar yang terdengar netral
ternyata adalah konfigurasi yang tidak bisa jalan.

Urutan prioritas dikonfirmasi dari sumber: `agent/agent_init.py:2384` membaca
`model.max_tokens` dari config, dan `agent/anthropic_adapter.py:263`
(`_resolve_anthropic_messages_max_tokens`) **lebih memilih `requested` daripada
`_get_anthropic_max_output(model)`**. Jadi nilai config menang.

Perbaikan: `model.max_tokens: "${AGENTDROP_MAX_TOKENS}"` dengan default 8192 —
cukup untuk satu aksi browser plus penalaran.

### Model per worker

Operator meminta tiap worker punya config sendiri agar model bisa disesuaikan
dengan jenis tugas. Itu benar, dan implementasinya punya satu jebakan.

Hermes **tidak punya sintaks default** untuk `${VAR}`. Variabel yang tidak ada
dibiarkan verbatim (`config.py:2767`), jadi `"${A:-$B}"` akan menjadi string
harfiah. Fallback tidak bisa ditulis di YAML — ia harus diselesaikan saat
install dan dituliskan ke `.env` sebagai nilai konkret.

`credentials_ensure_model_vars()` sekarang dua tingkat:

1. **global** — `AGENTDROP_MODEL|PROVIDER|BASE_URL|MAX_TOKENS`, diisi default
   kalau belum ada
2. **per worker** — `AGENTDROP_MODEL_PEKERJA_QUEST` dst. (7 worker × 4 = 28
   variabel), mewarisi nilai global yang baru dijamin ada

Urutan itu penting. Versi pertama menulis per worker lebih dulu, jadi variabel
global belum ada saat fallback dibaca dan **semua worker mendapat nilai
kosong**. Terlihat dari uji: `AGENTDROP_MODEL_PEKERJA_QUEST=` tanpa nilai.

Diuji end-to-end: `.env` kosong → 28 variabel terisi. Lalu `pekerja-quest`
diubah ke `claude-opus-4` dan `AGENTDROP_MAX_TOKENS_PEKERJA_X=4096`, install
ulang → **keduanya bertahan**, worker lain tetap mengikuti global. 7/7 profil
terpasang merujuk variabelnya sendiri.

Validator `[23]` diperbarui untuk bentuk per worker dan kini **mewajibkan**
`max_tokens`. Empat suntikan diuji: hapus `max_tokens`, hardcode 64000, campur
provider per worker dengan model global, dan hapus default dari `.env.example`.
Semua tertangkap. Suntikan ketiga sempat menghasilkan pesan yang membandingkan
dua string identik (`bukan ${AGENTDROP_MODEL}` padahal yang diharapkan
`${AGENTDROP_MODEL}`) — suffix per worker tidak ikut terbawa ke pesan.
Diperbaiki dan diuji ulang.

**Pelajaran, ketiga kalinya dalam beberapa arc:** komentar yang menjelaskan
mengapa sebuah nilai *tidak* diset perlu diuji sama seriusnya dengan nilai itu
sendiri. "Biarkan default" terdengar aman, padahal default-nya 64.000 dan
akun operator tidak sanggup.

---

## Arc 22 — `CUSTOM_BASE_URL` tidak dibaca Hermes

Operator mengisi `CUSTOM_BASE_URL=https://api.hcnsec.cn/` di `.env` dan
endpoint-nya tidak pernah dipakai. `.env.example` sendiri yang menyuruh begitu:

> "Set model.base_url in config.yaml to the same origin."

Sesudah model dipindah ke `.env` (arc 20), instruksi itu menunjuk ke tempat
yang tidak dibaca apa pun — `config.yaml` sekarang hanya merujuk
`${AGENTDROP_BASE_URL}`.

Dari sumber, kedua variabel itu diperlakukan **berbeda**:

- `hermes_cli/models.py:4080` — `api_key` diambil dari `CUSTOM_API_KEY`
  (lalu jatuh ke `OPENAI_API_KEY`, `OPENROUTER_API_KEY`)
- `hermes_cli/models.py:2836-2839` — base_url diambil dari **config.yaml**:

```python
def _get_custom_base_url() -> str:
    model_cfg = _get_model_config_dict()
    return str(model_cfg.get("base_url", "")).strip()
```

Jadi `CUSTOM_API_KEY` berpengaruh, **`CUSTOM_BASE_URL` tidak**. Endpoint harus
masuk lewat `AGENTDROP_BASE_URL`.

Soal bentuk URL: `/v1` di akhir tidak wajib. `probe_api_models`
(`models.py:5706-5720`) menyusun dua kandidat dan mencoba keduanya:

```python
if normalized.endswith("/v1"):
    alternate_base = normalized[:-3].rstrip("/")
else:
    alternate_base = normalized + "/v1"
candidates = [(normalized, False)]
if alternate_base and alternate_base != normalized:
    candidates.append((alternate_base, True))
```

`https://api.hcnsec.cn/` dan `https://api.hcnsec.cn/v1` dua-duanya bisa;
menuliskan `/v1` hanya menghindarkan satu percobaan jaringan yang gagal.

**Yang tidak bisa diverifikasi dari sini:** sandbox memblokir egress ke host
itu (`curl` mati di `SSL_ERROR_SYSCALL`), jadi daftar model yang tersedia di
endpoint tersebut **tidak diketahui**. `AGENTDROP_MODEL` harus diisi dengan id
model persis seperti yang dilaporkan endpoint — jalankan `hermes model` di
mesin operator untuk melihatnya. Jangan menebak nama model.

### Yang diubah

- `.env.example`: instruksi lama diganti penjelasan bahwa hanya
  `CUSTOM_API_KEY` yang dibaca, beserta jalur yang benar.
- `lib/20-credentials.sh`: memperingatkan operator yang mengisi
  `CUSTOM_BASE_URL` sementara `AGENTDROP_BASE_URL` masih menunjuk OpenRouter,
  lengkap dengan tiga baris yang harus disetel. Diuji dua arah: `.env` operator
  memunculkan peringatan; `.env` yang sudah benar (`provider=custom`,
  `base_url` endpoint) **tidak** memunculkan peringatan palsu dan nilainya
  tidak ditimpa.
- Pemeriksaan `[28]`.

**Pemeriksaan [28] sempat lolos palsu, dan itu layak dicatat.** Versi pertama
hanya mencari `"CUSTOM_BASE_URL" in cred.read_text()`. Menghapus baris
peringatannya tetap lolos, karena nama variabel itu masih muncul di komentar
penjelas. Persis pola lama: *a check that has never been seen to fail is
untested*. Diperketat menjadi dua regex — kode yang membaca variabelnya
(`grep -E "^CUSTOM_BASE_URL=`) dan kode yang mencetak peringatannya — lalu
kedua suntikan diuji ulang dan keduanya tertangkap.

**Pelajaran:** mencari nama sebuah variabel di dalam berkas tidak membuktikan
ada kode yang memakainya. Komentar mengandung nama variabel sama seringnya
dengan kode.

---

## Arc 23 — `pekerja-daftar`, dan pembalikan sebagian batas signing

### Worker yang hilang

Operator benar: tidak ada worker untuk **onboarding awal**. `pekerja-quest`
dibatasi platform quest — SOUL.md-nya menyebut Galxe, Layer3, Zealy, Intract —
sedangkan task nGRND yang ia jalankan ada di **situs proyek sendiri**
(`digitsbt.ngrndrewards.com`) dengan alur register → connect wallet → SBT →
earn. Tidak ada profil yang mengakuinya.

Ditambahkan `pekerja-daftar`:

- `config/hermes/profiles/pekerja-daftar/{config.yaml,SOUL.md}`
- variabel model sendiri: `AGENTDROP_*_PEKERJA_DAFTAR`
- `max_turns: 40` (onboarding lebih pendek dari campaign quest)
- terdaftar di `PROFILES` dan `PROFILE_SKILLS` (`lib/30-hermes.sh`), di daftar
  variabel `.env` (`lib/20-credentials.sh`), dan di rute delegasi
  `pekerja-koordinator`
- skill: `browser-operation browser-burn-in airdrop-intake self-improvement` —
  **`quest-executor` sengaja tidak dipetakan**, karena mencampurnya membuat
  worker ini mengerjakan campaign yang bukan urusannya

Diverifikasi dengan kode Hermes sendiri, bukan dengan membaca berkas:

```
from hermes_cli import profiles
  default          model='anthropic/claude-sonnet-4'  skill=10
  pekerja-daftar   model='anthropic/claude-sonnet-4'  skill=4
  ... (8 profil)
```

`agentdrop run --list` membaca direktori terpasang, jadi otomatis menampilkan
8 profil.

Validator menolak SOUL.md pertama saya karena dua hal yang benar: tidak ada
blok Protokol Browser dan tidak ada aturan anti prompt-injection. Keduanya
disyaratkan untuk profil beralat browser (`validate_config.py:647-651,1583`).
Keduanya disisipkan dari pola profil yang sudah lolos, dengan penguatan khusus
— lihat di bawah.

### Pembalikan sebagian batas signing (keputusan operator)

**Keputusan lama (K7 + WALLET BOUNDARY):** agent menyiapkan sampai popup
wallet muncul, **manusia yang menekan Confirm/Sign/Approve**. Berlaku di semua
profil.

**Keputusan operator sekarang:** `pekerja-daftar` **boleh** menekan
`Confirm`/`Sign`/`Approve` di dalam popup wallet.

Ini penyimpangan sadar, bukan kelalaian. Karena itu aturan penggantinya
dibuat **lebih ketat**, bukan lebih longgar:

Tetap dilarang dan tidak bisa ditawar:
- `approve` unlimited (`uint256 max`) pada token apa pun → `blocked`
- mengirim private key / seed phrase ke halaman mana pun
- transaksi yang mengirim dana keluar, kecuali disebut eksplisit dalam tugas
- menandatangani `permit` / `permit2` / `setApprovalForAll` tanpa membaca
  isinya lebih dulu

Dan dua aturan yang hanya ada karena signing-nya otomatis:

- **Sebelum menekan Confirm, agent menyebutkan di log apa yang disetujui** —
  kontrak, jumlah, jaringan, wallet. Kalau tidak bisa menjelaskannya, ia tidak
  menekannya.
- **Kalau teks halaman dan isi popup wallet tidak cocok, agent berhenti.**

Alasan aturan kedua perlu ditulis eksplisit: worker lain punya lapisan kedua
berupa manusia yang membaca popup. `pekerja-daftar` tidak. Kalau sebuah
halaman berhasil mengubah apa yang agent siapkan, **tidak ada yang
menangkapnya**. Blok anti-injection di SOUL.md-nya menyatakan itu dengan
kalimat sendiri, bukan menyalin alasan worker lain — karena alasannya memang
berbeda.

**Batas lama tetap berlaku di enam profil lain.** Ini pengecualian untuk satu
worker, bukan perubahan yang berlaku umum.

---

## Arc 24 — Provider custom tidak pernah sampai ke worker, dan ukuran sebenarnya dari 29.480 token

### Kenapa `hermes model` tidak berpengaruh ke worker

Operator menyetel DeepSeek lewat `hermes model`, lalu `pekerja-daftar` tetap
meminta `anthropic/claude-sonnet-4` ke OpenRouter. Bukan cache, bukan
kesalahan operator.

`hermes model` menulis ke **profil default**:

- `hermes_cli/main.py:4957` — `cfg["custom_providers"] = providers` lalu
  `save_config(cfg)`
- `hermes_cli/config.py:4023` — docstring `save_config`: *"Save configuration
  to ~/.hermes/config.yaml"*

Profil worker punya `config.yaml` sendiri di `~/.hermes/profiles/<nama>/`.
Tidak ada mekanisme yang menyalin setelan default ke sana. Jadi perintah itu
memang berhasil — ke tempat yang tidak dibaca worker.

Perbaikan: setiap config (utama + 8 profil) sekarang punya blok
`custom_providers` yang dirender dari `.env`. Diverifikasi dengan
`load_config()` Hermes sendiri:

```
model.default    = 'DeepSeek-V4-Flash'
model.provider   = 'custom'
model.base_url   = 'https://api.hcnsec.cn/v1'
custom_providers = [{'name': 'agentdrop-custom', ..., 'api_mode': 'codex_responses',
                     'models': {'DeepSeek-V4-Flash': {}}}]
```

Dan diuji arah sebaliknya: dengan `AGENTDROP_PROVIDER=openrouter`, blok itu
**dibuang** oleh `_render_config` — kalau dibiarkan, config berisi provider
hantu dengan `base_url` kosong.

Bentuk list dipakai karena itulah yang ditulis `hermes model` sendiri.
`config.py:2076` menyebutnya "legacy list form; modern equivalent is
`providers: {}`", tapi memakai dua skema berbeda untuk hal yang sama lebih
buruk daripada memakai bentuk legacy yang konsisten dengan tool-nya.

### `AGENTDROP_API_MODE` — satu variabel yang menentukan berhasil atau tidak

Endpoint operator menawarkan DeepSeek/GLM/Kimi/MiniMax dan memilih mode
`codex_responses` (`/responses`). Kalau config kita membiarkan mode
`auto`, heuristik URL akan memilih `/chat/completions` dan **tool calling
gagal walau modelnya benar**. Variabel ini sekarang eksplisit di `.env`, dan
`.env.example` menjelaskan keempat pilihan beserta akibat salah memilih.

### Ukuran sebenarnya dari 29.480 token

Log operator menunjukkan `Context: 2 msgs, ~29,480 tokens` **sebelum satu tool
call pun**. Itu overhead tetap yang dibayar di **setiap putaran**. Saya ukur
komposisinya, dan hasilnya mengoreksi dugaan saya sendiri:

| sumber | token | catatan |
|---|---|---|
| SOUL.md pekerja-daftar | ~2.290 | 9.162 karakter |
| deskripsi 4 skill | ~171 | **bukan isi skill** — `prompt_builder.py:2014` hanya mengirim `description` frontmatter |
| deskripsi tool browser | ~1.089 | 21 tool |
| **sisanya: Hermes inti** | **~25.930** | tidak bisa kita pangkas lewat config |

Dua hal yang saya duga sebelumnya ternyata salah:

1. **Isi skill tidak masuk prompt.** Saya sempat menghitung 7.891 token untuk
   empat SKILL.md. Hermes memakai *progressive disclosure*
   (`tools/tool_search.py:1-30`): yang dikirim hanya nama + deskripsi pendek,
   dan isi baru dibaca saat skill dipanggil.
2. **Sebagian besar overhead bukan milik kita.** `toolsets.py:31-59`
   `_HERMES_CORE_TOOLS` memuat 29 tool yang **tidak pernah ditunda** —
   komentar di `tool_search.py` eksplisit: *"Core tools ... are never
   deferred. Always-load means always-load."* Enam di antaranya tidak kita
   pakai sama sekali: `terminal`, `process`, `vision_analyze`,
   `image_generate`, `browser_exec`, `text_to_speech`.

Jadi memangkas SOUL.md dan skill **tidak akan** mengubah 29.480 secara
berarti. Yang bisa memangkas adalah mengurangi **jumlah putaran**, dan itu
soal prosedur, bukan ukuran berkas.

**Pelajaran:** saya dua kali menghitung biaya konteks dari ukuran berkas di
repo, dan dua kali pula hasilnya salah karena tidak memeriksa apa yang
benar-benar dikirim. Ukuran berkas bukan ukuran prompt.

---

## Arc 25 — Perintah yang hilang: tidak ada cara menyetel model untuk worker

### Bukti dari log operator bahwa jalurnya sebenarnya berfungsi

Operator melaporkan setup "sama sekali tidak berjalan". Log-nya berkata lain,
dan angka di dalamnya yang membuktikannya:

```
You requested up to 8192 tokens, but can only afford 2666
```

**8192, bukan 64000.** 64000 adalah ceiling native `claude-sonnet-4`
(`anthropic_adapter.py:175`); 8192 adalah `AGENTDROP_MAX_TOKENS` default kita.
Artinya `.env` dibaca, `${VAR}` di-render, dan config terpasang dipakai. Yang
tidak berubah adalah `AGENTDROP_MODEL` dan `AGENTDROP_PROVIDER` — karena
keduanya masih bernilai default.

### Akar sebenarnya: tidak ada perintah untuk menggantinya

`hermes model` menulis ke profil **default** (`main.py:4957` → `save_config` →
`config.py:4023` menulis `~/.hermes/config.yaml`). Worker punya config sendiri.
Dan AgentDrop **tidak menyediakan perintah apa pun** untuk menyetel model —
satu-satunya jalan adalah menyunting `.env` dengan tangan, yang tidak diketahui
operator.

Jadi operator memakai satu-satunya perintah yang terlihat (`hermes model`),
perintah itu berhasil ke tempat yang salah, dan tidak ada pesan apa pun yang
menunjuk penyebabnya.

Ditambahkan **`agentdrop model`**:

- menanyakan provider, base_url, model, api_mode, max_tokens, dan
  `CUSTOM_API_KEY` kalau provider-nya `custom`
- menyamakan variabel per-worker dengan global
- memanggil `_render_all_configs()` sehingga config utama + 8 profil dirender
  ulang tanpa harus menjalankan `./install.sh` penuh
- `agentdrop model --show` menampilkan yang aktif sekarang

Diuji dengan tty buatan (`script -qec`), karena perintah ini membaca stdin dan
tidak bisa diuji lewat pipe:

```
sebelum : default: "anthropic/claude-sonnet-4"
sesudah : default: "Qwen3.8-27B"   provider: "custom"
          base_url: "https://api.hcnsec.cn/v1"   max_tokens: "4096"
```

Dan diverifikasi dengan `load_config()` Hermes sendiri pada tiga profil:

```
pekerja-daftar   Qwen3.8-27B  custom  max=4096  api_mode=chat_completions
pekerja-x         Qwen3.8-27B  custom  max=4096  api_mode=chat_completions
pekerja-quest    Qwen3.8-27B  custom  max=4096  api_mode=chat_completions
```

Satu cacat di versi pertama: kondisi `[[ "${1:-}" == "--show" || $# -eq 0 && ! -t 0 ]]`
membuat `agentdrop model` tanpa argumen selalu mencetak tampilan read-only,
karena `&&` mengikat lebih erat dari `||`. Diperbaiki dengan pengelompokan
eksplisit.

### `agentdrop audit timing` memberi putusan yang menyesatkan

Untuk task yang mati di panggilan API pertama, alat itu tetap mencetak
*"kandidat kuat latensi PROVIDER"* — padahal tidak ada satu pun tool call, jadi
tidak ada yang diukur. Itu mengarahkan diagnosis ke tempat yang salah pada
kasus yang paling sering terjadi.

Sekarang kasus `pre_tool_call == 0` ditangani **sebelum** pemecahan waktu, dan
menyebut kesalahan yang tercatat:

```
tidak ada satu pun tool call — agent tidak pernah sempat bertindak.
Jadi ini bukan soal kecepatan browser atau jumlah putaran; task-nya gagal di awal.
kesalahan tercatat:
  07:07:03  api_request_error  HTTP 402: ... can only afford 2666.
```

Keempat kasus diuji ulang dan semuanya memberi putusan berbeda: 0 tool call →
gagal di awal; 40 putaran → pangkas prosedur; 6 putaran jeda besar → provider;
tool lambat → browser/CDP.

**Pelajaran:** alat diagnosis yang memberi verdict harus diuji pada kasus
*gagal*, bukan hanya kasus *lambat*. Versi pertama hanya diuji pada tiga
bentuk kelambatan, jadi cabang kegagalan tidak pernah terlihat salah.

## Arc 26 — Uji semua worker, dan exit code yang berbohong

Operator meminta: *"persiapkan untuk test berikutnya … tinggal atur dan prepare ke
cronjob, kita akan test semua worker."* Sebelum menyusun paket uji, ada satu
fakta di log operator sendiri yang menentukan seluruh desainnya:

```
✓ pekerja-daftar selesai (rc=0)
```

Padahal task itu mati di panggilan API pertama (HTTP 402) dan tidak memanggil
satu tool pun. `agentdrop:163-168` menilai dari `$?` keluaran
`hermes chat`, dan **rc=0 hanya berarti "sesi selesai", bukan "tugas
berhasil"**. Jadi sinyal yang dipakai selama ini tidak bisa membedakan worker
yang bekerja dari worker yang gagal total.

Karena itu `scripts/test-workers.sh` menilai dari **log audit**, bukan exit
code:

```
LULUS = ada pre_tool_call DAN tidak ada baris level=error
GAGAL = 0 tool call (agent mati sebelum bertindak), atau ada error tercatat
```

Setiap worker mendapat satu task kecil read-only yang sesuai perannya
(SOUL.md); tidak ada yang menyentuh wallet, login, atau posting. Terdaftar
sebagai `agentdrop test-workers [--only <profil>]` — 14 subcommand sekarang.

**Dua bug di kode yang saya tulis sendiri, keduanya ketahuan dari pengujian:**

1. `_sekarang()` memakai `date -u +"%Y-%m-%dT%H:%M:%S.%fZ"`. **GNU date tidak
   mendukung `%f`** — ia mencetak `%f` apa adanya, jadi pembanding string
   menjadi `...:%fZ` dan seluruh filter waktu rusak (hitungan menumpuk antar
   worker: 1, 2, 3, 4…).

2. Setelah `%f` diperbaiki, hitungannya *masih* menumpuk (1, 2, 3, 4, 5, 6).
   Penyebabnya lebih halus: resolusi milidetik terlalu kasar — dua task yang
   berurutan cepat berbagi timestamp yang sama, jadi task kedua mewarisi
   hitungan task pertama. Diganti **selisih jumlah baris** sebelum/sesudah,
   yang tidak bergantung pada presisi jam sama sekali.

**Validator menemukan cacat di dirinya sendiri.** Aturan `hermes chat` di
`tools/validate_config.py:351` memindai semua baris termasuk komentar, jadi
komentar `# rc sengaja TIDAK dipakai … hermes chat mengembalikan 0 walau`
terbaca sebagai pelanggaran — padahal pemanggilan sebenarnya sudah benar
(`chat -q "$T"`). Aturan tetangga di `:364-365` sudah punya pengecualian
komentar; aturan ini belum. Disamakan. Diuji dua arah: pelanggaran nyata di
kode tetap tertangkap (exit 1), komentar lolos.

**Empat kasus diuji dengan `hermes` tiruan yang menulis ke log audit asli:**
semua sukses → 8 lulus 0 gagal (tepat 1 tool call tiap worker); semua gagal →
0 lulus 8 gagal; campuran → 7 lulus 1 gagal dengan worker yang tepat
teridentifikasi; `--only pekerja-x` → 1 lulus. Jalur CLI
(`agentdrop test-workers`) diuji terpisah dari pemanggilan skrip langsung.

**Pelajaran:** sebuah harness uji yang salah akan menghasilkan kesimpulan yang
salah dengan sangat meyakinkan. Harness pertama melaporkan "8/8 lulus" dengan
hitungan 1,2,3…8 — angka yang jelas-jelas salah tapi lolos sebagai "lulus".
**Baca nilainya, bukan hanya verdict-nya.**

**Yang belum bisa dipastikan dari sandbox:** `api_mode` yang benar untuk
endpoint operator (`chat_completions` vs `codex_responses`) tetap tidak bisa
diverifikasi di sini — egress ke `api.hcnsec.cn` mati di TLS. `agentdrop
test-workers` justru alat yang akan menjawabnya di mesin operator: kalau
`api_mode` salah, tool calling tidak jalan dan tiap worker akan tampil sebagai
"0 tool call".

## Arc 27 — Enam koreksi operator, dan dua fakta yang membatalkan sebagian permintaannya

Operator melaporkan enam hal sekaligus. Sebelum menulis kode, semuanya diverifikasi
di repo asli — dan dua di antaranya tidak bertahan setelah diperiksa.

### 1. OpenManus: struktur bersarang itu ADA, tapi bukan sumber kecepatannya

Operator: *"openmanus membagi beberapa agent di bawahnya … setiap agent worker
tidak ambil task itu sendiri dia kerja bareng dengan agent di bawahnya."*

Dibaca ulang di `FoundationAgents/OpenManus`:

- `main.py:17` — `agent = await Manus.create()`. **Satu** agent. Tidak ada pohon.
- Multi-agent hanya lewat `run_flow.py:16`, yang menambah **satu** agent
  (`data_analysis`). `README.md:174` mengonfirmasi: hanya DataAnalysis yang
  terintegrasi.
- `flow/planning.py:77 get_executor(step_type)` memang memilih agent per jenis
  langkah — mekanisme yang operator maksud itu nyata — tapi ia memilih **satu**
  executor per langkah, dan eksekusinya tetap `while True` berurutan.
- Kecepatan ada di `agent/toolcall.py:142` — `for command in self.tool_calls:` —
  **banyak tool call dalam SATU respons model.**

Operator memilih jalur ini (`multitool`). Ditambahkan sebagai
`## Kecepatan: beberapa aksi dalam satu putaran` ke 8 SOUL.md, dengan batas yang
eksplisit: gabung yang independen, pisahkan yang berurutan — karena `ref` dari
`browser_snapshot` batal setelah halaman berubah.

Hermes sudah mendukungnya (`agent/tool_dispatch_helpers.py:201`
`for tool_call in tool_calls`). Yang **tidak** didukung adalah paralelisme
browser: `_PARALLEL_SAFE_TOOLS` (`:48-61`) tidak memuat satu pun `browser_*`, dan
`:175` menyatakan apa pun di luar daftar itu menjadi barrier. Jadi keuntungan di
sini adalah berkurangnya round-trip ke model, bukan eksekusi serentak. Ditulis
terus terang di SOUL.md supaya tidak ada yang menganggapnya paralel.

### 2. Skill BUKAN penyebab lambat — klaim ini saya tolak dengan angka

Operator: *"skill yang kamu buat terlalu banyak file, 1 worker punya lebih dari
2 file skill ini yang membuat worker lama prosesnya."*

Diukur, bukan diperkirakan:

- `agent/skill_utils.py:1175` — `SKILL_PROMPT_DESC_LIMIT = 60`. Deskripsi skill
  **dipotong di 60 karakter**.
- `agent/prompt_builder.py:2014` — yang dikirim hanya `(name, description)`;
  body SKILL.md tidak pernah masuk prompt.
- 4 skill × 60 karakter = 240 karakter ≈ **60 token**.
- Pembanding: `_HERMES_CORE_TOOLS` = **53 tool** yang selalu dikirim dan, menurut
  `tools/tool_search.py:10`, *"never deferred. Always-load means always-load."*

Jadi memangkas skill menghemat puluhan token dari konteks ~29.000. Tidak
dilakukan, dan alasannya dicatat di sini supaya tidak diulang sebagai "sudah
diperbaiki".

### 3. Nama worker → bahasa Indonesia

`worker-orchestrator → pekerja-koordinator`, `worker-analyzer → pekerja-riset`,
`worker-daily → pekerja-harian`, `worker-onboard → pekerja-daftar`,
`worker-quests → pekerja-quest`, `worker-discord → pekerja-discord`,
`worker-monitor → pekerja-pantau`, `worker-x → pekerja-x`.

300 penggantian di 45 berkas + 8 folder, memakai pemetaan **eksplisit** — bukan
`sed s/worker/pekerja/` buta, karena "worker" juga muncul sebagai kata benda umum
("worker apapun") dan menggantinya membabi buta menghasilkan kalimat rusak. Ada
juga `worker_x` bertanda hubung bawah (label status di SOUL.md) yang akan
terlewat oleh pola bertanda hubung.

### 4. Endpoint custom jadi default; lapisan per-worker DIHAPUS

Ini akar dari keluhan *"custom di env tapi tidak pernah dipakai"*. Mekanisme
kegagalannya:

`config.yaml` tiap profil merujuk `${AGENTDROP_MODEL_WORKER_X}`. Variabel itu
**tidak pernah ada di `.env.example`** — hanya dibuat saat install. Kalau satu
langkah terlewat, Hermes membiarkannya verbatim (`config.py:2767`), jadi
`model.default` menjadi string `"${AGENTDROP_MODEL_WORKER_X}"` apa adanya.
Endpoint terpasang di config tapi tidak pernah dipakai, **tanpa error yang jelas.**

40 rujukan per-worker diganti ke variabel global; blok per-worker dihapus dari
`lib/20-credentials.sh`; `.env.example` default ke `custom` /
`https://api.hcnsec.cn/v1` / `Qwen3.8-27B` / `chat_completions`.

**Bug ikutan yang ketahuan dari pengujian:** `AGENTDROP_API_MODE` dan
`AGENTDROP_PROVIDER_NAME` tidak ikut dijamin oleh `credentials_ensure_model_vars`,
padahal keduanya dikonsumsi `_render_config` (`lib/30-hermes.sh:55`). Akibatnya
`api_mode` ter-render sebagai `"auto"` — dan `"auto"` **tidak pernah resolve**
sebagai provider (`hermes_cli/auth.py:2268` menutup jalur config-provider).
Diperbaiki; diverifikasi `api_mode='chat_completions'` di 4 profil lewat
`load_config()` Hermes asli.

### 5. Telegram tersambung ke agent default — dan sekarang bisa mendelegasikan

Penyebabnya dua lapis, keduanya terverifikasi:

1. `hermes_cli/profiles.py:1105 profiles_to_serve(multiplex=True)` — *"the
   default profile is always served"*. Profil **default** yang memegang
   `TELEGRAM_BOT_TOKEN` dan menjawab Telegram, bukan pekerja.
2. Config utama tidak punya toolset `delegation` (hanya disebut di komentar),
   jadi tidak ada `delegate_task` — **tidak ada jalan** dari Telegram ke pekerja
   mana pun. Ia mengerjakan semuanya sendiri.

Diperbaiki: `delegation` ditambahkan ke toolset root, `terminal` dibuang dari
root (CodeAct ditolak operator dan berlaku di semua profil — menaruhnya hanya di
root berarti justru profil yang paling sering dipakai punya kemampuan yang
dilarang), `disabled_toolsets: [terminal, code_execution]` ditambahkan ke root,
dan `SOUL.md` root ditulis ulang dari pelaksana menjadi koordinator dengan tabel
delegasi.

`delegation.max_spawn_depth: 2` + `orchestrator_enabled: true` — inilah struktur
bersarang yang operator minta, dan Hermes memang mendukungnya
(`cli-config.yaml.example:1539-1541`, mensyaratkan `role="orchestrator"` pada
perantara).

Dibuktikan dengan kode Hermes sendiri, bukan dengan membaca config:
`_get_platform_tools()` + `toolsets.TOOLSETS` → `delegate_task` **ADA** di profil
default dan semua pekerja; `terminal` dan `execute_code` **tidak ada**.

### Validator: 273 → 285 checks

`[31]` menolak variabel model per-worker di config mana pun. `[32]` menolak
config root tanpa `delegation`, dengan `terminal`, atau tanpa
`disabled_toolsets`. Keempat cabang diuji dengan injeksi nyata: var per-worker
dikembalikan → tertangkap; `delegation` dibuang → tertangkap; `terminal`
dikembalikan → tertangkap; `disabled_toolsets` dikosongkan → tertangkap.

**Cacat di aturan baru saya sendiri:** blok `[31]/[32]` pertama ditulis langsung
di dalam `main()` yang tidak mendeklarasikan `global checks` →
`UnboundLocalError` saat validator sampai di ringkasan. Dipindah ke fungsi
tersendiri mengikuti pola `[30]`. Pesan `[31]` juga salah mencetak
`$AGENTDROP_MODEL` (kurang `${}`) karena `m.group(0)[2:]` membuang `${` —
diperbaiki dan diuji ulang dengan injeksi.

**Pelajaran:** validator yang saya tulis untuk mencegah regresi pun mengandung
cacat yang hanya terlihat saat dijalankan sampai akhir. Menambah aturan tidak
cukup; aturannya harus dijalankan dan dilihat gagal.

## Arc 28 — Signing otomatis untuk semua pekerja (K14)

Operator membatalkan batas signing: *"disini agent kerjakan task sampai selesai
tidak ada human approve … jika sehari ada 10 project dan masing punya task chain
10-20 maka total sehari saya approve 200 kali, tidak bisa ditinggal. Saya bangun
ini agar agent tetap work meski saya offline."*

Aritmetikanya yang menentukan, bukan preferensi: **~200 approval sehari** membuat
sistem tidak berguna kalau setiap popup diserahkan ke manusia, padahal tujuannya
berjalan saat operator offline.

### K7 tidak dilanggar — dan pembedaan ini penting

K7 melarang **ekstensi bikinan sendiri**. Itu tentang *ekstensi*, bukan tentang
siapa yang menekan `Confirm`. Selama arc 12-27 keduanya tercampur: "tidak ada
ekstensi sendiri" ikut dibaca sebagai "manusia yang menandatangani". K7 sekarang
diklarifikasi di tempatnya, dan keputusan baru ini jadi **K14**.

Yang berpindah hanya **tombol di popup**. Kunci tetap di dalam wallet dan tidak
pernah dipegang agent (K10 tetap berlaku).

### Tiga keputusan operator, lewat pertanyaan eksplisit

Saya tidak memutuskan sendiri, karena ketiganya mengubah isi aturan:

1. **`approve` unlimited (`uint256 max`) → BOLEH.** Banyak dApp airdrop memang
   memintanya dan menolak jumlah terbatas. Larangan lama justru akan
   menghentikan agent di situs-situs itu — persis interupsi yang ingin
   dihilangkan. Syaratnya: catat token dan spender-nya supaya bisa di-revoke.
2. **Halaman ≠ popup → CATAT, TERUS JALAN.** Ketidakcocokan teks halaman dengan
   isi popup adalah sinyal situs mencurigakan, dan itu **wajib diteruskan ke
   operator** — tapi bukan alasan berhenti di tengah campaign.
3. **CAPTCHA / 2FA / OTP / KYC → TETAP `human`.** Agent tidak memecahkan
   tantangan verifikasi. Ini satu-satunya kelas yang masih menumpuk menunggu
   operator, dan jumlahnya harus jauh lebih kecil dari sebelumnya.

### Taksonomi berubah: `siapkan` / `human:wallet` → `wallet`

Kelas lama `siapkan` ("agent menyiapkan sampai popup, operator menekan") dihapus
dan diganti `wallet` ("agent kerjakan sampai selesai"). Berlaku di
`pekerja-quest`, `pekerja-harian`, `pekerja-daftar`, `pekerja-koordinator`, dan
skill `quest-executor`, `daily-executor`, `airdrop-intake`.

`pekerja-daftar` bukan lagi pengecualian — dulu ia satu-satunya yang boleh
signing, sekarang semua boleh, jadi bagian "ini penyimpangan sadar dari worker
lain" di SOUL.md-nya ditulis ulang.

### Pengganti lapisan pemeriksaan manusia

Karena tidak ada orang kedua yang membaca ulang, risikonya **tidak hilang — ia
dipindahkan ke kualitas catatan agent**. Karena itu catatan wajib, bukan
opsional:

- baca **isi popup** sebelum menekan (halaman bisa berbohong, popup tidak)
- catat **setiap** approval: fungsi, kontrak/spender, jumlah, chain
- popup tertutup **bukan** bukti berhasil — verifikasi status/tx hash/saldo
- popup tidak muncul = kegagalan untuk dilaporkan, bukan diakali

Yang tetap dilarang tanpa pengecualian: private key / seed phrase dalam bentuk
apa pun; transaksi yang **mengirim dana keluar** kecuali task memintanya
eksplisit (approve bukan transfer).

### Validator: 285 → 303

`[33]` memindai 8 SOUL.md + 10 SKILL.md untuk **pola yang bertindak** — tujuh
regex: "berhenti di situ", "stop di situ", "operator yang menekan", "operator
yang menandatangani", "manusia tanda tangan", "berhenti dan menyerahkan", "tidak
pernah menandatangani".

Sengaja mencari pola, bukan string `human:wallet`: kelas itu bisa dihapus dari
tabel sementara kalimat "berhenti di situ" tetap ada di bawahnya, dan pencarian
nama saja akan lolos. Diuji dengan injeksi — kalimat lama dikembalikan ke
`daily-executor`, aturan menangkapnya, lalu dipulihkan.

### Verifikasi

Dijalankan, bukan dibaca: `tools/validate_config.py` → **303 checks, SEMUA
LOLOS**. Install ulang → 8 profil terpasang. SOUL.md **ter-render** di
`~/.hermes/profiles/` diperiksa: aturan signing baru ada di keempat profil yang
disentuh, larangan lama nol. `quest-executor` terpasang punya langkah 3 baru dan
nol larangan lama. `agentdrop test-workers` → **8 lulus, 0 gagal**.

**Yang tidak bisa diverifikasi dari sandbox:** apakah `agent-browser` (binari
eksternal, bukan bagian repo Hermes) benar-benar bisa menjangkau popup ekstensi
wallet lewat CDP. Popup ekstensi adalah target terpisah di Chrome, dan saya
tidak punya Chrome maupun display di sini. `browser_extension_router` di Hermes
memang ada, tapi **off secara default** dan butuh gateway browser-controller —
bukan jalur yang kita pakai. **Ini hanya bisa dipastikan dengan menjalankan satu
task `connect wallet` sungguhan di mesin operator.** Kalau popup tidak
terjangkau, gejalanya spesifik: agent melaporkan "popup tidak muncul" pada task
yang seharusnya memunculkannya.

## Arc 29 — Kendali dari Telegram: pintasan pekerja, model, dan sesi

Operator meminta: *"telegram bot agar saya bisa atur dan ganti-ganti worker di
telegram dan juga provider, model, dan ketika ganti worker muat sesi baru."*

### Empat jalan buntu, diverifikasi di repo Hermes sebelum menulis apa pun

Sebelum membangun, saya cari apakah Hermes sudah menyediakannya. Tidak:

1. **`/profile` hanya MELIHAT** (`gateway/slash_commands.py:355` — "show the
   profile serving this source and its home"). Tidak ada perintah ganti profil.
2. **`gateway.profile_routes`** (`gateway/profile_routing.py`) merutekan
   chat → profil, tapi dibaca **saat gateway start** (`gateway/run.py:29064`
   membaca `config.profile_routes`). Menggantinya butuh restart.
3. **`/p/<profile>/`** hanya untuk HTTP API
   (`gateway/platforms/api_server.py:35-36`), bukan Telegram.
4. **Perintah `/` yang tidak dikenal tidak diteruskan ke model** — gateway
   membalas "Unknown command" (`gateway/run.py:18847`). Jadi membuat perintah
   sendiri lewat teks biasa tidak mungkin.

### Yang dipakai: mekanisme resmi skill-perintah

Hermes mendaftarkan **setiap skill sebagai perintah `/nama-skill`**
(`agent/skill_commands.py`, dipanggil dari `gateway/run.py:18749`). Ini jalur
resmi, bukan akalan. Jadi pintasan dibangun sebagai skill tipis:

`/riset` `/harian` `/quest` `/daftar` `/x` `/discord` `/pantau` — masing-masing
mendelegasikan ke pekerja yang sesuai — plus `/panggil-pekerja` yang memuat
protokol lengkapnya (peta nama, cara verifikasi, batas). Ketujuh pintasan
sengaja **tidak menduplikasi** protokol itu; mereka menunjuk ke sana, supaya
keduanya tidak bisa berbeda.

Semua dipetakan ke `pekerja-koordinator`, karena dialah yang menghadap Telegram.

**Diverifikasi dengan kode Hermes asli, bukan dengan membaca config:**
`get_skill_commands()` mengembalikan 18 perintah, dan
`resolve_skill_command_key()` me-resolve **8/8** pintasan — termasuk bentuk
underscore `/panggil_pekerja`, karena Telegram melarang tanda hubung di nama
perintah bot (`agent/skill_commands.py:649-650`).

### Provider/model: pakai `/model` bawaan, dan satu jebakan yang harus diketahui

Operator memilih `/model` bawaan. Ia memang sudah ada
(`hermes_cli/commands.py:257`) dan **sadar profil** di gateway multiplex
(`gateway/slash_commands.py:1775-1778` menyelesaikan `config_path` dalam scope
profil yang melayani chat) — jadi ia menulis ke profil yang benar, bukan ke
profil default.

**Jebakan yang saya temukan saat memverifikasi:** `/model --global` menulis
`model_cfg["default"] = result.new_model` langsung ke config.yaml
(`gateway/slash_commands.py:2397`), yang **menimpa rujukan `${AGENTDROP_MODEL}`**
di profil itu. Setelah itu `agentdrop model` di terminal tidak lagi menjangkau
profil tersebut. Itu bukan bug Hermes — itu memang arti "persist to config" —
tapi operator perlu tahu profil itu lepas dari `.env`. Dicatat di skill.

Tanpa `--global`, ganti model hanya berlaku untuk sesi itu dan disimpan di
session DB (`:2283`); bertahan setelah restart gateway tapi tidak menjangkau
pekerja lain.

### Sesi

Operator memilih **sesi per pekerja yang bertahan**. Ini sudah otomatis:
`delegate_task` memberi tiap subagent `task_id` sendiri
(`tools/delegate_tool.py:165-177`), jadi memanggil pekerja yang sama dua kali
melanjutkan konteksnya. `/new` bawaan Hermes (`gateway/slash_commands.py:145` →
`reset_session()`) tersedia kalau operator ingin mulai bersih.

### Validator: 351 → 367

`[34]` memastikan tiap pintasan (a) punya `SKILL.md`, (b) terdaftar di array
`SKILLS`, dan (c) dipetakan ke `pekerja-koordinator`. Ketiga cabang diuji dengan
injeksi nyata: buang dari `SKILLS` → tertangkap; buang dari `PROFILE_SKILLS` →
tertangkap; hapus folder skill → tertangkap.

**Cacat di aturan baru saya sendiri, dan jenisnya baru:** versi pertama
mencocokkan nama skill **per baris** dengan `re.M`, padahal array bash
`SKILLS=( ... )` terpecah empat baris. Hasilnya **positif palsu** — lima dari
delapan pintasan dilaporkan "tidak terdaftar" padahal ada. `riset` lolos hanya
karena kebetulan berada di awal baris. Diperbaiki dengan membaca seluruh isi
array lalu memecahnya jadi token.

Ini kebalikan dari cacat yang biasanya saya buat: bukan lolos palsu, tapi
**gagal palsu** — dan keduanya sama berbahayanya, karena yang satu membuat
operator memperbaiki hal yang tidak rusak.

### Verifikasi

`tools/validate_config.py` → **367 checks, SEMUA LOLOS**. Install ulang →
koordinator punya 13 skill, total 18 perintah terdaftar.
`resolve_skill_command_key()` → **8/8**. `agentdrop test-workers` → **8 lulus,
0 gagal**.

**Yang tidak bisa diverifikasi dari sandbox:** perilaku nyata perintah ini di
Telegram. Resolusi perintah sudah terbukti lewat kode Hermes, tapi apakah
gateway benar-benar meneruskannya ke koordinator, dan apakah `delegate_task`
menjawab dalam waktu yang wajar lewat chat — itu hanya bisa dipastikan dengan
bot yang berjalan di mesin operator.

## Arc 30 — "Semua command unknown di telegram": cache skill tidak di-refresh

Operator melaporkan **semua** pintasan Arc 29 dibalas "Unknown command". Saya
sudah menandai risiko ini di akhir Arc 29 sebagai hal yang tidak bisa diverifikasi
dari sandbox — tapi menandainya bukan berarti menemukannya. Penyebabnya sekarang
ketemu, dan **bukan** di skill-nya.

### Mekanisme yang benar, dan satu syarat yang terlewat

Skill memang terdaftar sebagai perintah `/nama-skill`, dan itu sudah diverifikasi
(Arc 29: 8/8 resolve). Tapi ada syarat yang baru terlihat saat gejalanya muncul:

```
agent/skill_commands.py:550  get_skill_commands()
    is_fresh = bool(commands)
               and _skill_commands_platform == current_platform
               and _skill_commands_home     == current_home
```

Cache hanya di-refresh kalau **platform** atau **HERMES_HOME** berubah —
**bukan kalau isi folder skill berubah** (`:565-568`).

**Dibuktikan, bukan disimpulkan:** skill baru ditambahkan ke `~/.hermes/skills`
saat proses hidup, lalu `resolve_skill_command_key()` dipanggil lagi — tetap
`None`. 18 perintah sebelum, 18 sesudah.

Jadi: `install.sh` menyalin skill baru, tapi gateway yang **sudah hidup** tidak
pernah melihatnya. Perintah itu baru ada setelah gateway di-restart.

Yang membuat ini lolos dari Arc 29: semua pengujian saya menjalankan scanner
dalam **proses baru**, yang selalu memindai ulang dari disk. Gateway operator
adalah proses **lama** yang masih memegang cache. Pengujian saya menguji hal
yang benar dengan cara yang tidak mewakili keadaan sebenarnya.

### Perbaikan

1. **`agentdrop status` bagian `[5] Pintasan Telegram`** — memisahkan dua
   kegagalan yang gejalanya identik di Telegram:
   - skill belum tersalin → `./install.sh`
   - skill ada tapi gateway belum di-restart → `agentdrop stop && agentdrop start`

   Tanpa pemisahan ini operator tidak punya cara membedakan keduanya.

2. **`install.sh` menyuruh restart** kalau gateway sedang jalan, dengan alasan
   mekanismenya tertulis — bukan sekadar "restart dulu".

### Cacat di pemeriksaan baru saya sendiri, dan jenisnya berbahaya

Versi pertama memakai `stat -c %Y "/proc/<pid>"` sebagai waktu mulai proses.
**Itu waktu AKSES, bukan waktu mulai** — berubah setiap kali ada yang membaca
direktori itu. Dibuktikan: proses yang baru dimulai dan berkas yang disentuh
dua detik sebelumnya menghasilkan angka yang sama.

Akibatnya pemeriksaan **selalu** menyimpulkan "gateway hidup setelah skill
terpasang" — termasuk pada kasus yang justru harus ditangkap. Ini lolos satu
putaran uji penuh karena saya mengujinya hanya pada kondisi yang seharusnya
lulus.

Ketahuan saat saya menjalankan kondisi sebaliknya. Diganti `ps -o lstart=`, lalu
**keempat** kondisi diuji:

| Kondisi | Hasil |
|---|---|
| skill terpasang, gateway mati | ✓ + peringatan nyalakan |
| gateway hidup **sebelum** skill (kasus operator) | ✗ + perintah restart |
| gateway hidup **setelah** skill | ✓ |
| skill belum terpasang | ✗ + `./install.sh` |

### Validator: 367 → 370

`[35]` menegakkan tiga hal: `install.sh` memuat perintah restart, `verify.sh`
punya bagian Pintasan Telegram, dan **tidak** memakai pola `stat -c %Y "/proc/`
yang sudah terbukti salah. Ketiga cabang diuji dengan injeksi nyata.

Aturan ketiga itu ada justru karena cacatnya sendiri lolos satu putaran —
mengunci pelajaran, bukan hanya perbaikannya.

### Verifikasi

`tools/validate_config.py` → **370 checks, SEMUA LOLOS**, `[35]` diuji tiga
injeksi. Empat kondisi `agentdrop status` diuji dan hasilnya sesuai tabel.
`agentdrop test-workers` → **8 lulus, 0 gagal**.

**Tetap tidak bisa diverifikasi dari sandbox:** apakah setelah restart gateway
benar-benar meneruskan `/riset` ke koordinator dan `delegate_task` menjawab
lewat Telegram. Resolusi perintah sudah terbukti; pengirimannya belum.

## Arc 32 — "Agent menentang instruksi, bilang tidak bisa login": prompt-nya memang melarang

Operator menguji `agentdrop test-workers` di mesinnya dan melaporkan empat hal:
masih lambat, popup tidak terbuka, **agent menentang instruksi dan bilang tidak
bisa login / connect wallet**, dan terlalu banyak tool serta skill yang dirender
sekaligus. Ia juga menilai `install.sh` terus menambah skill tanpa menghapus
yang lama, dan tidak ada cache.

Tiga dari lima penilaian itu **saya verifikasi dan ternyata salah** — tapi
gejala yang melatarinya nyata, dan penyebabnya berbeda dari yang diduga.

### Penyebab #1 — `login` memang tercatat sebagai tugas manusia

Ini bukan halusinasi model. `login` tertulis sebagai kelas `human` di **sembilan
tempat berbeda**:

```
pekerja-quest/SOUL.md:72        `human` — ... CAPTCHA, 2FA, login, OTP SMS/email
pekerja-harian/SOUL.md:65       Jangan mencoba login sendiri
pekerja-koordinator/SOUL.md:120 Butuh manusia (login, CAPTCHA, KYC, approval wallet)
pekerja-koordinator/SOUL.md:205 Connect Twitter -> human:oauth (operator login via noVNC)
quest-executor/SKILL.md:69,73   `human` | KYC, verifikasi identitas, login
browser-operation/SKILL.md:238  Butuh manusia — login, CAPTCHA, 2FA, KYC, approval wallet
browser-operation/SKILL.md:303  OAuth → STOP. Butuh login akun operator
daily-executor/SKILL.md:67      Jangan coba login sendiri
airdrop-intake/SKILL.md:63,134  kelas `human:oauth`
```

Agent tidak "menentang instruksi" — ia **mematuhi** instruksi yang salah. Akun
yang dipakai memang dibuat untuk agent dan kredensialnya tersedia, jadi login,
signup, dan OAuth adalah pekerjaannya. Yang tetap milik manusia hanya empat:
CAPTCHA, 2FA, OTP, dan KYC/verifikasi identitas.

Baris `koordinator:120` dan `browser-operation:238` sekaligus **melanggar K14** —
keduanya masih menyebut `approval wallet` sebagai titik henti manusia, padahal
Arc 28 sudah mencabutnya. Aturan validator `[33]` tidak menangkapnya karena
pola-pola yang dicocokkan berbeda dari kalimat ini.

**Perbaikan:** sembilan tempat itu ditulis ulang, dan setiap SOUL.md diberi
bagian baru `## Akun ini milik saya` yang menyatakan secara tegas bahwa login
adalah tugas agent — ditutup dengan: *"Kalau saya mendapati diri menulis 'saya
tidak bisa login' — itu salah."* Pernyataan tegas, bukan sekadar tidak adanya
larangan, karena model jauh lebih patuh pada yang pertama.

### Penyebab #2 — 53 tool di setiap putaran

Operator benar bahwa terlalu banyak tool dirender. Penyebabnya satu baris di
setiap profil: `toolsets:` dimulai dengan `hermes-cli`, dan
`toolsets.py:478-481` memetakannya ke `_HERMES_CORE_TOOLS` = **53 tool**,
termasuk **14 tool kanban**, **4 tool Home Assistant**, `text_to_speech`,
`image_generate`, `session_search`, `cronjob`, dan `computer_use`. Tidak satu
pun dipakai airdrop farming; semuanya masuk skema tool di setiap putaran.

Diganti dengan toolset sempit, dan **toolset dipakai sebagai penegak batas**:

| Profil | Sebelum | Sesudah | Yang dicabut |
|---|---|---|---|
| koordinator | 53 | **13** | `browser` (13) — ia tidak boleh mengeksekusi |
| 7 worker | 53 | **25** | `delegation` — mereka leaf |

Dihitung dari pemetaan `toolsets.py` yang asli, bukan perkiraan. Sekarang
koordinator **secara struktural** tidak bisa membuka halaman, dan worker
**secara struktural** tidak bisa mendelegasikan — batas itu tidak lagi bergantung
pada kepatuhan model terhadap kalimat di SOUL.md.

### Penyebab #3 — pool skill global

`SKILLS=()` memuat **semua 18** skill dan disalin ke `~/.hermes/skills`. Itu
adalah HERMES_HOME profil **default**, dan profil default-lah yang memegang
`TELEGRAM_BOT_TOKEN` (`profiles.py:1105`). Jadi setiap pesan Telegram membuat
koordinator melihat 18 prosedur — termasuk `quest-executor` yang bukan urusannya.

Sekarang: pool global dihapus, HERMES_HOME utama hanya membawa milik koordinator,
dan tiap worker membawa **3** skill (koordinator 11). `browser-burn-in` tidak
dipetakan ke worker mana pun — itu alat uji pemasangan, bukan prosedur kerja.

### Dua penilaian operator yang tidak terbukti

Dicatat supaya tidak "diperbaiki" di arc berikutnya:

1. **"install.sh terus menambah skill tanpa menghapus"** — tidak benar.
   `lib/30-hermes.sh:188` melakukan `rm -rf "$dst/skills"` sebelum menyalin, dan
   `:204` melakukan hal yang sama untuk home utama. Validator sudah punya aturan
   yang menuntut kedua baris itu. Yang terlihat sebagai "13 skill di koordinator"
   adalah **pemetaan yang memang memberi 13**, bukan tumpukan.
2. **"Tidak ada cache"** — Hermes punya **tiga** lapisan cache:
   `_SKILLS_PROMPT_CACHE` (`prompt_builder.py:1512`, LRU dalam proses) +
   **snapshot disk** `.skills_prompt_snapshot.json` yang bertahan lintas restart
   (`:1773`, path di `:1520`) + `_cached_system_prompt_static` (`system_prompt.py:1047`).

   Tapi keluhan di baliknya **sah**, hanya penyebabnya berbeda: SOUL.md
   menyuruh *"Baca skill `browser-operation` sekali di awal sesi"*, dan skill itu
   **12.499 karakter**. Sekali dibuka, seluruhnya masuk riwayat dan ikut
   terkirim ulang **di setiap putaran sesudahnya**. Enam aturan intinya sudah
   tertulis inline di SOUL.md, jadi kewajiban itu pemborosan murni. Sekarang
   `browser-operation` dinyatakan **rujukan, bukan bacaan wajib**.

### Popup wallet — bisa dijangkau, dan Arc 31 salah soal ini

Arc 31 menyimpulkan popup wallet "harus kode" — perlu plugin. **Itu keliru.**
Tool `browser_cdp` sudah ada di toolset kita (lewat `_HERMES_CORE_TOOLS`) dan
menerima `target_id`:

```
tools/browser_cdp_tool.py:266-273
  When ``target_id`` is provided, we call ``Target.attachToTarget`` with
  ``flatten=True`` ... then send ``method`` with that ``sessionId``.
```

Jadi `Target.getTargets` → saring `chrome-extension://` → `Runtime.evaluate`
dengan `target_id` itu. Prosedurnya sekarang tertulis di
`skills/browser-operation/SKILL.md`, lengkap dengan peringatan bahwa ia **belum
diuji pada wallet sungguhan** (sandbox tidak punya Chrome).

Yang juga diperbaiki: `browser-operation:306` selama ini menulis *"Popup wallet
extension tidak bisa dikendalikan lewat DOM"* — klaim usang yang membuat agent
menyerah sebelum mencoba.

### `agentdrop` tidak pernah memeriksa apakah Chrome hidup

Operator menjalankan `test-workers` dengan task "buka https://…", padahal tidak
ada Chrome yang memegang port CDP. Tidak ada satu pun pesan yang menunjuk
penyebabnya — yang terlihat hanyalah worker yang "lambat". Ditambahkan
`browser_preflight()` di `lib/40-browser.sh`, dipanggil dari `agentdrop run` dan
`agentdrop test-workers`. Sengaja **peringatan**, bukan berhenti keras:
koordinator memang tidak punya tool browser. Kedua kondisi diuji.

### Validator 370 → 370 checks, dua aturan baru, satu ditulis ulang

- **`[36]` Login/OAuth bukan kelas `human`.** Versi pertama mencari "login"
  berdekatan dengan CAPTCHA/2FA/OTP/KYC dan **menembak lima baris yang tidak
  melarang apa pun** — enum status, catatan tentang tab, bahkan baris yang
  justru menulis "Login BUKAN `human`". Persis cacat aturan `[34]` dulu. Ditulis
  ulang jadi **pemeriksaan positif** (tiap SOUL.md wajib menyatakan login adalah
  tugas agent) + **pola negatif sempit** yang tidak ambigu. Diuji empat injeksi
  **dan** satu uji false-positive: 0 error pada baris yang sah.
- **Aturan batas toolset.** `hermes-cli` ditolak; koordinator wajib tanpa
  `browser` dan wajib dengan `delegation`; worker wajib dengan `browser` dan
  wajib tanpa `delegation`. Empat injeksi, semuanya tertangkap.
- **Duplikat toolset.** YAML menerima daftar duplikat tanpa error. Pernah
  terjadi: `todo` dan `delegation` terdaftar dua kali karena suntingan menyisip
  di atas baris komentar. Diuji injeksi.

### Cacat saya sendiri di arc ini

1. **Menambah skill `koordinator` ke `SKILLS=()` tanpa memeriksa direktorinya
   ada.** Validator yang menangkap, bukan saya.
2. **`err(f"...{sebut}...")` padahal variabelnya `sebab`** → `NameError`. Dan
   yang lebih buruk: **grep saya menyembunyikan crash itu**, sehingga satu
   putaran terlihat "lolos" padahal validator mati. Sudah keenam kalinya kelas
   kesalahan ini muncul. **Baca ekor keluaran, jangan grep lalu percaya.**
3. **Dua aturan validator menghasilkan false positive** sebelum diperketat.

### Verifikasi

`tools/validate_config.py` → **370 checks, SEMUA LOLOS**. Install bersih di
`/tmp/hh2`: tiap worker **3 skill**, koordinator **11**, home utama **12**.
Tool per profil dihitung dari `toolsets.py` asli: **13 / 25**.
`agentdrop test-workers` → **8 lulus, 0 gagal**. `browser_preflight` diuji pada
kedua kondisi. `bash -n` bersih untuk `agentdrop`, `lib/30-hermes.sh`,
`lib/40-browser.sh`.

**Tidak bisa diverifikasi dari sandbox:** unduhan Chrome for Testing (egress
diblokir), prosedur popup wallet pada MetaMask sungguhan, dan apakah kecepatan
yang dirasakan operator benar-benar membaik — itu butuh mesinnya.

## Arc 33 — Audit skill & SOUL: dua worker tanpa skill khusus, dan 58 skill bawaan Hermes

Sebelum operator pull ulang, ia meminta kepastian: tidak ada berkas kosong atau
gap, **setiap worker punya skill khusus yang tidak dimiliki worker lain**, prompt
system eksplisit, dan **tidak ada skill bawaan Hermes yang ikut terbawa**.

Semuanya diaudit terhadap hasil install yang sebenarnya, bukan terhadap repo.
Tiga dari empat permintaan itu menemukan masalah nyata.

### Temuan 1 — 58 skill bawaan Hermes bisa masuk ke profil, dan kita tidak menolaknya

Ini yang paling serius. Hermes mengirim **58 skill bawaan** dalam 13 kategori
(`hermes-agent/skills/`: apple, autonomous-ai-agents, creative, devops, email,
media, note-taking, productivity, research, social-media, software-development,
web). `sync_skills()` menyuntikkannya ke HERMES_HOME saat install, saat
`hermes update`, dan saat sync langsung.

`install.sh` kita **tidak pernah** menolak — `grep no-bundled-skills` di seluruh
repo menghasilkan **0**.

Hermes menyediakan mekanisme resminya:

```
tools/skills_sync.py:99-105
  Marker file written by `hermes profile create --no-skills` ...
  When present in HERMES_HOME, sync_skills() is a no-op so neither the
  installer, `hermes update`, nor a direct sync re-injects bundled skills.

tools/skills_sync.py:728
  essential_only = (_hermes_home() / NO_BUNDLED_SKILLS_MARKER).exists()
```

Dengan penanda itu, yang tetap di-seed hanya `ESSENTIAL_SKILLS` =
`{"hermes-agent"}` (`agent/skill_utils.py:443`).

**Perbaikan:** `lib/30-hermes.sh` sekarang menulis `.no-bundled-skills` ke
**setiap profil** dan ke **HERMES_HOME utama**, setiap kali install — bukan
sekali, karena operator bisa menghapusnya dan `hermes update` berikutnya akan
menyuntikkan 58 skill lagi. Diverifikasi sesudah install: 9 berkas penanda ada.

Dibandingkan nama per nama terhadap 58 skill bawaan: **bocoran 0**, 20 skill
terpasang semuanya milik AgentDrop.

### Temuan 2 — dua worker tidak punya satu pun skill khusus

| Profil | Skill khusus sebelum | Sesudah |
|---|---|---|
| pekerja-riset | **— tidak ada —** (`airdrop-analyzer` juga dipegang koordinator) | `riset-executor` |
| pekerja-daftar | **— tidak ada —** (`airdrop-intake` juga dipegang koordinator) | `onboard-executor` |
| 5 worker lain | sudah punya | tidak berubah |

Keduanya tidak punya satu pun prosedur yang khusus miliknya, jadi tidak ada yang
membedakan pekerjaannya selain kalimat di SOUL.md.

`riset-executor` sengaja dibedakan dari `airdrop-analyzer`: yang pertama menilai
dari **sumber primer yang dikunjungi sendiri** untuk memutuskan layak difarming,
yang kedua menilai dari teks pengumuman untuk memutuskan delegasi atau tidak.
`onboard-executor` berisi batas situs-proyek vs platform-quest, prosedur popup
wallet lewat `browser_cdp`, dan syarat verifikasi "form terkirim ≠ terdaftar".

### Temuan 3 — dua SOUL tanpa pernyataan batas sama sekali

Operator: *"tidak boleh agent a kerjakan tugas agent b."* Diukur dengan mencari
pernyataan batas eksplisit:

```
pekerja-quest   0x   ← paling rawan tumpang tindih dengan pekerja-daftar
pekerja-riset   0x   ← paling rawan tumpang tindih dengan koordinator
6 lainnya       1–3x
```

Keduanya diberi bagian `## Yang TIDAK saya kerjakan` yang menyebut worker lain
berdasarkan nama, dan menutup dengan: kalau task-nya masuk wilayah worker lain,
**hentikan dan laporkan** — jangan dikerjakan.

### Temuan 4 — satu gap rujukan skill

`pekerja-riset/SOUL.md:60` menulis `` `daily-executor` membaca berkas itu`` —
merujuk skill yang tidak terpasang di profil itu. Secara makna benar (ia
menyebut siapa yang *membaca* berkas), tapi memakai nama skill dalam backtick
membuatnya terlihat seperti arahan. Diganti jadi nama profilnya.

### Yang ternyata sudah benar

- **Tidak ada berkas kosong.** 18 SKILL.md: semuanya ≥854 byte, punya
  frontmatter, `name:`, dan `description:`.
- **Tidak ada SOUL kosong.** 8 SOUL.md: 9.458–16.459 byte, 10–12 bagian, dan
  kedelapannya punya bagian `## Akun ini milik saya/agent`.
- Tujuh bagian wajib (peran, akun milik agent, aturan, output, memory loop,
  injeksi=data) ada di semua profil — sebagian di bawah judul berbeda, dan itu
  tidak masalah.

### Validator 370 → 395

Empat aturan baru, semuanya diuji injeksi:

- **`[37]`** setiap worker wajib punya ≥1 skill yang tidak dimiliki profil lain.
- **`[38]`** `.no-bundled-skills` wajib ditulis ke **profil** dan ke **home
  utama** — tiga injeksi terpisah (buang semua / buang profil saja / buang home
  utama saja), ketiganya tertangkap.
- **`[39]`** SOUL tidak boleh menyuruh mengikuti skill yang tidak terpasang di
  profilnya. Polanya sengaja sempit (`Skill \`nama\``): versi yang mencocokkan
  semua nama skill dalam backtick menembak sebutan biasa. Diuji false-positive:
  0 error pada baris yang sah.
- **`[40]`** setiap SOUL wajib menyatakan apa yang TIDAK ia kerjakan.

### Cacat saya sendiri di arc ini

1. **`isi_lib` belum terdefinisi** saat aturan `[37]` memakainya →
   `UnboundLocalError`. Ketujuh kalinya kelas kesalahan ini muncul.
2. **Skill baru saya sendiri menembak aturan `[36]`.** Kalimatnya
   *"Login dan approval wallet bukan pekerjaan operator"* — maksudnya kebalikan
   dari yang dilarang, tapi polanya cocok. Diperbaiki dengan menulis ulang
   kalimatnya, bukan dengan melonggarkan aturannya.
3. **`/tmp/fix` dan `/tmp/fakebin` hilang saat reprovision** dan saya menulis
   skrip ke direktori yang tidak ada — `cat` gagal, lalu `bash -n` di baris
   berikutnya tetap mencetak OK sehingga terlihat sukses.

### Verifikasi

`tools/validate_config.py` → **395 checks, SEMUA LOLOS**. Install bersih di
`/tmp/hh2`: tiap worker 3–4 skill, koordinator 11, home utama 12; **9 marker
`.no-bundled-skills` ada**; **0 bocoran** dari 58 skill bawaan; **0 gap** rujukan
skill; **0 cacat isi**. `agentdrop test-workers` → **8 lulus, 0 gagal**.
`bash -n` bersih untuk semua skrip.

**Tidak bisa diverifikasi dari sandbox:** perilaku `hermes update` sungguhan
terhadap marker itu (Hermes tidak terpasang di sini), dan apakah model benar
mematuhi batas cakupan yang baru ditulis.

## Arc 34 — Audit menyeluruh seluruh kode: enam gap nyata

Operator meminta audit seluruh kode untuk memastikan tidak ada gap lagi. Delapan
kelas pemeriksaan dijalankan terhadap repo **dan** terhadap hasil install.

### Gap 1 — `cmd_run` menilai keberhasilan dari exit code *(cacat terbuka sejak Arc 20-an)*

```
agentdrop (sebelum)
  hermes --profile X chat -q "..."
  local rc=$?
  if [[ $rc -eq 0 ]]; then _ok "$profile selesai (rc=0)"
```

`hermes chat` mengembalikan **0 walau task gagal total** — sudah terjadi di mesin
operator: HTTP 402 dari endpoint, tidak ada satu tool pun terpanggil, rc tetap 0.
Ini kelas cacat **S** yang tercatat di AGENTS.md tapi tidak pernah ditutup.
`scripts/test-workers.sh` sudah memakai penilaian yang benar; `cmd_run` belum.

**Perbaikan:** `cmd_run` sekarang menilai dari **selisih jumlah baris log audit**,
cermin dari `hitung_total()` di test-workers. Tiga jalur, semuanya diuji:

| Kondisi | Sebelum | Sesudah |
|---|---|---|
| rc=0, tool terpanggil, tanpa error | ✓ selesai | ✓ "1 tool call, tanpa error" |
| rc=0, **tidak ada** tool terpanggil | ✓ selesai *(salah)* | ✗ "task tidak dikerjakan" + tunjuk `agentdrop model --show` |
| rc=0, ada baris `level=error` | ✓ selesai *(salah)* | ✗ "task GAGAL" + tunjuk `agentdrop audit errors` |

### Gap 2 — `x-engager` tidak punya prosedur reply/quote/thread

SOUL `pekerja-x` menjanjikan "Post wajib quest (announce, **thread**, **quote**,
**reply**)" dan "**Reply dan engagement** di thread proyek", tapi skillnya hanya
punya satu bagian `## Membuat post`. Dihitung: `thread` **0** sebutan, `reply` 1,
`quote` 1 — semuanya bukan prosedur.

Ditambahkan prosedur untuk reply, quote, thread, dan engagement. Yang paling
penting dari isinya adalah **cara verifikasinya**, karena ketiganya gagal dengan
cara yang terlihat seperti berhasil:

- reply yang nyasar jadi post mandiri → "terkirim", tapi quest tidak terhitung
- quote yang kutipannya hilang → jadi post biasa
- thread yang dibuat dengan membalas diri sendiri → sering tidak diakui platform

### Gap 3 — `discord-engager` tidak punya prosedur join dan role gate

SOUL menjanjikan delapan langkah (baca aturan → peta server → cek role → kerjakan
verifikasi → verifikasi role). Skillnya hanya berisi **prinsip**, bukan langkah.
Tidak ada cara masuk server lewat invite, tidak ada bentuk role gate, tidak ada
cara memastikan role benar-benar bertambah.

Ditambahkan, termasuk tabel empat bentuk role gate (reaction / bot command / form
/ connected account) dan satu aturan verifikasi yang penting: **bot role gate
sering membalas "verified" tapi gagal menetapkan role** karena konfigurasi
servernya rusak. Tanpa memeriksa daftar role, agent melaporkan keberhasilan yang
tidak terjadi.

### Gap 4 — empat profil berbeda pada kunci yang tidak boleh berbeda

Dibandingkan kunci per kunci di delapan `config.yaml`:

| Kunci | Sebelum | Sesudah |
|---|---|---|
| `browser.record_sessions` | **7/8** — `pekerja-riset` tidak punya | 8/8 `false` |
| `tool_loop_guardrails.warn_after.*` | **4/8** | 8/8 `2/3/2` |
| `tool_loop_guardrails.hard_stop_enabled` | **7/8** — riset `false` tanpa satu pun komentar penjelas | 8/8 `true` |

`pekerja-riset` tanpa `record_sessions: false` berarti ia merekam video WebM per
sesi dan menyimpannya 72 jam sementara tujuh worker lain tidak. Tidak ada
komentar yang menjelaskan perbedaan itu — murni drift.

### Gap 5 — prompt cron masih menyuruh berhenti saat sesi mati

`scripts/install-cron.sh:92` (job 09:00) menulis *"Kalau ketemu CAPTCHA atau
**sesi mati, hentikan campaign itu**"* — bertentangan langsung dengan Arc 32 yang
menjadikan login pekerjaan agent.

**Yang membuatnya lolos:** aturan `[36]` hanya memindai `SOUL.md` dan `SKILL.md`.
Prompt cron adalah instruksi yang benar-benar dikirim ke agent, tapi tidak
pernah diperiksa. Cakupan aturan diperluas ke `scripts/install-cron.sh` dan pola
baru ditambahkan; diuji injeksi.

### Gap 6 — dua import tak terpakai

`sys` di `tools/audit_log.py:45` dan `shutil` di `tools/validate_config.py:31`.
Dihapus sesudah dipastikan nol pemakaian, lalu keduanya diuji masih bisa
diimpor/dijalankan.

### Yang diperiksa dan ternyata BERSIH

- **Berkas yatim:** hanya `docs/analisis-bottleneck.md`. Lima `knowledge/chains/*`
  yang tadinya terlihat yatim ternyata dirujuk **sebagai direktori** enam kali —
  detektor saya yang terlalu ketat, bukan kodenya.
- **Fungsi shell:** 35 fungsi terdeklarasi (dibuktikan dengan `declare -F` sesudah
  sourcing semua `lib/*.sh`), tidak ada yang dipanggil tanpa definisi.
- **Kelas cacat shell:** `VAR="$(cmd|cmd)"` di bawah `set -euo pipefail` → **0**;
  baris terakhir fungsi berupa `[[ ]] && {}` → **0**; `grep -c … || echo 0` → 0
  (hanya satu komentar yang menjelaskan jebakan itu); `~` di token kedua hook
  `command:` → **0**; path `/home/<user>` hardcoded → **0** (satu-satunya
  kemunculan adalah contoh di docstring `audit-log.py:18`).
- **Rujukan path:** 5 kandidat, semuanya false positive — `.env` dan `data/audit`
  dibuat saat runtime, `extensions/installed` dibuat `mkdir -p` di
  `lib/40-browser.sh:137`, dan satu adalah string regex di validator.
- **Flag `hermes cron create`:** kelima flag yang dipakai (`--name`, `--skill`,
  `--workdir`, `--reasoning-effort`, `--deliver`) **diverifikasi ada** di
  `hermes_cli/subcommands/cron.py`. Ini menutup sebagian dari "cron tidak pernah
  diverifikasi" — eksekusinya tetap belum bisa diuji di sini.
- **pyflakes** pada semua Python: bersih setelah gap 6.

### Validator 396 checks

Aturan baru **`[41]`** — delapan profil wajib seragam pada sepuluh kunci yang
bukan selera per worker (`record_sessions`, `warn_after.*`, `inactivity_timeout`,
`snapshot_threshold`, `backend`, `disabled_toolsets`). Diuji dua injeksi.
Aturan `[36]` diperluas cakupannya + satu pola baru, diuji injeksi.

### Cacat saya sendiri di arc ini

1. **Menulis kata Cina `状态` ke dalam `x-engager`** saat menambahkan prosedur
   reply — persis kelas kesalahan yang sudah terjadi empat kali. Tertangkap oleh
   grep CJK yang memang dijalankan tiap kali, dan diganti sebelum commit.
2. **Detektor berkas yatim saya menembak lima false positive** karena mencari
   nama berkas persis, padahal `knowledge/chains/` dirujuk sebagai direktori.
3. **`/tmp/fix` hilang lagi saat reprovision** — `cat` gagal, dan karena
   `bash -n` di baris berikutnya tetap mencetak OK, satu putaran terlihat sukses.

### Verifikasi

`tools/validate_config.py` → **396 checks, SEMUA LOLOS**. `bash -n` bersih untuk
12 skrip. `pyflakes` bersih. Install bersih → delapan profil seragam
(skill khusus ada, SOUL 9.458–16.459 B, marker ada, 7 toolset, config seragam
semua "YA"), home utama 12 skill + marker. `agentdrop test-workers` → **8 lulus,
0 gagal**. Ketiga jalur penilaian `cmd_run` diuji dan hasilnya sesuai tabel.

**Tidak bisa diverifikasi dari sandbox:** eksekusi `hermes cron` sungguhan,
unduhan Chrome (egress diblokir), dan perilaku reply/quote/thread Discord serta X
pada situs aslinya.
