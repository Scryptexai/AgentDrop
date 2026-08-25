---
name: airdrop-analyzer
description: "Evaluasi proyek airdrop dengan filter 4 dimensi (Team, Product, Narrative, Timing) dan keluarkan keputusan PRIORITIZE / CONSIDER / SKIP."
version: 1.0.0
author: AgentDrop
license: MIT
platforms: [linux, macos]
metadata:
  hermes:
    tags: [airdrop, research, analysis, crypto, due-diligence]
    related_skills: [portfolio-tracker]
---

# Airdrop Project Analyzer

Menilai apakah sebuah proyek airdrop layak difarming **sebelum** operator
mengeluarkan waktu atau modal.

## Kapan dipakai

Saat operator memberi URL, nama proyek, atau deskripsi sebuah airdrop dan
bertanya "ini layak nggak?".

## Kerangka: 4 Dimensi (Sniper approach)

Sumber: prinsip farming yang dipublikasikan @0xsexybanana, HTX Insights,
23 Mar 2026. Ide intinya — singkirkan "industrial garbage" dari firing range
sebelum modal dikeluarkan. Kebalikannya juga berlaku: proyek yang lolos filter
belum tentu sukses, tapi yang gagal filter hampir pasti tidak.

### 1. TEAM — cerdas, eksekusi kuat, niat baik
Ketiganya wajib, tidak ada yang bisa dikorbankan.

Cara menilai:
- Baca tweet/konten founder. Ada insight nyata tentang industrinya, atau hanya
  slogan dan shilling?
- Apakah mereka menunjukkan rekam jejak eksekusi (produk rilis, masalah
  diselesaikan) atau hanya janji?
- Kalau ada kesempatan interaksi langsung: rendah hati atau arogan?

Sinyal buruk: founder yang kontennya kosong dan hanya tahu cara berteriak.

### 2. PRODUCT — Product-Market Fit
Tiga sub-dimensi:
- (a) Produk punya PMF yang jelas.
- (b) Delivery-nya kompeten.
- (c) Tim bertanggung jawab atas kualitas.

Cara menilai: apakah mereka pernah merilis versi penuh error dasar ke pengguna?
Pembanding yang dipakai sumber: OKX tidak pernah menyerahkan produk penuh
kesalahan tingkat rendah, baik di tahap awal maupun matang.

Sinyal buruk: outage berulang, rollback, kompensasi massal, fitur baru yang
terasa asal jadi. "Growth running ahead of the product" adalah tanda tim tanpa
pengalaman operasional.

### 3. NARRATIVE — naratif baru yang belum terfalsifikasi
- Apakah naratif ini punya ruang hype di Web3?
- Apakah ia selaras dengan tren investasi Web2 (mis. AI, robotika)?

Logika hype keduanya sering tersinkron. Sumber memberi contoh taruhan besar
pada Openmind karena AI + robotika adalah darling triliun dolar di Web2 dan
belum terfalsifikasi di Web3.

### 4. TIMING & COST
- Apakah sentimen pasar sangat FOMO, atau sangat pesimis?
- Apakah biaya partisipasi rendah atau tinggi?

**Aturan tegas dari sumber: "Kalau Anda merasa ragu, lebih baik tidak ikut."**

Ketika sebuah peluang difarming semua orang, profit pool pasar tidak sanggup
menanggung volumenya: airdrop besar jadi kecil, kecil jadi nihil, nihil jadi
rugi. FOMO terdeteksi ketika feed penuh influencer airdrop yang mengajak
farming dan semua orang bullish.

## Format output

```
Project: [nama]
Overall Score: [1-10]
Decision: [PRIORITIZE / CONSIDER / SKIP]

Reasoning:
- Team:      [analisis + bukti spesifik]
- Product:   [analisis + bukti spesifik]
- Narrative: [analisis + bukti spesifik]
- Timing:    [analisis + bukti spesifik]

Recommended Actions:
- [3-5 aksi spesifik]
- Estimasi durasi: X minggu
- Akun yang dibutuhkan: [...]

Evidence:
- [URL — tanggal diakses]

Confidence: [0.0-1.0]
Unverified:
- [apa yang tidak bisa saya cek]
```

## Aturan

1. **Bersikap kejam.** Default ke SKIP. Sebagian besar proyek tidak lolos.
2. **Setiap klaim butuh URL + tanggal.** Tidak bisa diverifikasi → tulis di
   bagian `Unverified`, jangan disajikan sebagai fakta.
3. **Confidence < 0.7 → minta review manusia**, jangan putuskan sendiri.
4. **Jangan pernah merekomendasikan proyek tanpa PMF jelas.**
5. **Skill ini hanya menilai.** Tidak mengeksekusi campaign, tidak menyentuh
   wallet, tidak ada private key.
6. **Skor adalah penilaian, bukan janji.** Selalu sebutkan itu.
