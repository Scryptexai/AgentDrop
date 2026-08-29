---
name: airdrop-intake
description: "Parse pengumuman airdrop mentah dari Telegram, klasifikasi tiap task (auto/human/recurring/unknown), dan susun rencana eksekusi sebelum apa pun dikerjakan."
version: 1.0.0
author: AgentDrop
license: MIT
platforms: [linux, macos]
metadata:
  hermes:
    tags: [airdrop, parsing, orchestration, delegation, telegram, intake]
    related_skills: [quest-executor, daily-executor, airdrop-analyzer]
---

# Airdrop Intake

Mengubah pengumuman airdrop mentah — forward dari channel, penuh emoji dan
bullet `➖` — menjadi rencana eksekusi terstruktur.

## Kenapa skill ini ada

**Setiap airdrop punya format task berbeda, aturan berbeda, dan kebutuhan
berbeda.** Tidak ada parser generik yang aman. Yang bisa dilakukan adalah
mengklasifikasi dengan hati-hati, menandai yang tidak pasti sebagai `unknown`,
dan **menginvestigasi** yang tidak pasti sebelum menyentuh apa pun.

Skill ini adalah langkah WAJIB pertama. Tidak ada eksekusi tanpa intake.

**Sebelum mem-parse, baca dulu:**

- `knowledge/patterns/format-task.md` — tujuh format task yang sudah dikenal,
  lengkap dengan cara eksekusi, bukti keberhasilan, dan titik hentikan manusia
  untuk masing-masing. Format yang sudah dikenal **tidak perlu** ditandai
  `unknown` dan diinvestigasi ulang.
- `knowledge/projects/<nama>.md` kalau proyeknya sudah pernah diintake.

**Sesudah mengklasifikasi, tulis balik** format baru ke
`knowledge/patterns/format-task.md`. File itu **dirancang untuk ditulis**, dan
intake adalah tempat format baru pertama kali terlihat.


## Langkah 1 — Parse

Dari teks pengumuman, ekstrak:

| Field | Cara mengenalinya |
|---|---|
| `project` | Judul, biasanya setelah emoji 🔈/🚀/📢 |
| `register_url` | URL pertama, sering punya kode referral (`?r=`, `/r/`, `?ref=`) |
| `referral_code` | Nilai di parameter referral — **pertahankan apa adanya** |
| `raw_tasks` | Baris ber-bullet (`➖`, `-`, `•`, angka) |
| `claims` | Klaim reward ("Confirmed", "up to $10") — catat, **jangan dipercaya** |
| `extra_links` | Link lain (channel, bot, docs) |

Kalau ada klaim reward, simpan sebagai `unverified_claim`. Pengumuman channel
sering melebih-lebihkan dan kadang menipu.

## Langkah 2 — Klasifikasi tiap task

| Kelas | Pemicu | Penanganan |
|---|---|---|
| `auto` | Register, isi form, follow, join, baca artikel, quiz | agent kerjakan |
| `wallet` | "Connect EVM Wallet", sign message, bridge, deposit, swap, approve | **agent kerjakan sampai selesai**, termasuk menekan `Confirm`/`Sign`/`Approve` |
| `human:oauth` | "Connect Twitter/X/Discord/Telegram/GitHub" | **operator** via noVNC |
| `human:inbox` | "Submit Email", "Verify Email" | **operator** — butuh akses inbox |
| `human:kyc` | KYC, verifikasi identitas, selfie, paspor | **operator** |
| `recurring` | "Daily Mission", "Daily Check-in", "Daily Task" | agent + **buat cron job** |
| `blocked` | CAPTCHA, 2FA, verifikasi SMS | **operator** |
| `unknown` | Apa pun yang tidak cocok | **investigasi dulu** |

### Jebakan yang paling sering terjadi

**"Connect EVM Wallet" ≠ "Submit EVM Address."**

- `Connect EVM Wallet` → situs meminta **signature** → `wallet`. Agent
  mengerjakan seluruhnya: buka halaman, isi form, klik tombol yang memunculkan
  popup, baca isi popup, tekan `Confirm`/`Sign`/`Approve`, catat apa yang
  disetujui
- `Submit EVM Address` → situs hanya minta **alamat publik** → `auto` (alamat
  dibaca dari `.env`, `WALLET_ADDRESS_FARMING`), agent boleh mengerjakan

Salah mengklasifikasi yang pertama sebagai `auto` berarti agent mencoba
menandatangani transaksi. Itu batas yang tidak boleh dilewati.

**"Connect Twitter" bukan `auto`.** Meski terdengar sederhana, ini alur OAuth
di domain pihak ketiga — butuh login akun operator. Masuk `human:oauth`.

**"Complete Easy Task" / "Complete Task" selalu `unknown`.** Namanya tidak
memberi informasi apa pun. Buka halamannya, baca syaratnya, baru klasifikasi.

## Langkah 3 — Investigasi yang `unknown`

Untuk setiap task `unknown`:

1. `browser_navigate` ke URL campaign (bukan dari tab yang kebetulan terbuka)
2. `browser_snapshot`
3. **Cocokkan URL + judul** dengan yang diharapkan — agent dan operator memakai
   **satu browser yang sama** lewat noVNC, jadi tab aktif bisa saja tab yang
   dibuka operator untuk login, bukan tab campaign Anda
4. Baca syarat task itu
5. Klasifikasi ulang berdasarkan apa yang **Anda baca**, bukan apa yang Anda
   duga

Kalau setelah investigasi masih ambigu → tetap `unknown`, dan laporkan ke
operator apa adanya. **Jangan menebak.**

## Langkah 4 — Deteksi aturan spesifik proyek

Sebelum eksekusi, cari tahu dan catat:

- **Apakah butuh wallet sama sekali?** Kalau ya, chain apa (EVM/Solana/lainnya)?
- **Apakah ada syarat harian?** → butuh cron, bukan sekali jalan
- **Apakah ada minimum aktivitas?** (mis. "minimal 5 hari")
- **Apakah ada batas waktu / snapshot date?**
- **Apakah referral wajib?** Kalau URL punya kode referral, pertahankan — jangan
  pernah mendaftar lewat URL polos kalau operator memberi URL berkode
- **Apakah ada larangan multi-akun di ToS-nya?** Kalau ada, catat dan ingatkan
  operator

## Langkah 5 — Output

Tulis hasilnya ke **`data/campaigns/<nama-proyek>/info.json`**. Berkas ini
dibaca `daily-executor` dan `pekerja-pantau`, jadi kalau tidak ditulis, keduanya
kehilangan konteks proyek dan bekerja tanpa tahu chain, referral, atau syarat
proyeknya.

```json
{
  "project": "NamaProyek",
  "register_url": "https://...",
  "referral_code": "XXXXXX",
  "source_claim": {"reward": "...", "status": "unverified_claim"},
  "tasks": [
    {"seq": 1, "raw": "Register", "class": "auto", "evidence": "form pendaftaran"},
    {"seq": 2, "raw": "Connect Twitter", "class": "human:oauth", "evidence": "OAuth di x.com"},
    {"seq": 3, "raw": "Complete Easy Task", "class": "unknown", "evidence": "syarat ambigu setelah dibuka"}
  ],
  "counts": {"auto": 3, "human": 2, "recurring": 1, "unknown": 1},
  "needs_cron": [{"task": "Daily Mission", "schedule": "0 9 * * *"}],
  "project_rules": ["butuh EVM wallet", "referral wajib"],
  "confidence": 0.8,
  "recommendation": "LANJUT / TUNGGU KLARIFIKASI / TOLAK"
}
```

## Langkah 6 — Delegasi (hanya setelah operator setuju)

Orchestrator memakai `delegate_task`:

```
tasks: [
  {goal: "Eksekusi task auto untuk <proyek>", role: "leaf"},
  {goal: "Buat cron daily untuk Daily Mission <proyek>", role: "leaf"}
]
```

Selalu sertakan `output_schema` agar jawaban child terstruktur.

## Aturan

1. **Intake dulu, eksekusi kemudian.** Tidak ada pengecualian.
2. **`unknown` berarti investigasi, bukan tebakan.**
3. **Tidak ada signature wallet, transaksi, bridging, deposit.**
4. **Tidak ada private key / seed phrase** — alamat publik saja.
5. **CAPTCHA / 2FA / OAuth → operator**, lewat `http://localhost:6080/vnc.html`.
6. **Jangan pernah membuang kode referral** dari URL yang operator berikan.
7. **Klaim reward adalah klaim**, bukan fakta. Selalu beri label `unverified`.
8. **Confidence < 0.7 → minta klarifikasi operator**, jangan lanjut.
