---
name: quest-executor
description: "Kerjakan campaign airdrop multi-langkah di platform quest (Galxe, Layer3, Zealy, Intract), memisahkan task otomatis dari task yang butuh manusia."
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
hermes --profile pekerja-quest chat -q "Kerjakan campaign ini: https://app.galxe.com/quest/..."
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
| `auto` | follow Twitter, join Discord, baca artikel, jawab quiz | agent, sampai selesai |
| `wallet` | connect/sign wallet, bridging, deposit, swap, mint, claim, approve | **agent, sampai selesai** — termasuk menekan `Confirm`/`Sign`/`Approve` |
| `auto` | login, signup, OAuth | **agent** — akun miliknya, kredensial tersedia |
| `human` | KYC, verifikasi identitas, CAPTCHA, 2FA, OTP | **operator** — agent tidak menyentuh |
| `blocked` | CAPTCHA, 2FA, verifikasi SMS | **operator** |

Tuliskan rencana + jumlah `human` **sebelum** mulai. Jumlah `human` harus kecil
— hanya KYC, CAPTCHA, 2FA, dan OTP. Login BUKAN `human`: akun yang dipakai
agent memang dibuat untuknya. Kalau sebuah campaign ternyata punya
banyak task `human`, laporkan itu sebagai temuan.

## Langkah 2 — Eksekusi task `auto`, satu per satu

- **Satu task, satu verifikasi.** Jangan batch beberapa task lalu berharap
  semuanya berhasil.
- Setelah tiap task, **baca ulang UI**: status berubah jadi selesai?
- Screenshot bukti.
- Kalau sebuah task gagal: retry sekali, lalu lewati dan catat. Jangan biarkan
  satu task macet menghentikan seluruh campaign.

## Langkah 3 — Kerjakan task `wallet` sampai selesai

Untuk setiap task `wallet` (connect/sign wallet, bridging, deposit, swap, mint,
claim, approve):

1. Buka halaman, isi form, pilih jaringan dan jumlah.
2. Klik tombol yang memunculkan popup wallet.
3. **Baca isi popup-nya** — kontrak, jumlah, jaringan, nama fungsi. Halaman bisa
   berbohong; popup tidak.
4. Tekan `Confirm`/`Sign`/`Approve`.
5. **Catat apa yang disetujui** ke laporan: fungsi, kontrak/spender, jumlah,
   chain. Untuk `approve` unlimited, catat token dan spender-nya supaya bisa
   di-revoke nanti.
6. **Verifikasi hasilnya** — status berubah, tx hash muncul, atau saldo bergerak.
   Popup tertutup bukan bukti berhasil.

Kalau popup tidak muncul, itu kegagalan untuk dilaporkan — bukan sesuatu yang
diakali dengan cara lain.

## Langkah 4 — Lewati task `human` dan `blocked`

Catat task itu, jelaskan **persis** apa yang harus dilakukan operator (halaman
mana, tombol mana, kenapa agent tidak boleh), lalu lanjut ke task berikutnya.

## Aturan keras

- **Signing saya selesaikan sendiri, jadi catatan saya satu-satunya jejak.**
  Sistem ini dirancang berjalan saat operator offline; ~200 approval sehari
  tidak mungkin diserahkan ke manusia. Konsekuensinya:
  - **Baca popup sebelum menekan** — kontrak, jumlah, jaringan, nama fungsi.
  - **Catat setiap approval** — fungsi, kontrak/spender, jumlah, chain.
  - **`approve` unlimited boleh**, catat token dan spender-nya untuk revoke.
  - **Halaman dan popup tidak cocok → catat sebagai peringatan, terus jalan.**
    Itu sinyal situs mencurigakan yang harus terlihat di laporan, bukan alasan
    berhenti di tengah campaign.
  - **Popup tidak muncul → kegagalan untuk dilaporkan**, bukan diakali.

  Yang tetap tidak boleh: private key / seed phrase dalam bentuk apa pun;
  transaksi yang **mengirim dana keluar** kecuali task memintanya eksplisit
  (approve bukan transfer); CAPTCHA, 2FA, OTP, KYC tetap milik operator.

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
