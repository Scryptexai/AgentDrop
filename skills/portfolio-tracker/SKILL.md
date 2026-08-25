---
name: portfolio-tracker
description: "Lacak progres semua campaign airdrop, deteksi anomali, dan hasilkan laporan harian/mingguan yang jujur soal apa yang terverifikasi."
version: 1.0.0
author: AgentDrop
license: MIT
platforms: [linux, macos]
metadata:
  hermes:
    tags: [airdrop, tracking, reporting, monitoring, portfolio]
    related_skills: [daily-executor, quest-executor, airdrop-analyzer]
---

# Portfolio Tracker

Melacak progres seluruh campaign, memverifikasi klaim worker lain, dan memberi
operator gambaran yang bisa dipercaya.

## Kapan dipakai

```bash
hermes --profile worker-monitor chat -q "Buat ringkasan progres mingguan semua campaign"
```

## Struktur data

```
data/
├── campaigns/
│   └── <project-name>/
│       ├── info.json          # detail proyek + hasil analisis 4 dimensi
│       ├── progress.json      # progres harian (ditulis daily-executor)
│       ├── quest-run.json     # hasil eksekusi quest (ditulis quest-executor)
│       ├── discord-log.json   # aktivitas komunitas (ditulis discord-engager)
│       └── screenshots/       # bukti
└── logs/
    ├── YYYY-MM-DD-daily.md
    └── agent.log
```

## Tugas

### 1. Verifikasi tengah hari
- Baca semua `progress.json`.
- Cocokkan dengan log pagi. Yang diklaim selesai — ada buktinya? Screenshot ada?
  Timestamp masuk akal?
- **Klaim tanpa bukti = temuan.** Laporkan, jangan diam-diam menerima. Worker
  yang melaporkan sukses palsu lebih berbahaya daripada worker yang gagal.

### 2. Deteksi anomali
Tandai:
- `status` selain `ok`
- Campaign tidak jalan padahal jatuh tempo
- Poin tidak naik beberapa hari berturut-turut
- Screenshot hilang / timestamp tidak konsisten
- Alamat wallet yang tidak dikenali operator

### 3. Laporan

**Harian** (`data/logs/YYYY-MM-DD-daily.md`): apa yang jalan, apa yang gagal,
apa yang butuh manusia.

**Mingguan**: per campaign — hari aktif, total poin, tren, dan **rekomendasi
LANJUT / EVALUASI / BERHENTI**.

## Prinsip kejujuran data

1. **Jangan pernah mengarang angka.** Field kosong lebih baik daripada angka
   karangan.
2. **Pisahkan fakta dari perkiraan.** Poin tercatat = fakta. Estimasi nilai
   token = perkiraan, wajib diberi label `estimate`.
3. **Kalau data tidak cukup, tulis "data tidak cukup".** Jangan isi celah
   dengan tebakan yang terdengar meyakinkan.
4. **Rekomendasi BERHENTI itu sah.** Strategi 2026 adalah fokus 3–5 proyek,
   bukan 50. Menyarankan membuang campaign yang tidak produktif adalah bagian
   dari pekerjaan ini.
5. **Confidence < 0.7 → minta review manusia.**

## Format laporan mingguan

```
RINGKASAN MINGGUAN — [rentang tanggal]

Per campaign:
  [nama]  hari aktif: N/7  poin: X (+Y)  status: ok
    → rekomendasi: LANJUT / EVALUASI / BERHENTI
    → alasan: ...

Butuh tindakan manusia:
  - [daftar]

Anomali:
  - [daftar, atau "tidak ada"]

Catatan kejujuran data:
  - [apa yang tidak bisa saya verifikasi dan kenapa]
```
