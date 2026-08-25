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

- **5 worker terspesialisasi** — analyzer, daily, quests, discord, monitor
- **Browser persisten** — Camofox (Camoufox/Firefox) dengan profil yang bertahan
  antar sesi, jadi login dashboard tidak hilang setiap hari
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
bash scripts/start-gateway.sh              # service background
bash scripts/start-gateway.sh --foreground # foreground (WSL/Docker/Termux)
```

> ⚠️ **Isi `TELEGRAM_ALLOWED_USERS` dulu.** Tanpa itu bot menerima perintah dari
> siapa pun yang menemukan username-nya. Ambil user ID Anda dari @userinfobot.

---

## 📋 Prasyarat

- Linux / macOS / WSL2 (bukan root)
- Docker (untuk Camofox)
- Python 3 (untuk validator)
- API key: Anthropic / OpenRouter / OpenAI / Google / Nous Portal / endpoint custom

---

## 🚀 Instalasi

### Satu perintah

```bash
curl -fsSL https://raw.githubusercontent.com/Scryptexai/AgentDrop/main/install.sh -o install.sh
less install.sh        # baca dulu — kami tidak mem-pipe curl ke bash
bash install.sh
```

Yang dikerjakan `install.sh`:

| | |
|---|---|
| ✅ | Dependency dasar (`git`, `curl`) via apt/dnf/pacman/brew |
| ✅ | **Docker** (dari `get.docker.com`, diunduh ke file dulu + tambah user ke grup `docker`) |
| ✅ | **PyYAML** (dengan fallback `--user` → `--break-system-packages` untuk PEP 668) |
| ✅ | **Hermes Agent** (diunduh ke file dulu supaya bisa diperiksa, bukan di-pipe ke bash) |
| ✅ | Clone repo + buat `.env` (mode 600) |
| ✅ | **6 profil worker + 6 skill** ke `~/.hermes/profiles/*/` |
| ✅ | Secret tersebar ke tiap profil (tiap profil = HERMES_HOME terpisah) |
| ✅ | Jalankan validator |
| ⚠️ | Telegram: **memeriksa** dan memberi instruksi, tidak membuatkan bot untuk Anda |

Yang **tetap** harus Anda lakukan sendiri: isi API key + token Telegram di
`.env`, pilih model, dan login visual sekali per platform.

### Manual

```bash
# 1. Hermes Agent
curl -fsSL https://hermes-agent.nousresearch.com/install.sh | bash
source ~/.bashrc

# 2. Repo ini
git clone https://github.com/Scryptexai/AgentDrop.git ~/AgentDrop
cd ~/AgentDrop

# 3. Secret
cp .env.example .env && chmod 600 .env
$EDITOR .env                    # isi API key

# 4. Pasang config + 5 profil + skill
bash scripts/setup.sh

# 5. Camofox (butuh Docker)
bash scripts/start-browser.sh

# 6. Jadwal otomatis
bash scripts/install-cron.sh

# 7. Verifikasi
python3 tools/validate_config.py
hermes doctor
```

---

## 🔥 Burn-in dulu — sebelum agent dipercaya kerja

Jangan langsung menyuruh agent mengerjakan campaign. **Stabilkan lapisan
browser-nya dulu** dengan eksekusi nyata, lalu baru naik.

```bash
./scripts/burn-in.sh                 # Uji 1-4 (aman)
./scripts/burn-in.sh 3               # ulang satu uji saja
./scripts/burn-in.sh --with-wallet   # + Uji 5 (connect wallet, TESTNET saja)
./scripts/burn-in.sh --with-social   # + Uji 6 (alur sosial nyata)
./scripts/burn-in.sh --all           # Uji 1-6
./scripts/burn-in.sh --profile worker-quests
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
./scripts/start-agent.sh worker-analyzer
```

> **Catatan sintaks:** `hermes chat` **tidak menerima argumen posisional** —
> hanya `-q/--query` atau `--query-file`. `hermes chat 'teks'` akan error.
> Ini diverifikasi dari `hermes_cli/_parser.py`.

---

## 🖥️ GUI Browser — bukan headless

Task airdrop hampir semuanya interaksi GUI, jadi browser di sini dijalankan
**terlihat**, dengan resolusi manusia, dan bisa Anda ambil alih kapan saja.

### Arsitekturnya

Plugin `vnc` camofox-browser menyusun rantai ini (dari `plugins/vnc/README.md`):

```
Camoufox (Xvfb :99, 1920x1080)
    ↑
x11vnc (attach ke :99, port 5900)
    ↑
noVNC / websockify (port 6080)
    ↑
Browser Anda → http://localhost:6080/vnc.html
```

Plugin ini menimpa display virtual 1×1 bawaan mode headless dengan resolusi
yang bisa dipakai manusia, lalu menjalankan watcher yang mendeteksi display
Xvfb dan memasang x11vnc + noVNC. Watcher-nya menangani restart browser
otomatis — saat Camoufox relaunch di display baru, x11vnc pasang ulang.

Dependency (`x11vnc`, `novnc`, `python3-websockify`, `net-tools`, `procps`)
sudah terpasang di image saat build oleh `scripts/install-plugin-deps.sh`.

### Kenapa `headed: true` bukan jawabannya

`browser.headed` di Hermes hanya berlaku untuk **browser lokal Hermes**
(agent-browser/Chromium), bukan Camofox. Dari `config_defaults.py`:

> "Camofox setups always keep the built-in tools (no CDP surface)."

Jadi kalau Anda memakai Camofox (yang kami lakukan), `headed` tidak
berpengaruh apa pun. GUI-nya datang dari plugin vnc. Karena itu semua config di
repo ini menulis `headed: false` **dengan komentar penjelas**, supaya tidak ada
yang mengira itu sudah mengaktifkan GUI.

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
   `browser_vision` atau `computer_use(mode='som')` — Set-of-Mark, elemen
   diberi nomor di atas screenshot.

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

Plugin `persistence` menyimpan cookies + localStorage — dan kami aktifkan
`indexedDB: true` supaya login berbasis IndexedDB (Firebase Auth, SSO) ikut
tersimpan — ke volume Docker. Dari README upstream:

> "Sessions survive browser restarts — log in once (via cookies or VNC), and
> subsequent sessions restore the authenticated state automatically."

### Alur take-over

```bash
./scripts/takeover.sh worker-daily https://app.galxe.com/login
```

Skrip ini:
1. Menghitung **userId Camofox yang persis sama** dengan yang akan dipakai
   Hermes untuk profil itu
2. Membuka halaman login di browser persisten
3. Memberi Anda URL noVNC untuk login manual (MFA, CAPTCHA — agent tidak
   menyentuh ini)
4. Mengekspor `storage_state` sebagai cadangan

**Langkah 1 itu yang penting.** Hermes menurunkan userId secara deterministik
dari `HERMES_HOME` (`tools/browser_camofox_state.py:get_camofox_identity`):

```python
scope_root  = HERMES_HOME / "browser_auth" / "camofox"
user_id     = "hermes_" + uuid5(NAMESPACE_URL, f"camofox-user:{scope_root}").hex[:10]
session_key = "task_"   + uuid5(NAMESPACE_URL, f"camofox-session:{scope_root}:{task}").hex[:16]
```

Kalau skrip login memakai userId karangan, login Anda masuk ke profil Firefox
yang **berbeda** dari yang dipakai agent — sia-sia. Formula di atas sudah diuji
melawan fungsi Hermes asli dan menghasilkan nilai identik
(`hermes_68c00ea529` / `task_8fe86c2102965395` untuk `worker-daily`).

> **Kalau semua worker harus berbagi satu login:** set `CAMOFOX_USER_ID` di
> `.env`. Dari `_camofox_identity_override()`: *"Integrations that own the
> visible Camofox browser can set a shared user ID so Hermes operates in the
> same browser profile."* `takeover.sh` otomatis mengikuti nilai itu.
>
> ⚠️ **Trade-off yang harus Anda tahu:** `_adopt_existing_tab` menyaring tab
> berdasarkan `userId` saja. Makin banyak worker berbagi satu `userId`, makin
> besar peluang agent meng-adopsi tab milik worker lain. Kalau Anda memakai
> identitas bersama, aturan "verifikasi URL sebelum bertindak" di setiap skill
> jadi wajib, bukan opsional.

### Catatan jujur

Agent tidak "melihat" GUI seperti manusia. Ia membaca snapshot DOM dan
screenshot lewat API Camofox. Yang berubah dengan setup ini:

- Browser berjalan **terlihat** di 1920×1080, bukan display 1×1 → rendering dan
  layout nyata, screenshot cocok dengan yang manusia lihat
- **Anda bisa masuk dan mengambil alih** kapan saja untuk MFA/CAPTCHA
- Login **bertahan** antar sesi dan antar restart

---

## 📁 Struktur

```
AgentDrop/
├── README.md
├── install.sh                  # one-click installer
├── docker-compose.yml          # Camofox + VNC (tanpa `build:` — lihat catatan di file)
├── .env.example
├── config/
│   ├── camofox/camofox.config.json   # plugin vnc + persistence (di-mount ke /app/)
│   └── hermes/
│       ├── config.yaml         # config utama
│       ├── SOUL.md             # identitas agent utama
│       └── profiles/
│           ├── worker-orchestrator/  {config.yaml, SOUL.md}  ← pintu masuk Telegram
│           ├── worker-analyzer/      {config.yaml, SOUL.md}
│           ├── worker-daily/         {config.yaml, SOUL.md}
│           ├── worker-quests/        {config.yaml, SOUL.md}
│           ├── worker-discord/       {config.yaml, SOUL.md}
│           └── worker-monitor/       {config.yaml, SOUL.md}
├── skills/
│   ├── airdrop-intake/SKILL.md     ← parse + klasifikasi (WAJIB sebelum eksekusi)
│   ├── airdrop-analyzer/SKILL.md
│   ├── daily-executor/SKILL.md
│   ├── quest-executor/SKILL.md
│   ├── discord-engager/SKILL.md
│   └── portfolio-tracker/SKILL.md
├── scripts/
│   ├── setup.sh                # pasang config + profil + skill
│   ├── start-browser.sh        # build & nyalakan Camofox + GUI
│   ├── takeover.sh             # login VISUAL sekali, dipakai semua sesi
│   ├── start-gateway.sh        # nyalakan bot Telegram
│   ├── start-agent.sh          # jalankan worker
│   └── install-cron.sh         # jadwal via cron internal Hermes
├── tools/validate_config.py    # validator statis
├── docs/research.md            # riset + provenance setiap klaim
└── data/{campaigns,logs,screenshots}/
```

Setelah `setup.sh`, semuanya terpasang ke `~/.hermes/` dan
`~/.hermes/profiles/<worker>/`.

---

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

**Sudah diverifikasi** (25 Aug 2026, terhadap clone `NousResearch/hermes-agent`
dan `jo-inc/camofox-browser`):

- 6 `config.yaml` — setiap key top-level & sub-key dicocokkan ke `DEFAULT_CONFIG`
- 5 `SKILL.md` — frontmatter sesuai format skill bawaan Hermes
- 6 shell script — `bash -n` bersih
- Daftar key di validator **cocok persis** dengan sumber (0 selisih), dicek via
  `HERMES_SRC=/tmp/ha python3 tools/validate_config.py`
- **Formula userId Camofox** di `takeover.sh` diuji melawan fungsi Hermes asli
  `get_camofox_identity()` → identik (`hermes_68c00ea529` / `task_8fe86c2102965395`)
- **`.gitignore`** diuji dengan `git check-ignore`: `storage-state*.json`
  terabaikan, `.gitkeep` tetap terlacak
- **Negative test** (validator harus menangkap, bukan meloloskan):
  - key karangan dari brief awal (`file_ops`, `browser.camofox.url`,
    `security.never_store_private_keys`, `cron.enabled`,
    `model.default: claude-sonnet-4-5`) → **10 error**
  - toolset `browser` dicabut dari satu worker + `managed_persistence: false`
    → **2 error**
  - `camofox.config.json` dirusak (trailing comma) → tertangkap, dengan
    penjelasan failure mode senyap `{}`
  - `plugins.vnc.enabled: false` → tertangkap sebagai "browser akan headless"

```bash
python3 tools/validate_config.py                      # daftar beku
HERMES_SRC=/path/to/hermes-agent python3 tools/validate_config.py   # turunkan ulang dari sumber
```

**Belum diverifikasi** — sandbox pengerjaan tidak punya `docker`, `hermes`,
maupun `crontab`:

- ❌ `install.sh` end-to-end di mesin bersih
- ❌ `scripts/start-browser.sh` (build image Camofox + `/health` + noVNC :6080)
- ❌ `scripts/takeover.sh` terhadap Camofox yang benar-benar jalan
- ❌ `scripts/install-cron.sh` terhadap Hermes yang benar-benar jalan
- ❌ Sesi GUI nyata: login via noVNC → agent memakai sesi itu

Yang terakhir itu yang paling perlu Anda uji sendiri — itu inti dari seluruh
setup browser di sini.

---

## 🆘 Troubleshooting

| Masalah | Periksa |
|---|---|
| `hermes: command not found` | `source ~/.bashrc`, atau jalankan `install.sh` ulang |
| Camofox tidak connect | `docker ps` → container `camofox-browser` hidup? `curl localhost:9377/health` |
| Image Camofox tidak ada | Jalankan `make fetch && make build` di `~/.camofox-src` — **jangan** `docker build` langsung |
| **noVNC :6080 tidak kebuka** | `ENABLE_VNC=1` di `.env`? lalu `docker compose logs camofox \| grep -i vnc`. Plugin butuh `x11vnc`+`novnc`+`websockify` di image |
| **Browser masih terasa headless** | Cek `config/camofox/camofox.config.json` ter-mount: `docker compose exec camofox cat /app/camofox.config.json` harus menampilkan `vnc.enabled: true` |
| **Login hilang tiap hari** | `managed_persistence: true` di config worker? volume `camofox-profiles` masih ada? `persistence.enabled` di camofox.config.json? |
| **Login manual tidak kepakai agent** | userId harus sama. Pakai `scripts/takeover.sh` (menghitung userId), jangan login lewat tab sembarangan |
| API key error | `hermes config` → cek provider; secret harus di `~/.hermes/.env` |
| Cron tidak jalan | `hermes --profile <p> cron status`; scheduler butuh `hermes gateway run` |
| Profil tidak ketemu | `ls ~/.hermes/profiles/` → jalankan `scripts/setup.sh` |
| Skill tidak terbaca | Skill harus ada di `~/.hermes/profiles/<p>/skills/`, bukan cuma `~/.hermes/skills/` |
| Config ditolak Hermes | `python3 tools/validate_config.py` |

---

## 📚 Riset

Semua klaim teknis di repo ini punya provenance. Termasuk dua sumber dari brief
awal yang ternyata **404** (AirdropAlert, MadeOnSol) dan apa konsekuensinya.

→ [`docs/research.md`](docs/research.md)

---

## 📝 Lisensi

MIT
