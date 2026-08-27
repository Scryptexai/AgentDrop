# Sidik jari otomatis — bagaimana agent terdeteksi

**Ini berkas yang paling langsung tentang kita.** Sistem ini menjalankan
browser secara otomatis untuk mengejar airdrop. Deteksi otomatis adalah
musuh utamanya, dan musuhnya spesifik — bukan "terlalu sering", melainkan
**pola yang tidak mungkin dihasilkan manusia**.

---

## Empat tanda yang disebut eksplisit dalam riset 2026

Riset meta 2026 menyebutkan pola-pola ini dengan nama:

1. **Transaksi batch** — banyak aksi digabung, atau banyak tx beruntun tanpa jeda
2. **Pemakaian gas yang terlalu optimal** — manusia tidak konsisten; bot iya
3. **Urutan interaksi yang kaku** — selalu langkah yang sama, selalu lengkap
4. **Pola waktu yang mekanis** — tepat setiap 24 jam, pada jam yang sama

Keempatnya adalah **produk sampingan dari otomatisasi yang rapi**. Ironinya:
semakin efisien agent, semakin mudah terdeteksi.

---

## Sidik jari gas — yang paling teknis dan paling diabaikan

> "clusters where 300 wallets all used 25 gwei priority fees have been flagged"

Gas bukan angka acak. Setiap klien wallet **menghitungnya berbeda secara
default**:

> "use different wallet clients — MetaMask, Rabby, Frame, Keplr, Phantom each
> compute gas differently by default"

**Konsekuensi desain AgentDrop:** memasang MetaMask + OKX + Phantom bukan
redundansi. Tiap klien menghasilkan sidik jari gas yang berbeda secara alami.
Memakai satu klien untuk sepuluh wallet justru membuat kesepuluhnya identik —
persis pola klaster yang dicari.

Sebaliknya, **ekstensi bikinan sendiri adalah kasus terburuk**: semua
pemakainya menghasilkan nilai yang sama persis, karena dihitung oleh kode yang
sama. Selain berisiko di-ban sebagai klien non-official, ia juga membuat
sidik jari seragam. Ini salah satu alasan K7 di `AGENTS.md`.

---

## Sidik jari perilaku browser

Yang tidak kalah penting, dan kurang dibahas:

| Tanda | Kenapa mencurigakan |
|---|---|
| Kecepatan ketik seragam | Manusia bervariasi antar karakter |
| Klik pada koordinat yang persis sama tiap kali | Manusia tidak presisi begitu |
| Tidak pernah scroll, langsung ke elemen | Manusia membaca dulu |
| Fokus tab tidak pernah berpindah | Manusia terdistraksi |
| Sesi selalu durasi sama | Manusia berhenti di titik acak |

**Catatan jujur:** AgentDrop **tidak** memalsukan ini secara aktif. Yang
dilakukan adalah tidak memperburuknya — `browser-operation` mewajibkan
snapshot dan verifikasi per langkah, yang secara alami memperlambat dan
membuat urutan kurang seragam daripada "klik lima tombol lalu screenshot".

Kalau suatu saat butuh lebih jauh, itu keputusan operator, bukan keputusan
agent.

---

## Sidik jari jaringan

| Tanda | Status |
|---|---|
| IP datacenter untuk DePIN | **Didiskualifikasi.** MaxMind/IP2Location menolkan; butuh residensial |
| Banyak wallet satu IP | Terdeteksi sebagai klaster |
| IP berganti tiap sesi | Lebih buruk daripada IP tetap |

**Batas keras:** agent tidak bisa menyediakan IP residensial. Kalau sebuah
proyek mensyaratkannya (Grass dan sejenisnya), itu **butuh manusia**, dan
VPS tidak akan berhasil berapa lama pun dijalankan.

---

## Yang harus dilakukan agent

1. **Jangan seragam.** Kalau menjalankan cron, variasikan. Jadwal yang persis
   adalah sinyal paling murah untuk dideteksi.
2. **Jangan batch.** Satu aksi, verifikasi, lalu aksi berikutnya. Lebih lambat
   dan lebih aman.
3. **Jangan pakai satu klien wallet untuk banyak wallet.** Lihat di atas.
4. **Jangan optimalkan gas sendiri.** Biarkan klien wallet yang memutuskan —
   itu justru yang membuat sidik jarinya manusiawi.
5. **Laporkan kalau sebuah proyek memeriksa hal yang tidak bisa dipenuhi.**
   Misalnya IP residensial atau KYC. Itu bukan kegagalan agent.

---

## Batas etis dan praktis

Berkas ini menjelaskan **cara deteksi bekerja** supaya agent tidak gagal karena
ketidaktahuan. Ia **bukan** panduan untuk menyamar sebagai banyak manusia.

Yang AgentDrop lakukan: memakai wallet resmi, tidak menyeragamkan pola, dan
menyerahkan KYC serta identitas ke manusia. Yang tidak dilakukan: memalsukan
identitas, membuat klaster wallet untuk mengelabui penyaringan, atau
mengakali pemeriksaan residensial.

Selain karena itu melanggar aturan sebagian besar proyek, secara praktis juga
tidak bertahan: penyaringan semakin berbasis reputasi on-chain dan KYC, yang
tidak bisa dipalsukan dari sisi browser.
