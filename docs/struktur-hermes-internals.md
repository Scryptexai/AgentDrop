# Struktur Internal Hermes — Peta Jalur Panggilan

Dokumen ini adalah dasar Arc 35 (AgentDrop sebagai layer 2 di atas mesin Hermes).
Tujuannya satu: memastikan AgentDrop memanggil Hermes **tanpa miss call** data,
tool, maupun agent.

Semua kutipan `berkas:baris` di sini **diverifikasi dengan membaca berkasnya pada
Arc 35** terhadap sparse clone `NousResearch/hermes-agent`. Yang tidak bisa
diverifikasi dari sandbox ditandai **TIDAK TERVERIFIKASI**.

---

## 1. Tiga entry point

`pyproject.toml:392-394`:

```
hermes       = "hermes_cli.main:main"
hermes-agent = "run_agent:main"
hermes-acp   = "acp_adapter.entry:main"
```

Yang penting bagi kita: **`run_agent:main`** adalah runner agent yang sebenarnya.
`hermes_cli.main` adalah pembungkus CLI (parser, profil, subcommand) yang pada
akhirnya juga membangun objek yang sama.

Implikasi pertama dan paling penting untuk Arc 35: **mesin agent itu sebuah kelas
Python bernama `AIAgent`**, bukan binari. AgentDrop tidak perlu memanggil
`hermes` sebagai proses anak untuk menjalankannya.

## 2. `AIAgent` — mesinnya

| Apa | Di mana |
|---|---|
| `class AIAgent` | `run_agent.py:467` |
| `AIAgent.__init__` (±90 parameter) | `run_agent.py:490` |
| konstruktor mendelegasikan ke | `agent/agent_init.py:536` `init_agent()` |
| `run_conversation(...) -> Dict` | `run_agent.py:9173` → meneruskan ke `agent/conversation_loop.py:1945` |
| `chat(message, stream_callback) -> str` | `run_agent.py:9844` |
| konstruksi kanonik dari CLI | `run_agent.py:10012` |

`chat()` hanyalah pembungkus tipis:

```python
def chat(self, message, stream_callback=None) -> str:
    result = self.run_conversation(message, stream_callback=stream_callback)
    return result["final_response"]
```

**Kontrak kembalian `run_conversation`** — dibaca dari pemakaian nyata di
`run_agent.py:10042-10052`:

| Kunci | Isi |
|---|---|
| `completed` | bool — apakah agent menyelesaikan loop |
| `api_calls` | int — jumlah panggilan LLM |
| `messages` | list — seluruh pesan, termasuk tool call |
| `final_response` | str — jawaban akhir |

Ini menggantikan cara lama kita menilai keberhasilan lewat `$?` (Arc 34 Gap 1).
`completed` + `api_calls` adalah sinyal yang jauh lebih jujur.

### Parameter konstruktor yang menentukan perilaku kita

Dari `run_agent.py:490-572`, yang relevan langsung:

| Parameter | Efek |
|---|---|
| `base_url`, `api_key`, `model`, `provider`, `api_mode` | endpoint LLM |
| `enabled_toolsets` / `disabled_toolsets` | **batas lingkup worker** — inilah penegak Arc 32 |
| `max_iterations` | batas tool loop (default `sys.maxsize` = tak terbatas) |
| `session_id`, `session_db` | kelanjutan sesi |
| `platform`, `user_id`, `chat_id`, `thread_id` | identitas platform |
| `skip_context_files` | matikan injeksi SOUL.md/AGENTS.md |
| `load_soul_identity` | **tetap** pakai SOUL.md walau `skip_context_files=True` |
| `tool_start_callback`, `tool_complete_callback`, `tool_progress_callback`, `thinking_callback`, `reasoning_callback`, `stream_delta_callback`, `status_callback`, `notice_callback`, `event_callback`, `step_callback`, `clarify_callback` | **permukaan untuk merender UX** |

Baris terakhir itu adalah temuan yang membuka Arc 35: **`AIAgent` sudah
menyediakan belasan callback peristiwa.** UX ala Claude Code tidak perlu
menangkap stdout proses anak — cukup berlangganan callback ini.

## 3. Bagaimana tool ditentukan — jalur lengkap

```
config.yaml (profil)
   │  toolsets:            ← dibaca oleh jalur CLI
   │  platform_toolsets:   ← dibaca oleh jalur gateway
   │  agent.disabled_toolsets:
   ▼
hermes_cli/tools_config.py:2646  _get_platform_tools(config, platform)
   │   • baca platform_toolsets.<platform>
   │   • kalau tidak ada → PLATFORMS[platform]["default_toolset"]
   │   • kalau platform tak dikenal → "hermes-<platform>"
   ▼
toolsets.py:748   resolve_toolset(name)      ←展开 toolset komposit
toolsets.py:860   resolve_multiple_toolsets(names)
   │   TOOLSETS dict di toolsets.py:103
   ▼
model_tools.py:323  get_tool_definitions(enabled_toolsets, disabled_toolsets)
   ▼
agent/agent_init.py:1626   agent.tools = _ra().get_tool_definitions(...)
agent/agent_init.py:1634   agent.valid_tool_names = {t["function"]["name"] for t in agent.tools}
   ▼
kirim ke LLM sebagai daftar tools
```

### ⚠️ Titik rawan miss call #1 — dua kunci config yang berbeda

Ada **dua** kunci dan keduanya dipakai di jalur yang berbeda:

- **`toolsets:`** (level atas) — jalur CLI / `hermes chat`
- **`platform_toolsets.<platform>`** — jalur gateway, lewat
  `_get_platform_tools()`

Config kita memakai `toolsets:` di kedelapan profil, dan hanya koordinator yang
punya `platform_toolsets.telegram`. **Kalau AgentDrop membangun `AIAgent`
langsung tanpa membaca `toolsets:` dari config profil, worker akan mendapat
SELURUH tool** — persis cacat yang Arc 32 perbaiki. Ini bukan hipotesis: di
`run_agent.py:10012`, `enabled_toolsets` datang dari **argumen CLI**, bukan dari
config.

`agent.disabled_toolsets` **terkonfirmasi dibaca** — di
`hermes_cli/tools_config.py:2917` dan `:3036`, serta `cli.py:5514`. Jadi jaminan
"shell mati" kita nyata, bukan config hiasan.

## 4. Bagaimana SOUL.md dimuat

`agent/system_prompt.py:476`:

```python
if agent.load_soul_identity or not agent.skip_context_files:
    _soul_content = _r.load_soul_md(_ctx_len, home_override=_agent_home(agent))
```

Default `skip_context_files=False`, jadi SOUL.md **dimuat secara default**.
Kalau tidak ada SOUL.md, yang dipasang adalah `DEFAULT_AGENT_IDENTITY`
(identitas bawaan Hermes) — itulah sebabnya `.no-bundled-skills` dan SOUL.md
per profil penting.

### ⚠️ Titik rawan miss call #2 — SOUL.md dibaca dari home agent, bukan cwd

`_agent_home()` di `agent/system_prompt.py:370`, urutan resolusi:

1. **`HERMES_HOME` ContextVar override menang** (`get_hermes_home_override()`)
2. Fallback: home yang memuat `agent._session_db.db_path` (`<home>/state.db`)
3. Kalau keduanya gagal → `None`, pemanggil jatuh ke resolusi ambient

Komentar di sana menyebut bug nyata (#86313, #50233): tanpa override yang benar,
**profil default membocorkan skill dan identitasnya ke prompt bot lain.** Ini
persis jenis "miss call data" yang harus kita hindari.

## 5. Bagaimana `--profile` bekerja — dan jebakan urutannya

`hermes_cli/main.py:730`:

```python
hermes_home = resolve_profile_env(profile_name)
```

`resolve_profile_env()` di `hermes_cli/profiles.py:2571`. Docstring-nya menyatakan
dengan tegas bahwa ia **"Called early in the CLI entry point, before any hermes
modules are imported, to set the HERMES_HOME environment variable."**

`get_profile_dir()` di `hermes_cli/profiles.py:385`:

```python
def get_profile_dir(name):
    canon = normalize_profile_name(name)
    if canon == "default":
        return _get_default_hermes_home()
    return _get_profiles_root() / canon
```

### ⚠️ Titik rawan miss call #3 — urutan impor

`HERMES_HOME` harus sudah disetel **sebelum `import run_agent`**. Hermes
mengunci beberapa nilai pada saat impor. Kalau AgentDrop mengimpor dulu baru
menyetel env, kita dapat profil yang salah tanpa pesan error apa pun.

Alternatif yang lebih aman untuk proses yang melayani banyak profil:
`hermes_constants.set_hermes_home_override()` /
`reset_hermes_home_override()` — dipakai gateway di `hermes_cli/gateway.py:3948`
dan `hermes_cli/goals.py:705`.

## 6. Peta toolset (59 toolset — dijalankan, bukan dibaca)

Diperoleh dengan benar-benar mengeksekusi `toolsets.py` dan membaca
`TOOLSETS`. Yang relevan untuk kita:

| Toolset | Jumlah tool | Isi |
|---|---|---|
| **`browser`** | **14** | `browser_navigate`, `browser_snapshot`, `browser_click`, `browser_type`, `browser_scroll`, `browser_back`, `browser_press`, `browser_get_images`, `browser_vision`, `browser_console`, `browser_cdp`, `browser_dialog`, `browser_exec`, `web_search` |
| `file` | 4 | `read_file`, `write_file`, `patch`, `search_files` |
| `web` | 2 | `web_search`, `web_extract` |
| `todo` | 1 | `todo` |
| `memory` | 1 | `memory` |
| `skills` | 3 | `skills_list`, `skill_view`, `skill_manage` |
| `delegation` | 1 | `delegate_task` |
| `clarify` | 1 | `clarify` |
| `terminal` | 2 | `terminal`, `process` — **kita matikan** |
| `code_execution` | 1 | `execute_code` — **kita matikan** |
| `computer_use` | 1 | **dilarang di repo ini** |
| `hermes-cli` | 53 | komposit — **dilarang di `toolsets:`** (Arc 32) |
| `coding` | 31 | komposit |
| `kanban` | 14 | — |

Sisanya adalah toolset platform (`hermes-telegram` 53, `hermes-discord` 55,
`hermes-feishu` 58, dst.) dan integrasi (`spotify` 7, `yuanbao` 5,
`homeassistant` 4, `video_gen` 3, `desktop_ui` 11, `tts`, `vision`, `image_gen`,
`x_search`, `search`, `session_search`, `cronjob`, `project`, `safe`,
`context_engine`, `bot_room`, `debugging`).

**Untuk mode browser-penuh Arc 35**, toolset yang diperlukan hanya `browser`
(14 tool). `browser_cdp` — yang kita andalkan untuk popup wallet — **sudah
termasuk** di dalamnya, jadi tidak perlu toolset terpisah.

## 7. REPL Hermes yang sudah ada

Dua berkas yang layak ditiru, bukan dibangun ulang dari nol:

- **`cli.py`** (root repo) — **22.330 baris, 220 rujukan `prompt_toolkit`.** Ini
  REPL interaktif `hermes` yang sebenarnya. Membaca config di `cli.py:385`,
  `disabled_toolsets` di `cli.py:5514`.
- **`hermes_cli/console_engine.py`** — 1.696 baris. Mesin perintah konsol:
  `ConsoleCommand`, `ConsoleResult`, `ConsoleCommandError`
  (`:29`/`:34`/`:42`), parser argparse bersarang (`_parser_root` `:173`).

Keduanya menunjukkan pola yang benar: perintah `/...` di dalam sesi ditangani
oleh engine perintah, bukan dikirim ke LLM.

## 8. Ringkasan: apa yang wajib dilakukan AgentDrop

Agar tidak ada miss call, jembatan AgentDrop → Hermes **wajib**:

1. **Menyetel `HERMES_HOME` ke direktori profil SEBELUM mengimpor `run_agent`**
   — atau memakai `set_hermes_home_override()`.
2. **Membaca `toolsets:` dari `config.yaml` profil** dan meneruskannya sebagai
   `enabled_toolsets`. Jangan mengandalkan default.
3. **Membaca `agent.disabled_toolsets`** dan meneruskannya sebagai
   `disabled_toolsets`.
4. **Meneruskan `platform="cli"`** supaya petunjuk format yang benar disuntikkan.
5. **Meneruskan `session_id`** agar sesi per worker bertahan (Arc 29: `persist`).
6. **Menilai hasil dari `run_conversation()`** (`completed`, `api_calls`), bukan
   dari exit code.
7. **Menyediakan callback** untuk merender UX, bukan menangkap stdout.
8. **Tidak menyertakan `hermes-cli`** di toolset mana pun (Arc 32), dan tidak
   pernah `computer_use`.

## 9. Yang TIDAK bisa diverifikasi dari sandbox

- **Di mana installer resmi Hermes menaruh lingkungan Python-nya.** Egress ke
  `hermes-agent.nousresearch.com` diblokir, jadi isi `install.sh` upstream tidak
  bisa dibaca. Ini menentukan apakah `import run_agent` bisa dilakukan dari
  Python kita, dan interpreter mana yang harus dipakai.
- Perilaku `run_conversation()` terhadap endpoint sungguhan.
- Kehadiran target `chrome-extension://` untuk prosedur popup wallet.
- Eksekusi `hermes cron` yang sebenarnya.

Butir pertama adalah satu-satunya yang menghambat rancangan, dan rancangan Arc 35
dibuat supaya **tidak perlu menebaknya**: interpreter Hermes ditemukan saat
runtime dari shebang binari `hermes` yang sudah ada di PATH.
