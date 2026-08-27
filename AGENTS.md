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

Terakhir diperbarui: 2026-08-27 · commit `fc3fda7` · branch `arena/01a037ea-agentdrop`
Angka diverifikasi dengan perintah, bukan diperkirakan.

**7 profil · 10 skill · 13 berkas knowledge · 180 pemeriksaan validator lolos (exit 0)**

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
