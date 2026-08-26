---
name: x-engager
description: "Menjalankan sisi X/Twitter dari campaign airdrop — post, reply, dan verifikasi quest. Menangani DUA metode verifikasi yang dipakai proyek: OAuth (terdeteksi otomatis) dan manual (URL post ditempel ke form). Gunakan saat sebuah campaign punya task berupa Follow, Post, Quote, Reply, atau Share on X."
version: 1.0.0
author: AgentDrop
license: MIT
---

# X Engager

Skill ini untuk worker-x. Baca dulu **Protokol Browser** di SOUL.md — tidak ada
CSS selector di sini, semua elemen diambil dari snapshot.

## Langkah 0 — tentukan metode verifikasinya DULU

Jangan mulai memposting sebelum tahu metode apa yang dipakai proyek. Salah
menebak berarti post sudah tayang tapi tidak terhitung.

Cara menentukan:

1. `browser_navigate` ke halaman quest, lalu `browser_snapshot`.
2. **Cocokkan URL dan judul halaman** dengan yang ditugaskan sebelum membaca
   apa pun. Kalau tidak cocok, berhenti — Anda sedang melihat halaman lain.
3. Cari salah satu tanda ini:

| Tanda di halaman | Metode |
|---|---|
| Tombol "Verify" / "Check" / "Validate" tanpa kolom input | **OAuth** |
| Sudah ada tulisan "Connected: @username" | **OAuth** |
| Kolom input "Tweet URL" / "Post link" / "Paste your link" | **Manual link** |
| Instruksi "submit your post link after posting" | **Manual link** |
| Tidak ada keduanya | **Tidak tahu — investigasi, jangan menebak** |

Kalau setelah membaca halaman Anda masih tidak yakin, katakan tidak yakin.
Menempel URL ke form yang ternyata tidak ada, atau menunggu verifikasi otomatis
yang ternyata tidak pernah datang, sama-sama membuang campaign.

## Alur A — metode OAuth

1. Post sesuai instruksi (lihat "Membuat post" di bawah).
2. Screenshot post yang tayang.
3. Kembali ke halaman quest → `browser_navigate` → **cocokkan URL** →
   `browser_snapshot`.
4. Tekan tombol verifikasi.
5. Baca hasilnya. Tiga kemungkinan, dan Anda harus membedakan ketiganya:
   - **Terverifikasi** → status quest berubah, catat.
   - **Masih menunggu** → banyak proyek memverifikasi lewat cron mereka sendiri,
     bisa 5 menit sampai beberapa jam. Catat `menunggu`, jangan tekan tombol
     berulang-ulang.
   - **Gagal** → baca pesan errornya apa adanya dan laporkan. Jangan mengulang
     lebih dari dua kali.

## Alur B — metode manual link

Ini yang paling sering gagal, jadi jalankan berurutan.

1. Post sesuai instruksi. Screenshot.
2. **Ambil URL post.** URL post TIDAK muncul di address bar setelah posting.
   Cara mengambilnya:
   - `browser_navigate` ke `https://x.com/<username>`
   - **Cocokkan URL dan judul** — pastikan ini profil yang benar
   - `browser_snapshot`, cari post Anda dengan **mencocokkan teksnya**, bukan
     posisinya di timeline
   - URL post ada di tautan timestamp: `<a href="/<user>/status/<id>">`
   - Susun jadi `https://x.com/<user>/status/<id>`
3. **Buka URL itu.** `browser_navigate` ke URL tadi, lalu `browser_snapshot`
   dan pastikan post-nya benar-benar di sana. Langkah ini tidak boleh
   dilewati — URL yang salah membuat quest gagal dan sering tidak bisa diulang.
4. `browser_navigate` ke halaman quest → **cocokkan URL** → `browser_snapshot`.
5. Ketik URL ke kolom input memakai `browser_type` dengan `ref` dari snapshot
   terbaru.
6. Submit.
7. Baca status sesudah submit. Screenshot hasilnya.

## Membuat post

1. `browser_navigate` ke `https://x.com/compose/post` (atau klik tombol post
   dari timeline) → `browser_snapshot`.
2. Ketik teks memakai `browser_type` pada `ref` kotak compose.
3. **Baca ulang teksnya dari snapshot sebelum menekan tombol post.** Yang Anda
   niatkan dan yang ada di kotak sering berbeda — tagar bisa terpotong, mention
   bisa hilang.
4. Klik tombol post.
5. Verifikasi post tayang: bukan "sedang mengirim", tapi benar-benar muncul di
   timeline. Ambil screenshot.

Aturan isi post:

- Pakai teks yang diberikan proyek **apa adanya** kalau mereka memberi template.
  Jangan "memperbaiki" tagar atau mention — itu yang dibaca sistem mereka.
- Kalau proyek hanya memberi topik, tulis sendiri, tapi jangan mengklaim hal
  yang tidak Anda ketahui tentang proyeknya.
- Satu campaign = satu narasi. Jangan memposting hal yang bertentangan dengan
  post Anda sebelumnya di campaign yang sama.

## Batas dan rem

- **Jeda antar aksi.** Jangan memposting beruntun tanpa jeda.
- **Batas harian itu keras.** Kalau tercapai, berhenti dan lapor.
- **Akun terkunci, diminta verifikasi, atau suspensi → STOP SEKETIKA.** Lapor,
  berhenti. Jangan coba melewati, jangan bikin akun baru.
- **CAPTCHA / 2FA → STOP.** Serahkan ke manusia lewat noVNC.
- Tidak membeli follower atau engagement apa pun.

## Kalau mentok

Ikuti tangga kebuntuan di `browser-operation`: snapshot ulang → scroll → tutup
popup → back → tab baru → `browser_vision` →
berhenti dan minta manusia.

Tiga kali gagal dengan cara yang sama berarti itu bukan masalah prompt.
Berhenti dan laporkan apa yang Anda lihat, bukan apa yang Anda harapkan.
