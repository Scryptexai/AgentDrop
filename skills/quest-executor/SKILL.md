---
name: quest-executor
description: "Kerjakan campaign airdrop multi-langkah di platform quest (Galxe, Layer3, Zealy, Instruct), memisahkan task otomatis dari task yang butuh manusia."
version: 1.0.0
author: AgentDrop
license: MIT
platforms: [linux, macos]
metadata:
  hermes:
    tags: [airdrop, quest, galxe, layer3, zealy, browser]
    related_skills: [daily-executor, portfolio-tracker]
---

# Quest Executor

Mengerjakan campaign multi-langkah untuk akun milik operator, dengan pemisahan
tegas antara yang bisa dikerjakan agent dan yang wajib dikerjakan manusia.

## Kapan dipakai

**Sebelum menyentuh tombol, baca dulu:**

- `knowledge/patterns/format-task.md` — format task dan bukti keberhasilannya
- `knowledge/patterns/alur-airdrop.md` — posisi tahap ini dalam alur, supaya
  tidak klaim sebelum snapshot
- `knowledge/patterns/kualifikasi.md` — "selesai" bukan berarti "terhitung"
- `knowledge/projects/<nama>.md` — apa yang sudah pernah dikerjakan

**Sesudah selesai, tulis balik** hasilnya ke `knowledge/projects/<nama>.md`:
task mana yang berhasil, mana yang gagal dan kenapa, bukti apa yang terkumpul.


```bash
hermes --profile worker-quests chat -q "Kerjakan campaign ini: https://app.galxe.com/quest/..."
```

## Langkah 0 — verifikasi alamat sebelum bertindak

Jangan pernah berasumsi tab yang Anda tempati menampilkan halaman yang Anda
kira. Di setup AgentDrop, agent dan manusia memakai **satu browser yang sama**
lewat noVNC — jadi tab yang sedang aktif bisa saja tab yang baru dibuka operator
untuk login atau menyelesaikan CAPTCHA, bukan tab quest Anda.

(Catatan: penjelasan lama di sini menyebut `adopt_existing_tab` dan
`session_key`. Keduanya kunci `browser.camofox.*` di Hermes dan **tidak
berlaku** — AgentDrop memakai CDP, bukan Camofox. Risikonya tetap nyata, hanya
sebabnya berbeda: berbagi browser dengan manusia.)

Urutan wajib setiap kali mulai atau pindah halaman:

1. `browser_navigate(URL_yang_dimaksud)` — eksplisit, jangan mengandalkan tab
   yang kebetulan terbuka
2. `browser_snapshot`
3. **Cocokkan URL + judul di snapshot dengan yang Anda harapkan.** Tidak cocok
   → navigasi ulang sekali → masih tidak cocok → **hentikan dan lapor**

Salah klik di dashboard crypto bisa mahal. Bertindak di halaman yang belum
terkonfirmasi identitasnya bukan efisiensi, itu risiko.

## Langkah 1 — Klasifikasi SEMUA task sebelum menyentuh tombol

Buka halaman campaign, baca **semua** syarat (bukan hanya judul), lalu
klasifikasikan tiap task:

| Kelas | Contoh | Siapa |
|---|---|---|
| `auto` | follow Twitter, join Discord, baca artikel, jawab quiz | agent |
| `human` | sign message wallet, bridging, deposit, swap, KYC, verifikasi identitas | **operator** |
| `blocked` | CAPTCHA, 2FA, verifikasi SMS | **operator** |

Tuliskan rencana + jumlah `human` **sebelum** mulai. Ini yang membuat operator
tahu sejak awal berapa banyak pekerjaan yang tersisa untuk mereka.

## Langkah 2 — Eksekusi task `auto`, satu per satu

- **Satu task, satu verifikasi.** Jangan batch beberapa task lalu berharap
  semuanya berhasil.
- Setelah tiap task, **baca ulang UI**: status berubah jadi selesai?
- Screenshot bukti.
- Kalau sebuah task gagal: retry sekali, lalu lewati dan catat. Jangan biarkan
  satu task macet menghentikan seluruh campaign.

## Langkah 3 — Berhenti di task `human`

Catat task itu, jelaskan **persis** apa yang harus dilakukan operator (halaman
mana, tombol mana, kenapa agent tidak boleh), lalu lanjut ke task berikutnya.

## Aturan keras

- **Saya tidak pernah menandatangani atau mengonfirmasi apa pun.** Batas saya
  tegas dan tidak bergeser:
  - **Boleh** — menyiapkan: buka halaman, isi form, pilih jaringan/jumlah, klik
    tombol yang **memunculkan** popup wallet (termasuk untuk bridge atau
    deposit).
  - **Tidak boleh** — menekan `Confirm`/`Sign`/`Approve` di dalam popup wallet
    itu, atau menyentuh apa pun setelahnya.
  - Begitu popup wallet muncul → **stop di situ**, tandai `needs_human`,
    serahkan ke operator lewat noVNC.
  - Kalau popup **tidak** muncul, itu kegagalan untuk dilaporkan — bukan
    sesuatu yang diakali dengan cara lain.

  Kenapa batasnya di popup, bukan di awal: kalau saya berhenti sebelum mengisi
  form, operator harus mengulang seluruh langkah saya. Kalau saya menekan
  Confirm, saya telah menandatangani transaksi dengan dana nyata.
  `docs/arsitektur-alur.md` bagian 3 memuat aturan yang sama.
- **Tidak ada private key / seed phrase** di mana pun, termasuk screenshot.
  Sebelum menyimpan screenshot, pastikan tidak ada seed yang terlihat di layar.
- **CAPTCHA / 2FA → STOP.** Serahkan ke manusia (pola "Take Over" Manus).
  Beri tahu operator: buka **`http://localhost:6080/vnc.html`**, selesaikan di
  sana. Browser-nya GUI sungguhan dan sesi-nya sama dengan yang Anda pakai,
  jadi setelah operator selesai Anda tinggal lanjut.
- **Kalau UI berubah dan rencana tidak cocok lagi, berhenti dan tanya.** Jangan
  menebak-nebak tombol — salah klik di dashboard crypto bisa mahal.
- **Hormati rate limit.** Jangan spam request ke platform.

## Output

`data/campaigns/<name>/quest-run.json`:

```json
{
  "campaign": "nama",
  "platform": "galxe",
  "url": "https://...",
  "run_at": "2026-08-25T14:12:03+08:00",
  "tasks_total": 12,
  "tasks_done_auto": 8,
  "tasks_pending_human": 4,
  "tasks_failed": 0,
  "pending_human": [
    {"task": "Sign message to verify wallet", "reason": "wallet_signature"}
  ],
  "evidence": ["screenshots/2026-08-25-task-3.png"]
}
```
