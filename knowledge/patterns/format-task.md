# Format task — kenali sebelum mengerjakan

**Kenapa ini penting:** setiap proyek memakai format berbeda, dan format
menentukan worker mana yang mengerjakan, bukti apa yang dibutuhkan, dan di
mana titik henti manusianya. Menebak format berarti mengerjakan setengah task
lalu buntu di tempat yang tidak terduga.

Baca ini di langkah klasifikasi, sebelum membuka browser.

---

## 1. Campaign harian (daily check-in)

**Tanda:** kata "Daily", "Check-in", "Daily Mission", counter yang reset tiap
24 jam, streak.

| | |
|---|---|
| Worker | `pekerja-harian` + cron |
| Bukti | status di dashboard, kadang tx hash |
| Risiko | klaim dua kali → akun ditandai bot |
| Titik henti | login ulang, CAPTCHA |

**Yang membuat ini berbahaya:** berjalan tanpa operator yang menonton. Aturan
`pekerja-harian` lebih ketat karena itu — kalau ada yang berubah dari kemarin,
berhenti dan lapor, jangan menebak.

## 2. Quest platform (Galxe, QuestN, Layer3, Zealy)

**Tanda:** daftar quest bernomor, tiap quest punya poin, tombol "Claim" per
quest.

| | |
|---|---|
| Worker | `pekerja-quest` (+ `pekerja-x` untuk task sosial di dalamnya) |
| Bukti | tx hash, URL post, screenshot |
| Risiko | dependensi antar quest; verifikasi manual yang butuh berhari-hari |
| Titik henti | approve wallet, KYC |

**Jebakan paling umum:** mengerjakan quest urut dari atas tanpa membaca
seluruhnya. Quest sering punya dependensi — "Follow X" sebelum "Submit tweet
link", "Bridge dulu" sebelum "Verify balance".

**Catatan 2026:** platform pihak ketiga mulai ditinggalkan; proyek membangun
quest in-house supaya datanya bisa dipakai ulang. Jadi jangan berasumsi UI
Galxe berlaku di tempat lain.

## 3. Task sosial (X / Discord)

**Tanda:** follow, post dengan tagar, reply, join server, ambil role.

| | |
|---|---|
| Worker | `pekerja-x`, `pekerja-discord` |
| Bukti | URL post, daftar role |
| Risiko | akun di-ban karena melanggar aturan server / rate limit |
| Titik henti | akun terkunci, verifikasi email/telepon |

**Bedakan dua metode verifikasi SEBELUM bertindak** (lihat
`skills/x-engager/SKILL.md`): platform membaca timeline lewat API, atau
membaca satu URL post spesifik. Salah pilih = quest gagal meski postnya benar.

## 4. On-chain / interaksi protokol

**Tanda:** swap, bridge, deposit, provide liquidity, hold N hari.

| | |
|---|---|
| Worker | `pekerja-quest` (eksekusi) + `pekerja-pantau` (verifikasi) |
| Bukti | tx hash di explorer |
| Risiko | **dana nyata**, approve yang tidak bisa diurungkan |
| Titik henti | **setiap approve dan setiap signature** — approval wallet oleh manusia lewat noVNC |

**Aturan keras:** agent tidak menandatangani apa pun. Wallet resmi dipegang
manusia; popup konfirmasi disetujui manusia lewat noVNC.

## 5. DePIN / uptime

**Tanda:** "keep running", "uptime", epoch, node, bandwidth sharing.

| | |
|---|---|
| Worker | `pekerja-pantau` (memantau), bukan eksekusi |
| Bukti | dashboard uptime, log |
| Risiko | IP datacenter didiskualifikasi |

**Fakta penting:** Grass dan sejenisnya memeriksa IP lewat MaxMind/IP2Location.
**IP datacenter dinolkan.** VPS biasa tidak memenuhi syarat — ini butuh koneksi
residensial, yang tidak bisa diselesaikan oleh agent.

## 6. KYC / identitas

**Tanda:** "verify identity", selfie, dokumen, Gitcoin Passport, Trusta, Nomis.

| | |
|---|---|
| Worker | **tidak ada** — selalu manusia |
| Tindakan | laporkan apa yang dibutuhkan, lalu berhenti |

Agent tidak pernah mengerjakan KYC. Tidak ada pengecualian.

## 7. Tidak dikenal

**Kalau tidak cocok dengan satu pun di atas:** itu bukan alasan untuk mencoba.
Laporkan formatnya apa adanya, sebut bahwa ini di luar pola yang dikenal, dan
minta operator memutuskan. Lalu — kalau sudah dikerjakan manusia — **tulis
polanya ke berkas ini** supaya run berikutnya mengenalinya.

---

## Cara menambah pola baru

Kalau menemukan format yang belum ada di daftar ini:

1. Selesaikan dulu (atau serahkan ke manusia).
2. Tambahkan bagian baru dengan tabel yang sama: tanda, worker, bukti, risiko,
   titik henti.
3. Tulis **gejalanya**, bukan nama proyeknya — pola harus berlaku lintas proyek.
4. Cantumkan tanggal dan dari mana polanya diamati.
