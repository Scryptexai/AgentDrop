---
name: daily-executor
description: "Jalankan check-in dan aksi harian untuk semua campaign airdrop aktif, dengan bukti screenshot dan verifikasi state."
version: 1.0.0
author: AgentDrop
license: MIT
platforms: [linux, macos]
metadata:
  hermes:
    tags: [airdrop, automation, daily, browser, checkin]
    related_skills: [portfolio-tracker, quest-executor]
---

# Daily Executor

Menjalankan rutinitas harian farming airdrop untuk akun milik operator, dan
membuktikan bahwa setiap aksi benar-benar terjadi.

## Kapan dipakai

**Sebelum mulai, baca dulu:**

- `knowledge/patterns/format-task.md` — tujuh format task dan cara mengerjakannya
- `knowledge/meta/siklus.md` — di tahap apa siklus ini sekarang
- `knowledge/patterns/sidik-jari.md` — tanda tangan otomatisasi yang harus
  dihindari, karena daily check-in adalah aksi paling repetitif yang agent
  lakukan dan paling mudah terdeteksi

**Sesudah selesai, tulis balik** temuan baru ke `knowledge/projects/<nama>.md`:
task yang berubah, tombol yang pindah, syarat yang baru muncul. Worker besok
membaca itu.


Dijadwalkan otomatis lewat cron Hermes (lihat `scripts/install-cron.sh`), atau
manual:

```bash
hermes --profile pekerja-harian chat -q "Jalankan daily check-in untuk semua campaign aktif"
```

Perhatikan `-q`. `hermes chat` **tidak menerima argumen posisional** — hanya
`-q/--query` atau `--query-file` (lihat `hermes_cli/_parser.py`).

## Rutinitas

### Langkah 1 — Baca state, jangan langsung buka browser
1. Baca `data/campaigns/*/info.json` dan `progress.json`.
2. Tentukan campaign yang jatuh tempo hari ini (`next_action`,
   `next_action_time`).
3. Cek aksi kemarin. Yang menggantung → prioritas pertama.

### Langkah 2 — Eksekusi per campaign

> **WAJIB SEBELUM APA PUN: navigasi eksplisit, lalu verifikasi alamat.**
> Jangan pernah berasumsi tab yang Anda tempati menampilkan halaman yang Anda
> kira. Agent dan operator memakai **satu browser yang sama** lewat noVNC, jadi
> tab yang sedang aktif bisa saja tab yang dibuka operator untuk login atau
> CAPTCHA, bukan tab dashboard Anda.
>
> Urutannya selalu: `browser_navigate(URL_yang_dimaksud)` → `browser_snapshot`
> → **cocokkan URL/judul di snapshot dengan yang Anda harapkan**. Kalau tidak
> cocok, navigasi ulang sekali; kalau masih tidak cocok, hentikan dan lapor.
> Jangan bertindak di atas halaman yang belum Anda pastikan identitasnya.

1. Buka URL campaign dengan `browser_navigate`.
2. **Verifikasi status login sebelum apa pun.** Sesi mati → hentikan campaign
   itu, set `status: login_expired`, beri tahu operator. **Jangan coba login
   sendiri** — kredensial bukan urusan agent.
3. Lakukan aksi harian (check-in, claim, dsb).
4. **Screenshot bukti** → `data/campaigns/<name>/screenshots/YYYY-MM-DD-<aksi>.png`.
5. Update `progress.json`.

### Langkah 3 — Verifikasi (bagian terpenting)
Jangan pernah menyimpulkan berhasil dari "klik terasa berhasil". Baca ulang
state:
- Counter poin naik?
- Tombol berubah jadi "Claimed"/"Completed"?
- Timestamp "last claim" berubah?

**Kalau tidak ada perubahan yang bisa dibaca ulang, aksi itu GAGAL.** Catat
sebagai gagal. Laporan optimis yang salah lebih merusak daripada laporan gagal
yang jujur.

### Langkah 4 — Lapor
Ringkasan harian → `data/logs/YYYY-MM-DD-daily.md`.

## Skema progress.json

```json
{
  "campaign": "nama-campaign",
  "last_run": "2026-08-25T09:04:11+08:00",
  "days_active": 7,
  "total_days": 30,
  "today_actions": ["check_in", "claim"],
  "points_today": 150,
  "total_points": 1050,
  "status": "ok",
  "issues": [],
  "next_action": "check_in",
  "next_action_time": "2026-08-26T09:00:00+08:00",
  "evidence": "screenshots/2026-08-25-checkin.png"
}
```

`status` yang valid: `ok`, `login_expired`, `captcha_blocked`, `failed`,
`needs_human`, `paused`.

## Aturan

- **Tidak pernah melewati check-in harian.** Konsistensi jangka panjang adalah
  seluruh nilai strategi 2026.
- **Gagal → retry SATU kali → masih gagal → berhenti dan lapor.**
- **Screenshot untuk setiap aksi selesai.** Tanpa bukti = belum terjadi.
- **CAPTCHA / 2FA / verifikasi apa pun → STOP.** Set `captcha_blocked`, beri
  tahu operator, lanjut ke campaign berikutnya. Agent tidak memecahkan
  tantangan verifikasi.

  Cara menyerahkan ke manusia (browser di sini GUI, bukan headless):
  beri tahu operator untuk membuka **`http://localhost:6080/vnc.html`** dan
  menyelesaikan verifikasinya langsung di sana. Sesi itu sesi yang sama dengan
  yang Anda pakai — login tersimpan di profil Chrome
  (`~/.agentdrop/chrome-profile`), jadi setelah operator selesai Anda bisa
  lanjut tanpa perlu login ulang.
  Kalau sesi login mati total, operator login lagi lewat noVNC
  (`agentdrop browser`, lalu http://localhost:6080/vnc.html) — bukan Anda.
- **Signing saya selesaikan sendiri.** Buka halaman, isi form, pilih jumlah,
  klik tombol yang memunculkan popup wallet, **baca isi popup-nya**, tekan
  `Confirm`/`Sign`/`Approve`, lalu catat apa yang disetujui (fungsi, kontrak,
  jumlah, chain) ke laporan harian. `approve` unlimited boleh — catat token dan
  spender-nya. Popup yang tidak muncul adalah kegagalan untuk dilaporkan, bukan
  sesuatu yang diakali. Yang tetap `needs_human`: CAPTCHA, 2FA, OTP, KYC.
- **Tidak ada private key / seed phrase** di prompt, file, log, atau screenshot.
- **Log setiap aksi dengan timestamp.**
