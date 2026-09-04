# Dua Temuan Arc 37 — Sebelum Membongkar Apa Pun

Dua hal yang diminta operator diuji dulu terhadap kode, dan **keduanya ternyata
tidak seperti yang diperkirakan**. Ditulis supaya pekerjaan berikutnya tidak
membuang waktu di jalur yang salah.

## 1. Ikatan delegasi yang mau dilepas — di worker SUDAH tidak ada

Operator: *"setiap agent bisa di call satu per satu tanpa ada ikatan delegate
dengan yg lain dulu."*

Diukur dari delapan config profil:

| Profil | `delegation` di `toolsets` | di `platform_toolsets` |
|---|---|---|
| `config/hermes/config.yaml` (default) | **ADA** | — |
| `pekerja-koordinator` | **ADA** | **ADA** (telegram) |
| `pekerja-daftar` | tidak | — |
| `pekerja-discord` | tidak | — |
| `pekerja-harian` | tidak | — |
| `pekerja-pantau` | tidak | — |
| `pekerja-quest` | tidak | — |
| `pekerja-riset` | tidak | — |
| `pekerja-x` | tidak | — |

**Ketujuh worker sudah tidak punya delegasi**, dan itu bukan kebetulan —
validator menegakkannya (`tools/validate_config.py:572`):

```python
if "delegation" in ts:
    err(f"{rel}: worker '{name}' punya toolset 'delegation' — worker "
        f"adalah leaf; mencabutnya membuat batas leaf struktural")
```

Jadi **"memanggil tiap worker satu per satu" sudah bisa hari ini** — lewat REPL
(`/worker`, Arc 35) atau perintah `/` di Telegram (Arc 29). Tidak ada ikatan yang
menghalangi.

Yang masih punya delegasi **hanya koordinator**, dan di sanalah masalahnya:
delegasi **adalah identitas koordinator**. SOUL-nya menyebut delegasi **14 kali**,
termasuk:

- baris 30 — *"**Mendelegasikan** ke worker yang tepat"* (tugas pokok #3)
- baris 34 — *"didelegasikan, saya sedang membuang keunggulan arsitektur ini"*
- baris 242 — *"Saya pakai `delegate_task` milik Hermes"*
- baris 309 — *"Setiap tugas yang menyentuh halaman web **harus** saya
  delegasikan"*

Dan koordinator **sengaja tidak punya toolset `browser`** (validator `:561`).

**Konsekuensinya:** mencabut `delegation` dari koordinator membuatnya tidak punya
browser **dan** tidak punya delegasi — ia hanya bisa bercakap-cakap. Itu bukan
menyederhanakan, itu menghapus fungsinya.

### Jadi pilihannya bukan "lepas atau tidak", tapi peran koordinator mau jadi apa

| Pilihan | Akibat |
|---|---|
| **A. Cabut delegasi, koordinator jadi meja depan** | Ia hanya mengarahkan operator ke worker yang benar. Perlu menulis ulang SOUL (14 sebutan) + membalik validator `:565`. Koordinator jadi sangat tipis. |
| **B. Cabut delegasi, koordinator ikut mengeksekusi** | Butuh memberi koordinator `browser` — melanggar batas "koordinator tidak pernah mengeksekusi" yang sudah dikunci sejak Arc 32. |
| **C. Biarkan koordinator apa adanya** | Worker tetap bisa dipanggil satu per satu (sudah bisa). Koordinator tetap berguna untuk operator yang mau cukup memberi satu instruksi. |

**Rekomendasi: C**, lalu A kalau setelah dilatih ternyata operator memang selalu
memanggil worker langsung dan tidak pernah lewat koordinator. Memutuskan sekarang
berarti menulis ulang SOUL 16 KB untuk peran yang belum terbukti tidak diperlukan.

## 2. Biaya 2-putaran-per-klik — struktural, bukan kelalaian

Operator memilih memangkas ini. Hasil pemeriksaannya:

**`browser_navigate` sudah 1 putaran** — `tools/browser_tool.py:4478`:
*"Auto-take a compact snapshot so the model can act immediately without a
separate browser_snapshot call."*

**`browser_click` 2 putaran** — `:4608-4645`, seluruh badan fungsinya hanya
membalas:

```python
response = {"success": True, "clicked": ref}
```

**Tidak ada knob config** untuk menyalakan auto-snapshot sesudah klik. Yang ada
hanya `browser.snapshot_threshold` (`:367`) — itu batas **ukuran** snapshot,
bukan saklar kapan snapshot diambil.

**Dan batch dalam satu putaran mustahil.** `_PARALLEL_SAFE_TOOLS`
(`agent/tool_dispatch_helpers.py`) isinya:

```
ha_get_state, ha_list_entities, ha_list_services, image_generate, read_file,
search_files, session_search, skill_view, skills_list, vision_analyze,
web_extract, web_search
```

**Tidak ada satu pun tool browser.** Jadi menyuruh agent memanggil
`browser_click` + `browser_snapshot` sekaligus tidak akan dijalankan paralel.

### Yang dipakai: plugin tambahan, bukan override

Hermes menyediakan `register_tool(..., override=True)`
(`hermes_cli/plugins.py:1778`) untuk menimpa tool bawaan — contoh di
docstring-nya sendiri *"swap the default `browser_navigate`"*. Tapi itu:

1. menaruh kode kita di **jalur panas setiap klik**, dan
2. butuh gate `plugins.entries.<id>.allow_tool_override: true` (dipanggil di
   `:1806`, **hanya** ketika `override=True`).

Karena integrasi dengan Hermes sungguhan belum bisa diuji dari sandbox, kita
ambil jalur **tambahan**: tool baru `browser_act` di
`plugins/agentdrop-browser/`. Tool baru **tidak butuh gate**, dan kalau plugin
gagal dimuat agent tetap punya seluruh tool browser aslinya — kegagalannya
terbatas, bukan menyeluruh.

`browser_act` melakukan aksi **lalu** snapshot dalam satu panggilan, jadi satu
aksi logis = satu putaran LLM.

Tujuh jalur diuji:

| Kasus | Yang dipanggil | Hasil |
|---|---|---|
| click sukses | `click`+`snapshot` | snapshot dikembalikan |
| **click gagal** | `click` saja | error — **snapshot tidak dipanggil** |
| **aksi OK, snapshot mati** | `click`+`snapshot` | aksi tetap dilaporkan + `snapshot_error` |
| type sukses | `type`+`snapshot` | snapshot dikembalikan |
| press sukses | `press`+`snapshot` | snapshot dikembalikan |
| click tanpa `ref` | — | pesan jelas, nol panggilan |
| action tidak dikenal | — | pesan jelas, nol panggilan |

Baris kedua dan ketiga yang penting: aksi yang gagal tidak membuang panggilan
snapshot, dan keberhasilan aksi tidak dibuang hanya karena langkah keduanya
gagal.

### Yang belum dipakai

Plugin ini **belum dipasang** ke config profil mana pun, dan **belum diuji
terhadap Hermes sungguhan**. Langkah pemasangannya butuh diverifikasi di mesin
target: di mana Hermes mencari plugin (`~/.hermes/plugins/<nama>/` menurut
catatan sebelumnya — **belum diverifikasi ulang di arc ini**), dan bagaimana
toolset `agentdrop-browser` ditambahkan ke `toolsets:` profil.
