# Riset & Dasar Keputusan

Catatan ini merekam **apa yang benar-benar diverifikasi**, dari mana, dan kapan —
supaya klaim di repo ini bisa diaudit ulang. Semua pemeriksaan dilakukan pada
**25 Agustus 2026**.

---

## 1. Status sumber riset dari brief

| Sumber | Status | Catatan |
|---|---|---|
| HTX Insights — "The Last Time I'll Talk About Backpack, and Also Discussing My Airdrop Farming Principles" | ✅ **Ada, dibaca penuh** | Penulis: Princess Christine (@0xsexybanana), terbit 23 Mar 2026. Sumber utama filter 4 dimensi. |
| Manus Documentation — Cloud Browser | ✅ **Ada, dibaca** | Mekanisme "Take Over", sesi persisten, "No credential storage". |
| Hermes Agent docs — Configuration | ✅ **Ada, dibaca** | Struktur `~/.hermes/`, aturan secret→`.env`, precedence. |
| `NousResearch/hermes-agent` (GitHub) | ✅ **Clone penuh** | 25.182 commit, commit terakhir 13 menit sebelum pengecekan. |
| `browser-use/browser-use` (GitHub) | ✅ **Clone** | versi `0.13.8` (dari `pyproject.toml`). |
| `jo-inc/camofox-browser` (GitHub) | ✅ **Clone** | v1.14.0, 490 commit. |
| Steemit — "How I Farm Crypto Airdrops Across 30 Wallets Without Getting Flagged as a Sybil" | ⚠️ **Tidak dipakai** | Di luar cakupan — lihat bagian 6. |
| AirdropAlert — "Guide to Airdrop Farming 2026" | ❌ **404** | `airdropalert.com/guide-to-airdrop-farming-2026-earning-crypto-the-smart-way/` mengembalikan "Oops! We couldn't find the page you were looking for." |
| MadeOnSol — "Solana Airdrop Farming Strategies 2026" | ❌ **404** | `madeonsol.com/solana-airdrop-farming-strategies-whats-still-working-in-2026/` mengembalikan halaman 404. |
| TechCrunch — Browser Use | ⚪ Tidak dikutip | Tidak dibutuhkan setelah `browser-use` di-clone langsung. |

**2 dari sumber yang dirujuk brief sudah mati.** Klaim yang hanya didukung dua
sumber itu (mis. "LST stacking", "fokus 3-5 protokol") tidak ditulis sebagai
fakta di repo ini.

---

## 2. Filter 4 Dimensi (Sniper approach)

Sumber: HTX Insights, @0xsexybanana, 23 Mar 2026 — dibaca langsung.

Brief menyebut dua metodologi farming:

1. **"Old Dong school"** — jaring lebar, adu eksekusi, logika studio padat
   karya. Toleransi kesalahan tinggi; satu airdrop besar menutup semua sunk
   cost dari yang "反撸" (ditolak airdrop-nya).
2. **Sniper approach** (mengutip Xu Xin dari Today Capital) — riset berat,
   partisipasi dalam, menyaring "industrial garbage" keluar dari firing range
   **sebelum** modal keluar.

Kutipan kunci dari penulis: *"proyek yang saya bullishi belum tentu sukses,
tapi yang tidak saya bullishi pasti tidak sukses."*

### Keempat dimensi (verbatim dari sumber)

**1. Team (People)** — "Smart enough, good enough execution, good enough heart.
None can be missing."
Dinilai dari tweet founder: apakah orang ini "big brain" atau hanya frontman
yang tahu cara shilling dan berteriak slogan. Banyak tweet founder begitu kosong
sampai tidak ada insight tentang industrinya sendiri.

**2. Product (PMF)** — tiga sub-dimensi: (a) produk punya PMF, (b) delivery
kompeten, (c) tim bertanggung jawab atas produk. Pembanding yang dipakai: OKX
tidak pernah menyerahkan produk penuh "low-level mistakes", baik di tahap awal
maupun matang.

**3. Narrative** — "berada di track yang relatif baru, belum terfalsifikasi, dan
menikmati premi valuasi sangat tinggi." Uji ganda: apakah naratif ini punya
ruang hype di Web3 **dan** apakah ia "capital 风口" di Web2 — logika hype
keduanya sering tersinkron. Contoh penulis: Openmind (AI + robotika = darling
triliun dolar di Web2, belum terfalsifikasi di Web3) — yang kemudian kena 反撸
dan airdrop-nya nol, disebut penulis sebagai black swan dimensi lain.

**4. Timing & Cost** — apakah sentimen sangat FOMO atau sangat pesimis; biaya
partisipasi rendah atau tinggi.

> **Aturan tegas dari sumber: "If you feel hesitant, it's best not to
> participate."**

Alasannya: profit pool pasar 1.5-level tidak sanggup menanggung volume sebesar
itu. *"Even if it's a good project, if everyone farms it, a big airdrop becomes
a small one, a small one becomes nothing, and nothing becomes a big loss."*

### Studi kasus Backpack (kenapa penulis menolak farming)

- **Narrative:** skeptis pada naratif "compliant CEX". Hyperliquid naik sebagian
  karena kebutuhan tax avoidance + anti-censorship; di bawah kerangka kepatuhan
  yang makin keras, apa moat Backpack vs Binance/OKX?
- **Product:** "I rarely see any exchange's technical foundation as shoddy as
  Backpack's." Outage berulang, rollback, beberapa kompensasi massal dalam
  setengah tahun. Kontras: Hyperliquid di awal (2.000 followers) nyaris tanpa bug
  terlihat.
- **Timing & Cost:** season 3 dimulai saat perp zero-fee (mis. lighter) sudah
  populer; biaya farming 0.5u tidak menarik.

---

## 3. Fakta teknis Hermes Agent (dari sumber, bukan dokumentasi ringkas)

Semua diverifikasi terhadap clone `NousResearch/hermes-agent`.

### Struktur `~/.hermes/`
```
config.yaml   .env   auth.json   SOUL.md
memories/     skills/   cron/   sessions/   logs/
```

### Aturan konfigurasi
- Secret (API key, token, password) **wajib** di `.env`. Sisanya di `config.yaml`.
- Precedence: CLI args > `config.yaml` > `.env` > default bawaan.
- `hermes config set KEY VAL` merutekan otomatis: API key → `.env`, lainnya →
  `config.yaml`.
- Substitusi `${VAR_NAME}` didukung di `config.yaml`. Variabel tak terdefinisi
  dibiarkan verbatim + warning. `${env:VAR}` juga diterima.

### `--profile`
`_apply_profile_override()` (hermes_cli/main.py) di-scan **sebelum** argparse
dan di-strip dari argv. Ia menyetel `HERMES_HOME` ke
`~/.hermes/profiles/<name>/`.

**Konsekuensi penting:** profil adalah HERMES_HOME **terpisah penuh**. Config
profil **tidak** mewarisi `~/.hermes/config.yaml` — key yang tidak diset jatuh
ke default bawaan Hermes. Karena itu setiap profil di repo ini punya
`config.yaml` yang self-contained, `.env` sendiri, dan `skills/` sendiri.

### `hermes chat` tidak punya argumen posisional
Dari `hermes_cli/_parser.py`: `-q/--query` dan `--query-file` berada dalam
**mutually exclusive group**, dan tidak ada positional. Jadi:

```bash
hermes --profile worker-daily chat 'teks'      # ✗ error
hermes --profile worker-daily chat -q 'teks'   # ✓
```

### `model.default` memakai format `provider/model`
Contoh di `cli-config.yaml.example`: `anthropic/claude-opus-4.6`. Help
`hermes chat -m`: `"e.g., anthropic/claude-sonnet-4"`.

### `toolsets`
`DEFAULT_CONFIG["toolsets"] = ["hermes-cli"]`. Id valid (dari
`hermes_cli/tools_config.py`): `browser, terminal, file, web, memory, skills,
todo, vision, computer_use, code_execution, cronjob, delegate_task,
session_search, context_engine, clarify, delegation, image_gen, tts, stt, ...`

**`file_ops` bukan id valid** — yang benar `file`.

### Cron: scheduler internal, bukan system crontab
Hermes punya ticker in-process 60 detik (`cron/scheduler.py`), job disimpan di
tabel SQLite. Subcommand: `list, create/add, edit, pause, resume, run, remove,
status, runs, notepad, tick`.

```
hermes cron create <schedule> [prompt] \
  [--name N] [--deliver T] [--skill S] [--workdir W] \
  [--model M] [--reasoning-effort L] [--continuity]
```
`schedule`: `'30m'` | `'every 2h'` | `'0 9 * * *'`

Key `cron` asli: `allow_agent_scheduling, preflight, model_drift_guard, model,
model_provider, provider, chronos, max_parallel_jobs, mirror_delivery,
output_retention, script_timeout_seconds, session_db_timeout_seconds,
wrap_response, media_send_timeout_seconds`.

**Tidak ada** `cron.enabled` atau `cron.jobs_dir`.

### Camofox di Hermes
`CAMOFOX_URL` adalah **env var di `.env`**, bukan key config. Dari
`hermes-agent/.env.example`:
```
# CAMOFOX_URL=http://localhost:9377
# CAMOFOX_USER_ID=
# CAMOFOX_SESSION_KEY=
# CAMOFOX_ADOPT_EXISTING_TAB=false
```
Key `browser.camofox.*` asli (diekstrak dari `DEFAULT_CONFIG`):
`managed_persistence, user_id, session_key, adopt_existing_tab,
rewrite_loopback_urls, loopback_host_alias`. **Tidak ada `url`.**

Catatan dari `config_defaults.py`: *"Camofox setups always keep the built-in
tools (no CDP surface)."*

### Format SKILL.md
Skill bawaan Hermes memakai YAML frontmatter:
```yaml
---
name: apple-notes
description: "..."
version: 1.0.1
author: Hermes Agent
license: MIT
platforms: [macos]
metadata:
  hermes:
    tags: [...]
    related_skills: [...]
prerequisites:
  commands: [memo]
---
```
Platform valid: `linux`, `macos`, `windows`.

### SOUL.md, bukan `system_prompt`
`system_prompt` bukan top-level config key. Identitas agent di-inject dari
`SOUL.md` (slot #1 system prompt; `DEFAULT_SOUL_MD` di `hermes_cli/config.py`).

### Key guardrail yang BENAR-benar ada
`DEFAULT_CONFIG` punya 89 top-level key. Yang relevan untuk guardrail:

**`security`**: `redact_secrets` (default `True`), `allow_private_urls`,
`protected_instruction_files`, `website_blocklist: {enabled, domains,
shared_files}`, `approval`, `tirith_enabled`, `allow_lazy_installs`,
`acked_advisories`, `protected_instruction_extra_patterns`, `tirith_*`,
`allow_data_training_tiers_noninteractive`.

**`approvals`**: `mode` (`'smart'`), `timeout` (300), `cron_mode` (`'deny'`),
`single_query_mode` (`'deny'`), `smart_policy`, `denial_breaker_threshold` (3),
`deny` ([]), `mcp_reload_confirm`, `destructive_slash_confirm`.

**`human_delay`**: `mode` (`off`|`natural`|`custom`), `min_ms` 800, `max_ms`
2500 — **hanya untuk pacing respons di platform messaging**, bukan jeda aksi
browser. Tidak dipakai di repo ini agar tidak salah fungsi.

**Yang TIDAK ada** (key yang diasumsikan brief):
`security.never_store_private_keys`, `security.stop_on_captcha`,
`security.burner_only`, `security.require_approval_for_wallet`,
`browser.camofox.url`, `cron.enabled`, `cron.jobs_dir`, `system_prompt`.

### `agent.reasoning_effort`
Valid, didokumentasikan di `cli-config.yaml.example` baris 1078 di bawah
`agent:` (dimulai baris 974) dan diimplementasikan di `agent/reasoning_effort.py`.
Level menurut `--reasoning` CLI help: `none, minimal, low, medium, high, xhigh,
max, ultra`.

---

## 4. Fakta teknis Camofox (dari `jo-inc/camofox-browser`)

- **"Stealth headless browser for AI agents — bypass Cloudflare, bot detection,
  and anti-scraping. Drop-in Puppeteer/Playwright replacement."** Berbasis
  Camoufox (Firefox).
- **Tidak ada `docker-compose.yml` di upstream.** Yang ada `Makefile` dengan
  target `build, up, down, reset, clean, fetch`.
- `make up` menjalankan:
  `docker run -d --restart unless-stopped --name camofox-browser --shm-size=2g -p 9377:9377 $(IMAGE)`
- **Peringatan eksplisit di README:** *"Do not run `docker build` directly. The
  Dockerfile uses bind mounts to pull pre-downloaded binaries from `dist/`.
  Always use `make up` (or `make fetch` then `make build`)."*
  → Karena itu `docker-compose.yml` di repo ini **tidak punya `build:`**; ia
  memakai image lokal `camofox-browser:$(VERSION)-$(ARCH)`.
- Image: `IMAGE := camofox-browser:$(VERSION)-$(ARCH)`, `VERSION ?= 135.0.1`,
  ARCH auto-detect (`arm64` → `aarch64`). **Tidak ada image registry publik.**
- Env var server: `CAMOFOX_PORT` (9377), `CAMOFOX_BIND_HOST`,
  `CAMOFOX_ACCESS_KEY` (bearer untuk semua route kecuali `/health`, cookie
  import, `/stop`), `CAMOFOX_ADMIN_KEY` (untuk `POST /stop`),
  `CAMOFOX_PROFILE_DIR` (`~/.camofox/profiles`), `CAMOFOX_COOKIES_DIR`,
  `CAMOFOX_TRACES_DIR`, `MAX_SESSIONS` (50), `SESSION_TIMEOUT_MS` (1800000),
  `BROWSER_IDLE_TIMEOUT_MS` (300000), `CAMOFOX_INTERACTIVE` (`desktop`|`off`).
- `/health` tanpa autentikasi — aman untuk healthcheck.

### GUI browser: plugin vnc
Dari `plugins/vnc/README.md` (awalnya kontribusi @leoneparise di PR #65):

> "Interactive browser access via VNC. Log into sites visually, solve CAPTCHAs,
> approve OAuth prompts — then export the authenticated storage state for reuse
> by your agent."

Rantai prosesnya:
```
Camoufox (Xvfb :99, 1920x1080)
    ↑
x11vnc (attaches to :99, port 5900)
    ↑
noVNC / websockify (port 6080)
    ↑
Your browser → http://localhost:6080/vnc.html
```

> "The plugin overrides Camoufox's default 1x1 virtual display with a
> human-usable resolution, then runs a watcher process that detects the Xvfb
> display and attaches x11vnc + noVNC. The watcher handles browser restarts
> automatically."

- Env var: `ENABLE_VNC=1`, `VNC_PASSWORD`, `NOVNC_PORT` (default 6080)
- Config: `{"vnc": {"enabled", "resolution", "password", "viewOnly", "novncPort"}}`
- Dependency (`plugins/vnc/apt.txt`): `x11vnc`, `novnc`, `python3-websockify`,
  `net-tools`, `procps` — dipasang saat build oleh `scripts/install-plugin-deps.sh`
- Endpoint ekspor: `GET /sessions/:userId/storage_state`

### Config plugin Camofox
- File: **`camofox.config.json`** di root aplikasi. Dari `lib/plugins.js:68`:
  `const CONFIG_PATH = path.join(ROOT_DIR, 'camofox.config.json');`
  Dockerfile: `WORKDIR /app` + `COPY camofox.config.json ./` → **`/app/camofox.config.json`**
- Isi bawaan upstream v1.14.0:
  ```json
  {"interactive": {"mode": "off"},
   "plugins": {"youtube": {"enabled": true},
               "persistence": {"enabled": true},
               "vnc": {"enabled": false, "resolution": "1920x1080"}}}
  ```
- **Failure mode senyap:** `lib/config.js:readCamofoxConfig` hanya `JSON.parse`
  dan `catch { return {} }`. File rusak → **semua plugin mati tanpa error**,
  termasuk persistence. Karena itu `tools/validate_config.py` memvalidasi file
  ini, bukan mengasumsikannya.
- persistence plugin: `{enabled, profileDir, indexedDB}`. `indexedDB: true`
  menyimpan login yang hidup di IndexedDB (README menyebut Firebase Auth dan
  SSO lain). Trade-off upstream: snapshot lebih besar, checkpoint lebih lambat.
- `CAMOFOX_INTERACTIVE=desktop` membuka window Camoufox lokal nyata — tapi README
  menegaskan: *"intended for a person using the same machine; it does not expose
  a remote browser-control service."* Untuk Docker, GUI-nya lewat noVNC.

### userId Camofox diturunkan deterministik
Dari `tools/browser_camofox_state.py:get_camofox_identity` (dijalankan langsung
untuk memverifikasi):

```python
CAMOFOX_STATE_DIR_NAME = "browser_auth"
CAMOFOX_STATE_SUBDIR   = "camofox"
scope_root  = str(get_hermes_home() / "browser_auth" / "camofox")
user_id     = "hermes_" + uuid5(NAMESPACE_URL, f"camofox-user:{scope_root}").hex[:10]
session_key = "task_"   + uuid5(NAMESPACE_URL, f"camofox-session:{scope_root}:{task}").hex[:16]
```

Verifikasi empiris:
```
HERMES_HOME=/home/user/.hermes/profiles/worker-daily
get_camofox_identity() -> {'user_id': 'hermes_68c00ea529',
                           'session_key': 'task_8fe86c2102965395'}
```
Replikasi formula di `scripts/takeover.sh` menghasilkan nilai **identik**.

Override lewat `CAMOFOX_USER_ID` / `browser.camofox.user_id`. Dari
`_camofox_identity_override()`: *"Integrations that own the visible Camofox
browser can set a shared user ID so Hermes operates in the same browser profile
instead of creating a separate private session."*

### Hermes sudah sadar VNC
`tools/browser_camofox.py` punya `get_vnc_url()` yang mengembalikan URL VNC
kalau server Camofox menyediakannya. Hermes bisa menampilkan URL take-over ke
user tanpa skrip tambahan — `takeover.sh` hanya membungkus alur login + ekspor
storage state.

### Risiko adopsi tab yang salah (ditemukan saat meninjau ulang)
`_adopt_existing_tab` di `tools/browser_camofox.py:352`:

```python
tabs = _get("/tabs", params={"userId": session["user_id"]}).get("tabs", [])
matching_tabs = [t for t in tabs if t.get("listItemId") == session_key]
candidates = matching_tabs or [tab for tab in tabs]   # fallback: SEMUA tab
latest = candidates[-1]                               # ambil yang TERAKHIR
session["tab_id"] = latest.get("tabId")
```

Perhatikan baris `candidates`: kalau tidak ada tab yang cocok `session_key`,
Hermes **tidak gagal** — ia mengambil tab terbaru milik `userId` itu. Jadi agent
bisa menempel ke tab yang menampilkan halaman tak terduga (mis. tab yang dibuka
manusia lewat `takeover.sh`, atau tab worker lain bila `userId` dibagi).

**Kenapa tidak fatal** — `user_id` tidak bergantung pada `task_id`. Diuji dengan
menjalankan `get_camofox_identity()` langsung untuk 5 task_id berbeda:

```
task_id                 user_id             session_key
None                    hermes_68c00ea529   task_8fe86c2102965395
default                 hermes_68c00ea529   task_8fe86c2102965395
galxe                   hermes_68c00ea529   task_acd1e884c5025630
task-1                  hermes_68c00ea529   task_cb0ad0e3b1de58e5
conversation-abc123     hermes_68c00ea529   task_4f284e1a79bd593a

jumlah user_id unik: 1
```

Plugin persistence menyimpan auth state per **userId**, jadi login selalu ada di
profil yang sama walau tab-nya berganti. Setelah adopsi, `browser_navigate`
mengirim tab itu ke URL yang agent tuju.

**Kenapa tetap perlu dijaga** — kalau agent melakukan `browser_snapshot` SEBELUM
navigasi, ia membaca apa pun yang sedang tampil di tab adopsi. Karena itu
setiap skill yang memakai browser di repo ini mewajibkan urutan:
`browser_navigate` eksplisit → `browser_snapshot` → cocokkan URL/judul dengan
yang diharapkan. Aturan ini ditegakkan oleh `tools/validate_config.py`, jadi
tidak bisa hilang diam-diam saat skill diedit.

Catatan tambahan: `effective_task_id = task_id or "default"`
(`tools/browser_tool.py:3351`), dan tidak ditemukan mekanisme yang menyuntikkan
task_id dari `agent/` ke tool browser. Jadi jalur default runtime memakai
`task_id="default"` — sama dengan default `takeover.sh`.

### Snapshot adalah tool native Hermes
`browser_snapshot` didefinisikan di **`tools/browser_tool.py:3537`** milik
Hermes, dengan backend Camofox di `tools/browser_camofox.py`. Repo AgentDrop
tidak mengandung satu baris pun yang memanggil tool browser
(`browser_navigate|browser_snapshot|browser_click|playwright|selenium|page.goto`
→ nol hasil). Skrip di repo ini hanya menyiapkan konfigurasi dan membuka satu
tab untuk login manual; seluruh navigasi dan pembacaan halaman dilakukan tool
Hermes.

### `browser.headed` TIDAK berlaku untuk Camofox
- `browser.headed = False` — *"Local mode: launch Chromium with a visible window
  (also skips per-turn cleanup so the window persists between turns; idle reaper
  still applies)"*
- tapi juga: *"Camofox setups always keep the built-in tools (no CDP surface)."*

Jadi `headed` hanya relevan kalau meninggalkan Camofox dan memakai browser lokal
Hermes. Semua config di repo ini menulis `headed: false` **plus komentar** agar
tidak disalahartikan sebagai "GUI sudah aktif".

---

## 5. Pola "Take Over" dari Manus

Dari dokumentasi resmi Manus Cloud Browser:

> "When Manus encounters complex verifications (SMS codes, CAPTCHA, multi-factor
> authentication), the system will prompt you to **'Take Over'** the browser."

Alurnya: agent menemui tantangan verifikasi → user dinotifikasi → user
menyelesaikan verifikasi → kontrol dikembalikan → agent lanjut.

Prinsip keamanan yang mereka sebut dan kita adopsi:
- **No credential storage** — "Manus doesn't store your passwords"
- **Isolated environments** — tiap user punya instance browser terpisah
- **Session management** — user bisa logout/clear kapan saja
- **Data center IP** — Manus jujur menyatakan browser cloud-nya memakai IP data
  center, yang memicu verifikasi tambahan di sebagian situs.

Pola inilah yang jadi dasar aturan "STOP saat CAPTCHA/2FA" di semua skill
AgentDrop.

---

## 6. Arsitektur OpenManus (dirujuk langsung dari kode)

**Catatan repo:** `mannaandpoem/OpenManus` yang dirujuk sekarang hanya stub
redirect (1 commit "Initial commit", README 378 byte). README-nya menyatakan:
*"The OpenManus project has moved"* → **`FoundationAgents/OpenManus`**. Semua
temuan di bawah dari clone repo baru itu (2.4 MB).

### 6.1 Pengelolaan agent — tiga lapisan

```
BaseAgent            app/agent/base.py      (196 baris)
  ├─ name, system_prompt, next_step_prompt, llm, memory, state
  ├─ max_steps, current_step, duplicate_threshold
  ├─ run(): while current_step < max_steps and state != FINISHED: step()
  ├─ is_stuck(): hitung pesan assistant duplikat; >= threshold (2)
  ├─ handle_stuck_state(): PREPEND prompt ke next_step_prompt
  └─ state_context(): transisi state aman, ERROR saat exception
        ↓
ReActAgent           app/agent/react.py     (38 baris)
  └─ step() = think() lalu act()
        ↓
ToolCallAgent        app/agent/toolcall.py  (258 baris)
  ├─ think(): llm.ask_tool(messages, tools, tool_choice)
  └─ act(): eksekusi tool_calls
        ↓
Manus / BrowserAgent (agent spesifik, tool sendiri)
```

**Deteksi stuck** (`base.py`) menarik karena murah: bukan analisis semantik,
cukup menghitung berapa kali konten pesan assistant terakhir muncul ulang.
Kalau >= 2, prompt ini di-**prepend** ke `next_step_prompt`:

> "Observed duplicate responses. Consider new strategies and avoid repeating
> ineffective paths already attempted."

### 6.2 Pengelolaan browser

- `BrowserAgent` (MCPAgent) mengakses browser lewat **MCP**:
  `uvx browser-use --cli-mcp`, tool `browser_exec` (kirim body Python) dan
  `browser_screenshot`. Docstring-nya: *"The browser-harness session persists
  across calls."*
- `Manus` menyambung browser_use sebagai MCP server dengan env `BU_CDP_URL`,
  `BU_CDP_WS`, `BU_BROWSER_ID` — bisa diarahkan ke browser eksternal via CDP.
- `SandboxBrowserTool` (`app/tool/sandbox/sb_browser_tool.py`) menjalankan
  browser **di sandbox** (Daytona), bukan di mesin host.
- `BrowserContextHelper.format_next_step_prompt()` memanggil
  `get_current_state()` **setiap langkah** dan menyuntikkan: url, title, jumlah
  tab, `pixels_above`, `pixels_below`, dan screenshot sebagai image message.

### 6.3 Bagaimana UI dianalisis dan klik dilakukan — inti temuan

**Representasi elemen** (dari `app/prompt/browser.py`):

```
[33]<button>Submit Form</button>
```
- `index` = pengenal numerik untuk interaksi
- `type` = tipe elemen HTML
- `text` = deskripsi
- *"Only elements with numeric indexes in [] are interactive"* — elemen tanpa
  `[]` hanya konteks

**Tidak ada aksi klik-by-selector.** Aksi yang tersedia di `sb_browser_tool.py`:
`click_element`, `input_text`, `go_back`, `scroll_down`, `scroll_up`,
`send_keys`, `switch_tab`, `wait`, `get_dropdown_options`,
`select_dropdown_option` (+ `go_to_url`, `extract_content`, `done` di prompt).
Secara **struktural mustahil** mengunci ke selector.

`get_current_state()` juga mengembalikan help eksplisit:
> `"[0], [1], [2], etc., represent clickable indices corresponding to the
> elements listed."`

**Set-of-Mark** (dari prompt, aturan VISUAL CONTEXT):
> *"Bounding boxes with labels on their top right corner correspond to element
> indexes."*

Jadi screenshot dan daftar index memakai penomoran yang **sama** — agent bisa
memakai teks atau gambar, keduanya merujuk index identik.

**Kontrak respons terstruktur:**
```json
{"current_state": {
   "evaluation_previous_goal": "Success|Failed|Unknown - Analyze the current
      elements and the image to check if the previous goals/actions are
      successful like intended by the task...",
   "memory": "...Count here ALWAYS how many times you have done something and
      how many remain. E.g. 0 out of 10 websites analyzed",
   "next_goal": "..."},
 "action":[{...}]}
```

Tiga hal yang diadopsi AgentDrop:
1. **`evaluation_previous_goal`** — verifikasi wajib sebelum menentukan langkah
   berikutnya
2. **`memory` dengan hitung eksplisit** ("0 out of 10") — pola *recitation*
3. **`next_goal`** — satu langkah berikutnya, bukan rencana panjang

**Aksi berurutan dengan interupsi:**
> *"If the page changes after an action, the sequence is interrupted and you get
> the new state. Only provide the action sequence until an action which changes
> the page state significantly."*

**Penanganan error di prompt:** kembali ke halaman sebelumnya, cari baru, tab
baru, scroll untuk menemukan elemen, tutup popup/cookie, *"Don't hallucinate
actions"*.

### 6.4 Orkestrasi

`PlanningFlow` (`app/flow/planning.py`):
- `PlanStepStatus` — enum status per langkah
- `get_executor(step_type)` — **pilih agent berdasarkan tipe langkah**; kalau
  `step_type` cocok dengan key agent, pakai agent itu; selain itu fallback ke
  `primary_agent`
- `execute(input_text)` — susun rencana → eksekusi per langkah dengan executor
  yang sesuai → cek terminate

Ini pola yang sama dengan orchestrator → worker, tapi routing-nya berbasis
**tipe langkah**, bukan delegasi bebas.

### 6.5 Yang TIDAK diadopsi

Prompt OpenManus menulis:

> *"If captcha pops up, try to solve it - else try a different approach"*

**AgentDrop tidak mengadopsi ini.** CAPTCHA diserahkan ke manusia lewat noVNC.
Ini perbedaan kebijakan yang disengaja, bukan kelalaian.

### 6.6 Perbandingan dengan Hermes

| Aspek | OpenManus | Hermes (dipakai AgentDrop) |
|---|---|---|
| Representasi elemen | `[index]<type>text</type>` | AX tree + `refs` (`@e5`) |
| Klik | `click_element(index)` | `browser_click(ref="@e5")` |
| Selector CSS | tidak ada aksinya | tidak dipakai |
| Visual | screenshot + kotak bernomor | `browser_vision`, `computer_use(mode='som')` |
| State per langkah | `get_current_state()` | `browser_snapshot` |
| Verifikasi aksi | `evaluation_previous_goal` di skema | **diadopsi** ke `skills/browser-operation` |
| Hitung progres | wajib di `memory` | **diadopsi** |
| Stuck detection | `is_stuck()` + prepend prompt | `tool_loop_guardrails` |
| Konten di luar viewport | `pixels_above/below` | **diadopsi** sebagai aturan scroll |
| Orkestrasi | `PlanningFlow.get_executor(step_type)` | `delegate_task(role)` |

**Kesimpulan:** Hermes sudah memakai abstraksi yang benar (AX tree + refs, bukan
selector). Yang kurang adalah **disiplin verifikasi**, dan itu yang diadopsi ke
`skills/browser-operation/SKILL.md`.

---

## 7. Keputusan cakupan: tidak ada lapisan anti-sybil

Brief meminta komponen `sybil-protector` dengan 4-layer identity isolation
(wallet massal, browser fingerprint spoofing, rotasi proxy per wallet,
randomisasi perilaku) yang tujuannya eksplisit: **tidak terdeteksi sebagai
sybil**.

**Komponen itu tidak dibangun.** Membangun tooling untuk mengecoh deteksi sybil
berarti membantu pelanggaran ToS program airdrop dan penipuan terhadap proyek —
reward yang seharusnya untuk pengguna nyata dilarutkan ke identitas fiktif.

Yang dipilih user: **lewati lapisan itu sepenuhnya.**

Yang tetap dibangun (semuanya sah):
- Analisis proyek 4 dimensi (riset)
- Pelacakan progres campaign
- Automasi daily check-in & quest **atas akun milik operator sendiri**
- Engagement komunitas dengan volume manusiawi
- Monitoring & pelaporan

Isolasi yang tetap ada di repo ini bersifat **keamanan dan privasi**, bukan
penyamaran: satu browser profile persisten untuk satu operator, secret di `.env`
dengan mode 600, `security.redact_secrets`, dan `approvals.cron_mode: deny`.

---

## 8. Batas verifikasi di lingkungan pengerjaan

Yang **tidak** bisa dijalankan di sandbox tempat repo ini dibangun:

| Alat | Status |
|---|---|
| `git clone` | ✅ jalan |
| PyPI | ✅ jalan |
| `docker` / `docker-compose` | ❌ tidak ada |
| `hermes` | ❌ tidak ada |
| `crontab` | ❌ tidak ada |
| `curl` ke `raw.githubusercontent.com` | ❌ `SSL_ERROR_SYSCALL` |

**Konsekuensi:** `install.sh`, `scripts/start-browser.sh`, `scripts/takeover.sh`,
dan `scripts/install-cron.sh` **belum pernah dijalankan end-to-end**.

Yang **sudah** diverifikasi, dan caranya:

| Klaim | Cara diverifikasi |
|---|---|
| Setiap key config cocok skema Hermes | Parse `DEFAULT_CONFIG` dengan AST, bandingkan; 0 selisih |
| Format SKILL.md benar | Dibanding skill bawaan `skills/apple/*/SKILL.md` |
| Sintaks 6 shell script | `bash -n` |
| Formula userId Camofox di `takeover.sh` | **Menjalankan fungsi Hermes asli** `get_camofox_identity()` lalu membandingkan dengan replikasi → identik |
| `.gitignore` melindungi file sesi | `git check-ignore` per path |
| Validator benar-benar menangkap error | 4 negative test (key karangan, browser dicabut, JSON rusak, vnc dimatikan) |
| Port/flag/env var Camofox | Dibaca dari README + `Makefile` + `Dockerfile` + `plugins/*/apt.txt` di clone |

Yang **paling perlu Anda uji sendiri**: sesi GUI nyata — login via noVNC di
`:6080`, lalu pastikan agent benar-benar memakai sesi itu. Seluruh rantai
identity (userId deterministik → profil Firefox persisten → reuse oleh agent)
sudah diverifikasi di tingkat kode, tapi belum pernah dijalankan hidup.

---

## 9. Rute browser: Camofox vs Chrome CDP, dan status kredensial Hermes

Ditambahkan 2026-08-26 setelah operator menanyakan dua hal: apakah browser
harus Firefox, dan apakah Hermes benar-benar membaca `.env`.

### 9.1 Hermes membaca `.env` — terverifikasi

`hermes_cli/env_loader.py:470-504`:

```python
home_path = Path(hermes_home or os.getenv("HERMES_HOME", Path.home()/".hermes"))
user_env  = home_path / ".env"
...
_load_dotenv_with_fallback(user_env, override=True)
```

`.env` dimuat dengan `override=True`, jadi ia MENIMPA variabel shell yang basi.
`.env` di direktori proyek hanya fallback dev dan cuma mengisi yang kosong.

Karena `--profile` menyetel `HERMES_HOME` sebelum import
(`hermes_cli/main.py:520`), yang terbaca untuk sebuah worker adalah
`~/.hermes/profiles/<nama>/.env`. Karena itu `scripts/setup.sh` memasang `.env`
ke `~/.hermes/.env` DAN ke setiap direktori profil. Itu bukan redundansi.

`config.yaml` tetap tempat kredensial DIRUJUK, lewat `${VAR}` atau
`${env:VAR}` (`hermes_cli/config.py:2693-2701`). Tapi kredensial provider
sendiri dibaca dari env — `cli-config.yaml.example:41-52` menulisnya sebagai
nama env var:

```
"openrouter" - OpenRouter (requires: OPENROUTER_API_KEY or OPENAI_API_KEY)
"anthropic"  - Direct Anthropic API (requires: ANTHROPIC_API_KEY)
"gemini"     - Google AI Studio (requires: GOOGLE_API_KEY or GEMINI_API_KEY)
```

### 9.2 Camofox dan CDP saling eksklusif

`tools/browser_cdp_tool.py:466`:

> "The Camofox backend is REST-only and does not expose CDP."

Hermes bisa attach ke browser Chromium yang sudah jalan lewat
`browser.cdp_url` (`hermes_cli/config_defaults.py:577`) atau env
`BROWSER_CDP_URL`, dengan preseden:

1. `BROWSER_CDP_URL` (override live dari `/browser connect`)
2. `browser.cdp_url` di `config.yaml`

Jadi memilih Camofox berarti melepaskan seluruh permukaan tool `browser_cdp`.

### 9.3 Chrome 137 menghapus `--load-extension` — tapi hanya di build branded

Ini penyebab paling mungkin dari kegagalan "Chromium tidak bisa pasang
extension" yang dialami operator. Bukan `--no-sandbox`.

Pengumuman resmi tim Chrome (Richard Chen, 2025-04-04):

> "Starting in Chrome 137, we will remove the ability to load extensions via
> the `--load-extension` command-line flag in official Chrome branded builds...
> This change only applies to Chrome branded builds. `--load-extension` will
> continue to function as before in non Chrome brands, such as Chromium and
> Chrome For Testing."

Gejala di log: `--load-extension is not allowed in Google Chrome, ignoring.`

Chrome 139 menyusul menghapus `--extensions-on-chrome-urls` dan
`--disable-extensions-except` di build branded.

Yang tetap bisa memuat extension lewat command line:
- **Chromium** (unbranded)
- **Chrome for Testing**

Alternatif resmi untuk build branded: CDP `Extensions.loadUnpacked`, atau
WebDriver BiDi `webExtension.install`. Workaround tidak resmi yang dilaporkan
berhasil: `--disable-features=DisableLoadExtensionCommandLineSwitch`.

### 9.4 Kenapa sedikitnya wallet di addons.mozilla.org tidak menghalangi kita

Kekhawatiran yang wajar: Rabby dan banyak wallet lain hanya ada di Chrome Web
Store, dan Firefox addon lebih jarang dirawat.

Tapi AgentDrop **tidak memasang wallet dari store**. Extension
`extensions/agentdrop-wallet/` IS the provider: ia menyuntik `window.ethereum`
sendiri dan meneruskan permintaan ke daemon signing, yang bertanya ke
`tools/signing_policy.py`. Tidak ada MetaMask yang perlu terpasang.

Konsekuensi yang menguntungkan untuk Solana: dApp Solana mencari
`window.solana` (Phantom). Karena provider-nya milik kita, satu extension bisa
menyuntik `window.ethereum` DAN `window.solana` sekaligus — hal yang tidak bisa
dilakukan dengan memasang wallet pihak ketiga.

### 9.5 Perbandingan rute

| Rute | Wallet | Anti-deteksi | Extension | GUI |
|---|---|---|---|---|
| Camofox + addon Firefox (terpasang) | kita sendiri | spoofing C++ | ter-wire, 9 test | noVNC (plugin vnc) |
| Chromium/CfT + CDP | ekosistem Chrome | hilang | harus MV3 | harus bangun sendiri |
| Camofox + WalletConnect | tanpa extension | spoofing C++ | tidak perlu | noVNC |

Yang terpasang saat ini adalah rute pertama. Pindah ke Chromium berarti
kehilangan anti-deteksi Camoufox, yang justru alasan Camoufox dipilih untuk
farming; dan extension yang ada harus ditulis ulang ke Manifest V3 karena
Chrome sudah menghapus MV2.
