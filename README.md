# Hermes Airdrop Agent (AgentDrop)

Sistem multi-agent di atas [Hermes Agent](https://github.com/NousResearch/hermes-agent)
untuk **riset, pelacakan, dan automasi** farming airdrop — dijalankan oleh satu
operator, atas akun milik operator itu sendiri.

Clone → isi API key di `.env` → jalan.

---

## ⚠️ Baca ini dulu: cakupan

Repo ini **tidak** membangun tooling untuk mengecoh deteksi sybil. Tidak ada
generasi wallet massal, tidak ada fingerprint spoofing lintas identitas, tidak
ada rotasi proxy per wallet.

Alasannya sederhana: itu melanggar ToS hampir semua program airdrop dan
merugikan pengguna nyata yang reward-nya dilarutkan ke identitas fiktif.

Yang **ada** di sini, dan semuanya sah:

| | |
|---|---|
| 🖥️ **GUI browser** | Firefox sungguhan 1920×1080 yang bisa Anda **lihat dan ambil alih** lewat noVNC — bukan headless |
| 🔍 **Riset** | Filter proyek 4 dimensi, keputusan PRIORITIZE / CONSIDER / SKIP |
| 🗂️ **Pelacakan** | Progres campaign, bukti screenshot, laporan harian & mingguan |
| ⚙️ **Automasi** | Daily check-in & quest atas akun milik Anda sendiri |
| 💬 **Komunitas** | Engagement Discord dengan volume manusiawi, bukan bot |
| 🛡️ **Guardrail** | Berhenti di CAPTCHA/2FA, tanpa private key, approval untuk aksi berisiko |

Isolasi browser yang dipakai di sini untuk **keamanan dan privasi** satu
operator — bukan penyamaran. Detail: [`docs/research.md`](docs/research.md) §6.

---

## ✨ Fitur

- **6 worker terspesialisasi** — analyzer, daily, quests, discord, monitor, x
- **Browser asli + wallet resmi** — Chrome for Testing lewat CDP dengan
  MetaMask/OKX/Phantom yang diunduh, bukan ekstensi bikinan sendiri
- **Profil browser persisten** — login dashboard bertahan antar sesi
- **Log audit penuh** — setiap tool call, keputusan, dan kesalahan tercatat,
  dengan `agentdrop audit doctor` yang menunjuk berkas yang harus dibaca
- **Akses shell dimatikan** untuk semua worker — agent memakai tool native, tidak
  pernah mengetik perintah untuk membuka browser sendiri
- **Filter Sniper 4 dimensi** — Team, Product, Narrative, Timing & Cost
- **Scheduler native Hermes** — bukan system crontab
- **Audit trail** — screenshot bukti, log bertimestamp, rekaman sesi WebM
- **Berhenti saat ragu** — confidence rendah → minta review manusia

---

## 💬 Cara pakai: kirim ke Telegram, selesai

Anda tidak perlu menghafal perintah. Forward pengumuman airdrop ke bot, lalu
balas "ya".

```
Anda  →  🔈 MemeBitcoin Airdrop
         ➖ Register
         https://.../register?r=XXXXXX
         ➖ Connect Twitter
         ➖ Complete Easy Task
         ➖ Submit Email Address
         ➖ Submit EVM Address
         ➖ Complete Daily Mission
         ➖ Done

Bot   →  MemeBitcoin — analisis selesai

         Bisa saya kerjakan (2):
           1. Register (kode referral XXXXXX dipertahankan)
           2. Submit EVM Address  ← alamat publik, bukan signature

         Butuh Anda (3):
           1. Connect Twitter — OAuth, buka http://localhost:6080/vnc.html
           2. Submit Email — butuh akses inbox Anda
           3. Complete Easy Task — saya buka, syaratnya ambigu

         Perlu dijadwalkan (1):
           1. Daily Mission → cron tiap 09:00

         Lanjut? (ya / ubah / batal)

Anda  →  ya
```

### Arsitekturnya

```
Telegram (bot)
   ↓  pesan mentah
worker-orchestrator          ← role: orchestrator, delegate_task
   ├─ skill airdrop-intake   parse + klasifikasi + INVESTIGASI yang ambigu
   ↓  delegate_task(tasks=[...], output_schema=...)
   ├──→ worker-quests        eksekusi task `auto`
   ├──→ worker-daily         daily mission + cron
   ├──→ worker-analyzer      kelayakan proyek (opsional)
   └──→ worker-discord       komunitas
```

Ini memakai delegation native Hermes, bukan bikinan:
`delegation.orchestrator_enabled`, `delegate_task(goal, tasks=[{goal,context,role}],
output_schema=...)`, `role: leaf|orchestrator`, `max_concurrent_children`,
`max_spawn_depth`.

`max_spawn_depth: 1` — child tidak boleh mendelegasikan lagi. Delegasi berantai
tanpa batas adalah cara tercepat menghabiskan saldo API.

### Kenapa "pahami dulu" itu satu langkah tersendiri

**Setiap airdrop punya format task berbeda, aturan berbeda, dan kebutuhan
berbeda.** Skill `airdrop-intake` ada karena tidak ada parser generik yang aman.
Yang bisa dilakukan: klasifikasi hati-hati, tandai yang tidak pasti sebagai
`unknown`, lalu **buka halamannya dan baca syaratnya** sebelum menyentuh apa pun.

Dua jebakan nyata dari format yang biasa dikirim:

| Teks di pengumuman | Kelas | Kenapa |
|---|---|---|
| `Connect EVM Wallet` | `human:wallet` | butuh **signature** — wajib operator |
| `Submit EVM Address` | `auto` | cuma **alamat publik** — agent boleh |
| `Connect Twitter` | `human:oauth` | OAuth di domain pihak ketiga |
| `Complete Easy Task` | `unknown` | namanya tidak memberi informasi apa pun |
| `Complete Daily Mission` | `recurring` | butuh cron, bukan sekali jalan |

Salah mengklasifikasi baris pertama berarti agent mencoba menandatangani
transaksi. Itu batas yang tidak boleh dilewati.

### Menyalakan

```bash
agentdrop start     # gateway Telegram; agent berjalan di atasnya
agentdrop stop
agentdrop status    # periksa kesiapan sebelum mulai
```

> ⚠️ **Isi `TELEGRAM_ALLOWED_USERS` dulu.** Tanpa itu bot menerima perintah dari
> siapa pun yang menemukan username-nya. Ambil user ID Anda dari @userinfobot.

---

## 📋 Prasyarat

- Linux / macOS / WSL2
- Python 3.9+
- Node.js 18+  (Hermes menjalankan browser lewat `npx agent-browser`)
- API key: Anthropic / OpenRouter / OpenAI / Google / Nous Portal / endpoint custom
- Untuk GUI browser: `xvfb`, `x11vnc`, `novnc`

**Docker tidak dibutuhkan.** Browser berjalan langsung di host.

---

## 🚀 Instalasi

```bash
git clone https://github.com/Scryptexai/AgentDrop.git
cd AgentDrop
./install.sh
```

`install.sh` adalah **index**: ia me-source `lib/*.sh` dan menjalankan
tahap-tahapnya berurutan. Ia memasang, tidak menjalankan apa pun.

| Tahap | Yang dikerjakan |
|---|---|
| 1 | Dependensi: python3+venv, node, hermes, Xvfb/x11vnc/websockify |
| 2 | Kode ke `/usr/local/lib/agentdrop` (root) atau `~/.agentdrop/app`, perintah `agentdrop` ke PATH |
| 3 | Kredensial — ditanya langsung, ditulis ke tempat yang benar |
| 4 | Config, 7 profil + `SOUL.md`, skill per profil, memory, knowledge, hook audit |
| 5 | Chrome for Testing + unduh wallet resmi |
| 6 | Verifikasi |

Opsi: `--skip-browser`, `--skip-extensions`, `--non-interactive`, `--dir PATH`,
`--hermes-home PATH`, `--verify-only`.

**Private key tidak pernah masuk `.env`.** `.env` tersalin ke setiap profil, jadi
satu key di sana berarti key itu ada di tujuh tempat. Installer menulisnya ke
berkas tersendiri berizin 0600 dan menyimpan path-nya di `.env`.

Yang **tetap** harus Anda lakukan sendiri: mengisi API key dan token Telegram,
membuat atau mengimpor wallet di browser, dan login visual sekali per platform.

---

## 🎛️ Perintah

```bash
agentdrop status          periksa kesiapan — lakukan ini lebih dulu
agentdrop browser         nyalakan Chrome for Testing + noVNC
agentdrop extensions      pasang/perbarui wallet resmi
agentdrop start           nyalakan gateway Telegram (agent berjalan di atasnya)
agentdrop stop
agentdrop audit doctor    diagnosis kalau ada yang rusak
agentdrop audit trace ID  runtutan satu task
agentdrop logs            kumpulkan log ke data/audit/ untuk dianalisis
agentdrop cron            pasang jadwal otomatis
agentdrop burn-in         uji stabilisasi sebelum agent dipercaya
```

`agentdrop start` menyalakan gateway **dan** agent sekaligus — agent berjalan di
atas gateway, jadi memisahkannya jadi dua perintah hanya membingungkan.

---

## 🌐 Browser

Chrome for Testing, disambungkan lewat CDP. Dua hal yang perlu diketahui:

- **Harus Chrome for Testing, bukan Google Chrome branded.** Sejak Chrome 137,
  build branded mengabaikan `--load-extension` — ekstensi tidak akan termuat dan
  Chrome tidak memberi pesan error apa pun.
- **Verifikasi sebelum farming.** Buka noVNC, muat halaman apa pun, lalu di
  console pastikan `window.ethereum` dan `window.solana` ada. Kalau `undefined`,
  ekstensi tidak termuat dan semua task wallet akan gagal dengan cara yang
  membingungkan.

Wallet yang dipakai adalah **MetaMask / OKX / Phantom yang diunduh**, bukan
ekstensi bikinan sendiri. Ekstensi non-official terdeteksi sebagai klien asing,
berisiko di-ban proyek, dan ditolak sebagian dApp.

---

## 🔥 Burn-in dulu — sebelum agent dipercaya kerja

Jangan langsung menyuruh agent mengerjakan campaign. **Stabilkan lapisan
browser-nya dulu** dengan eksekusi nyata, lalu baru naik.

```bash
agentdrop burn-in                 # Uji 1-4 (aman)
agentdrop burn-in 3               # ulang satu uji saja
agentdrop burn-in --with-wallet   # + Uji 5 (connect wallet, TESTNET saja)
agentdrop burn-in --with-social   # + Uji 6 (alur sosial nyata)
agentdrop burn-in --all           # Uji 1-6
agentdrop burn-in --profile worker-quests
```

| Uji | Yang diuji | Sentuh wallet/sosial? |
|---|---|---|
| 1 | Navigasi + `browser_snapshot` | tidak |
| 2 | Elemen dinamis & `ref` | tidak |
| 3 | Form & input | tidak |
| 4 | Sesi bertahan (persistence) | tidak |
| 5 | Connect wallet | **ya** — butuh `--with-wallet` + ketik `TESTNET` |
| 6 | Alur sosial nyata | **ya** — butuh `--with-social` |

Uji dijalankan **satu per satu**, bukan sekaligus: kalau semuanya dikirim dalam
satu prompt, kegagalan di Uji 2 menular ke 3–6 dan Anda tidak tahu lapisan mana
yang rusak. Uji 5 dan 6 tidak pernah ikut secara default.

**Buka noVNC dulu** (`http://localhost:6080/vnc.html`) — burn-in justru untuk
ditonton. Log saja tidak cukup untuk menilai apakah browser benar-benar stabil.

Kalau satu uji gagal 3× dengan cara yang sama, itu bukan masalah prompt, itu
masalah lingkungan. Perbaiki lingkungannya, jangan perkuat promptnya.

---

## 🧪 Pakai

```bash
# Analisis sebuah proyek
hermes --profile worker-analyzer chat -q "Analisis proyek ini: https://..."

# Jalankan check-in harian sekarang
hermes --profile worker-daily chat -q "Jalankan daily check-in untuk semua campaign aktif"

# Kerjakan sebuah quest
hermes --profile worker-quests chat -q "Kerjakan campaign ini: https://app.galxe.com/quest/..."

# Laporan mingguan
hermes --profile worker-monitor chat -q "Buat ringkasan mingguan semua campaign"

# Chat interaktif
agentdrop start
```

> **Catatan sintaks:** `hermes chat` **tidak menerima argumen posisional** —
> hanya `-q/--query` atau `--query-file`. `hermes chat 'teks'` akan error.
> Ini diverifikasi dari `hermes_cli/_parser.py`.

---

## 🖥️ GUI Browser — bukan headless

Browser dijalankan dengan **GUI sungguhan**, bukan headless. Alasannya praktis:
login Google/Discord/X, OAuth, MFA, dan CAPTCHA dikerjakan **manusia**, dan
manusia tidak bisa mengerjakan itu di browser yang tidak terlihat.

Rantainya:

```
Chrome for Testing  ->  Xvfb :99  ->  x11vnc :5900  ->  noVNC :6080
       |                                                        |
       +-- CDP :9222 <-- Hermes attach ke sini                  +-- browser Anda
```

`agentdrop browser` menyalakan keempatnya. Anda menonton dan mengambil alih di
`http://localhost:6080/vnc.html`, agent memakai sesi yang sama.

> ⚠️ **Kalau port 6080 bisa diakses dari luar mesin, set `VNC_PASSWORD`.**
> Tanpa itu siapa pun yang mencapai port tersebut mengendalikan browser yang
> memegang wallet Anda.


### Bagaimana agent melihat & bertindak (tanpa selector)

Agent **tidak memakai CSS selector atau XPath**. Alasannya sederhana: UI website
airdrop berubah-ubah, jadi selector mengunci agent ke satu versi tampilan dan
patah saat mereka deploy.

Yang dipakai:

1. `browser_snapshot` → Hermes mengembalikan **accessibility tree** halaman,
   tiap elemen interaktif punya `ref` (mis. `@e5`).
2. `browser_click(ref="@e5")` → klik lewat ref, bukan lewat selector.
3. **`ref` hanya sah pada snapshot yang menghasilkannya.** Setelah halaman
   berubah, ref lama batal — agent wajib snapshot ulang.
4. **Verifikasi sebelum lanjut.** Setelah tiap aksi, agent harus menyatakan
   `berhasil` / `gagal` / `tidak diketahui` — bukan menumpuk aksi di atas
   asumsi.
5. Kalau accessibility tree tidak cukup (canvas, overlay, popup), turun ke
   `browser_vision` — screenshot halaman yang bisa Anda periksa secara visual.

Pendekatan ini bukan karangan: Hermes memang menyediakan tool-tool itu secara
native (`browser_snapshot` tidak punya parameter selector sama sekali), dan pola
verifikasinya diambil dari **OpenManus** (`FoundationAgents/OpenManus`), yang
mewajibkan field `evaluation_previous_goal: Success|Failed|Unknown` dan
penghitungan progres eksplisit ("3 dari 7 task") di setiap langkah.

Protokol lengkapnya di `skills/browser-operation/SKILL.md`, dan **diringkas wajib
di SOUL.md keenam worker** — karena SOUL.md adalah system prompt, sedangkan skill
hanya *tersedia* dan boleh diabaikan. `tools/validate_config.py` menolak build
kalau blok protokol itu hilang dari SOUL.md mana pun.

**Yang sengaja tidak diadopsi dari OpenManus:** prompt browser mereka menulis
*"If captcha pops up, try to solve it"*. Di sini CAPTCHA selalu diserahkan ke
manusia lewat noVNC.

### Login sekali, dipakai semua worker

Semua worker memakai **satu profil browser yang sama**
(`~/.agentdrop/chrome-profile`). Anda login sekali lewat noVNC, dan sesi itu
dipakai worker mana pun setelahnya. Cookie dan localStorage bertahan di profil
itu selama tidak dihapus.

### Alur take-over

```
1. agent mengerjakan task sampai butuh login
2. agent berhenti, lapor lewat Telegram: "butuh login <platform>"
3. Anda buka noVNC, selesaikan login/MFA/CAPTCHA
4. Anda balas "lanjut"
5. agent melanjutkan dengan sesi yang sudah login
```

Agent tidak pernah menyentuh kredensial Anda dan tidak pernah mengetik password.

### Catatan jujur

- Ekstensi wallet harus dibuat atau diimpor **manual sekali** lewat noVNC. Agent
  tidak bisa dan tidak boleh melakukannya.
- `window.ethereum` harus diverifikasi ada sebelum farming dimulai. Lihat bagian
  Browser di atas.
- Chrome for Testing, bukan Google Chrome branded. Lihat alasan di bagian Browser.


## 📁 Struktur

```
AgentDrop/
├── README.md
├── AGENTS.md                   # konteks build — WAJIB dibaca sebelum mengubah kode
├── install.sh                  # INDEX: me-source lib/*.sh, memasang, tidak menjalankan
├── agentdrop                   # satu-satunya perintah runtime
├── .env.example
│
├── lib/                        # modul yang di-source install.sh
│   ├── 00-common.sh            #   path + logging
│   ├── 10-deps.sh              #   python3, node, hermes, Xvfb/x11vnc
│   ├── 20-credentials.sh       #   tanya token/key, tulis ke tempat yang benar
│   ├── 30-hermes.sh            #   config, profil, skill, memory, hook
│   ├── 40-browser.sh           #   Chrome for Testing, wallet, noVNC
│   └── 50-verify.sh            #   preflight
│
├── config/
│   ├── extensions.yaml         # daftar wallet yang diunduh
│   └── hermes/
│       ├── config.yaml         # config utama (browser.cdp_url, toolsets, security)
│       ├── SOUL.md             # identitas agent utama
│       └── profiles/           # 7 profil, masing-masing {config.yaml, SOUL.md}
│           ├── worker-orchestrator/   ← pintu masuk Telegram
│           ├── worker-analyzer/  worker-daily/  worker-quests/
│           ├── worker-discord/   worker-monitor/  worker-x/
│
├── skills/                     # 10 skill; tiap profil hanya dapat yang dipetakan
│   ├── browser-operation/  browser-burn-in/  airdrop-intake/
│   ├── airdrop-analyzer/   daily-executor/   quest-executor/
│   ├── discord-engager/    portfolio-tracker/ x-engager/
│   └── self-improvement/   ← memory loop
│
├── knowledge/                  # dikembangkan AGENT (docs/ dikembangkan manusia)
│   ├── chains/  projects/  patterns/
│
├── memory/lessons/             # catatan GAGAL append-only, per profil
│
├── hooks/agentdrop-audit/      # gateway hook: agent:start / step / end
├── agent-hooks/audit-log.py    # shell hook: pre/post_tool_call, subagent_*
│
├── tools/
│   ├── validate_config.py      # validator statis
│   ├── audit_log.py            # penulis JSONL + redaksi
│   └── audit.py                # triase: health / errors / doctor / trace / stuck
│
├── scripts/                    # hanya yang belum tergantikan CLI
│   ├── burn-in.sh  collect-logs.sh  install-cron.sh
│
└── docs/
    ├── prosedur-uji.md         # cara menjalankan uji di mesin Anda
    ├── arsitektur-alur.md      # alur kerja
    ├── meta-2026.md            # riset meta airdrop 2026
    └── research.md             # catatan provenance tiap config key
```


## 🤖 Profil worker

| Profil | Tugas | Model | Reasoning |
|---|---|---|---|
| `worker-orchestrator` | **Pintu masuk Telegram** + delegasi ke worker | kuat | `high` |
| `worker-analyzer` | Filter proyek 4 dimensi | kuat | `high` |
| `worker-daily` | Check-in harian | hemat | `medium` |
| `worker-quests` | Eksekusi campaign multi-langkah | kuat | `high` |
| `worker-discord` | Engagement komunitas | sedang | `medium` |
| `worker-monitor` | Verifikasi & pelaporan | kuat | `high` |

`worker-orchestrator` adalah satu-satunya yang boleh mendelegasikan
(`delegation.orchestrator_enabled: true`) dan satu-satunya yang menghadap
Telegram. Ia **tidak** diberi toolset `terminal` di
`platform_toolsets.telegram` — pintu masuk publik tidak boleh punya shell.

> **Kenapa tiap profil punya `config.yaml` lengkap?** `hermes --profile <name>`
> menyetel `HERMES_HOME` ke `~/.hermes/profiles/<name>/`. Profil adalah
> HERMES_HOME **terpisah penuh** — tidak mewarisi config utama. Diverifikasi
> dari `hermes_cli/main.py:_apply_profile_override`.

---

## ⏰ Jadwal

| Waktu | Profil | Job |
|---|---|---|
| 09:00 | `worker-daily` | Daily check-in semua campaign |
| 13:00 | `worker-monitor` | Verifikasi tengah hari |
| 20:00 | `worker-monitor` | Laporan harian |
| Minggu 21:00 | `worker-monitor` | Ringkasan mingguan + rekomendasi lanjut/berhenti |

Memakai **scheduler internal Hermes** (ticker in-process 60 detik), bukan system
crontab — jadi job dapat preflight validation, model-drift guard, dan terlihat
di `hermes cron list`.

```bash
hermes --profile worker-daily cron list      # lihat job
hermes --profile worker-monitor cron status  # status scheduler
hermes --profile worker-monitor cron runs    # riwayat eksekusi
```

Job cron butuh scheduler yang hidup. Jalankan gateway:
```bash
hermes --profile worker-monitor gateway run
```

---

## 🛡️ Keamanan

Guardrail di repo ini memakai **key Hermes yang benar-benar ada**, bukan key
karangan:

```yaml
security:
  redact_secrets: true            # redaksi secret otomatis di log
  allow_private_urls: false       # tolak navigasi ke IP privat
  protected_instruction_files: true
  website_blocklist:              # opsional: blokir domain tertentu
    enabled: false
    domains: []

approvals:
  cron_mode: "deny"               # job tanpa pengawasan TIDAK bisa dapat approval
  single_query_mode: "deny"
  denial_breaker_threshold: 3
```

Ditambah aturan di setiap `SOUL.md` dan `SKILL.md`:

- **Tidak ada private key, seed phrase, atau keystore** — di prompt, file, log,
  atau screenshot. Hanya alamat publik. `setup.sh` **menolak** `.env` yang
  berisi field private key.
- **CAPTCHA / 2FA / verifikasi apa pun → STOP.** Serahkan ke manusia (pola
  "Take Over" dari Manus Cloud Browser).
- **Tidak ada signature wallet / transaksi.** Butuh signature → `needs_human`.
- **Verifikasi sebelum klaim.** Tidak ada perubahan state yang bisa dibaca ulang
  = aksi dianggap gagal.
- **Setiap aksi dicatat** dengan timestamp + screenshot.
- `.env` dipasang dengan mode `600` dan di-`.gitignore`.

---

## 📊 Data

```
data/
├── campaigns/<project>/
│   ├── info.json          # detail proyek + hasil analisis 4 dimensi
│   ├── progress.json      # progres harian
│   ├── quest-run.json     # hasil eksekusi quest
│   ├── discord-log.json   # aktivitas komunitas
│   └── screenshots/       # bukti
└── logs/
    ├── YYYY-MM-DD-daily.md
    └── agent.log
```

---

## 🔄 Alur kerja

```
1. Operator forward info airdrop
        ↓
2. worker-analyzer → skor 4 dimensi → 8/10 → PRIORITIZE
        ↓
3. Operator: "gas"
        ↓
4. worker-quests → kerjakan task `auto`, STOP di task `human`
        ↓
5. worker-daily → check-in otomatis tiap 09:00
        ↓
6. worker-monitor → verifikasi 13:00, laporan 20:00, ringkasan Minggu 21:00
```

---

## ✅ Status verifikasi

**Sudah diuji dan lolos:**

- Validator statis: **179 pemeriksaan**, exit 0
- Log audit end-to-end: penulis JSONL, redaksi dua lapis (diuji per pola dengan
  memutus satu pola pada satu waktu), `flock` konkuren, rotasi
- Shell hook dengan bentuk payload persis dari dokumen Hermes, termasuk stdin
  rusak dan kosong
- Ekstraksi CRX3 dengan CRX sintetis
- `bash -n` bersih di semua skrip
- Tiap guard validator diuji **mutasi** — kondisinya benar-benak dirusak, lalu
  dipastikan validator menolaknya

**Belum bisa diuji di lingkungan pembuat, dan butuh mesin Anda:**

- Hook yang benar-benar menyala di dalam run Hermes yang hidup
- Chrome for Testing yang benar-benar memuat ekstensi wallet
- Alur lengkap Telegram → orchestrator → worker → wallet

Ketiganya diuji lewat prosedur di `docs/prosedur-uji.md`, dan hasilnya
dikumpulkan dengan `agentdrop logs` supaya bisa dianalisis.

> **Catatan jujur soal cakupan uji.** Dulu ada tiga suite test (47 policy,
> 25 daemon, 9 plugin). Ketiganya dihapus bersama subsistemnya saat ekstensi
> bikinan sendiri dan signing daemon dibuang. Yang tersisa sebagai pengaman
> adalah validator 179 pemeriksaan plus uji mutasi per guard — itu **bukan**
> pengganti suite test. Kalau nanti ada logika Python baru dengan cabang
> keputusan nyata, ia butuh suite test sendiri.

---

## 🆘 Troubleshooting

| Gejala | Periksa |
|---|---|
| Mulai dari mana pun | `agentdrop status` — menyebut komponen mana yang belum siap |
| `hermes` tidak ketemu | Jalankan `./install.sh` |
| Ekstensi tidak termuat | `agentdrop browser-status`, lalu pastikan yang dipakai Chrome for Testing, **bukan** Google Chrome branded |
| `window.ethereum` undefined | Ekstensi tidak termuat — jalankan `agentdrop extensions`, restart browser |
| CDP tidak menjawab | `agentdrop browser` |
| noVNC tidak kebuka | `xvfb`, `x11vnc`, `novnc` terpasang? `agentdrop browser-status` |
| Log audit kosong | Hook tidak terdaftar — `agentdrop status` bagian [3] |
| Agent membuka browser sendiri | `disabled_toolsets` hilang — jalankan ulang `./install.sh` |
| Profil tidak ketemu | `ls ~/.hermes/profiles/`, lalu jalankan ulang `./install.sh` |
| Ada yang rusak dan tidak tahu apa | `agentdrop audit doctor` |

`agentdrop audit doctor` membaca log audit, mengelompokkan kegagalan menurut
komponen, dan **menyebut berkas yang harus dibuka**. Itu langkah pertama yang
paling murah sebelum membaca apa pun yang lain.

---


## 📚 Riset

Semua klaim teknis di repo ini punya provenance. Termasuk dua sumber dari brief
awal yang ternyata **404** (AirdropAlert, MadeOnSol) dan apa konsekuensinya.

→ [`docs/research.md`](docs/research.md)

---

## 📝 Lisensi

MIT
