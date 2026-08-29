# Alur hidup sebuah airdrop — dari pengumuman sampai token

**Kenapa agent perlu tahu ini:** tanpa peta ini, agent mengerjakan task tanpa
tahu sedang berada di tahap mana. Padahal tahap menentukan apa yang masuk akal
dilakukan, apa yang belum ada gunanya, dan kapan berhenti.

Contoh nyata: mengerjakan "claim" sebelum snapshot terjadi tidak menghasilkan
apa pun selain biaya gas.

---

## Tahap-tahapnya

### 1. Pra-pengumuman (spekulatif)

Proyek hidup, token belum diumumkan. Kualifikasi **tidak diketahui**.

- **Yang masuk akal:** pakai produknya secara wajar, simpan catatan aktivitas
- **Yang tidak ada gunanya:** mengejar "task" yang diklaim orang di Telegram
- **Tanda tahap ini:** tidak ada halaman airdrop resmi, hanya spekulasi
- **Risiko:** tinggi — banyak situs palsu muncul justru di tahap ini

### 2. Program poin / quest dibuka

Mekanisme resmi diumumkan. Ini tahap paling bisa dikerjakan.

- **Yang masuk akal:** kerjakan quest sesuai `format-task.md`, pantau poin
- **Yang perlu dicatat:** apakah points-based atau activity-based, dan apakah
  ada epoch
- **Tanda tahap ini:** dashboard poin, daftar quest, leaderboard
- **Risiko:** sedang — tapi di sinilah prompt injection paling sering muncul

### 3. Snapshot

Proyek mengambil data pada satu titik waktu. **Sering diam-diam.**

- **Yang masuk akal:** pastikan syarat sudah terpenuhi SEBELUMNYA
- **Yang tidak ada gunanya:** aktivitas setelah snapshot
- **Tanda tahap ini:** pengumuman "snapshot taken", atau tidak ada tanda sama
  sekali
- **Catatan:** sejak 2026 banyak proyek memakai points system terus-menerus,
  jadi "snapshot" semakin jarang menjadi satu peristiwa tunggal

### 4. Pengumuman alokasi

Proyek mengumumkan siapa yang dapat dan berapa.

- **Yang masuk akal:** cek apakah wallet masuk daftar; **periksa penyaringan**
- **Yang penting diketahui:** LayerZero menghapus 59% wallet, Linea ~800 ribu.
  Tidak mendapat alokasi meski sudah mengerjakan task adalah **hasil yang
  mungkin**, bukan bukti ada yang rusak
- **Risiko:** situs "cek alokasi" palsu muncul massal di tahap ini

### 5. Klaim

Token bisa diambil.

- **Yang masuk akal:** klaim lewat **domain resmi yang sudah diverifikasi**
- **Titik henti manusia:** signature untuk klaim — approval lewat noVNC
- **Risiko:** **tertinggi.** Domain tiruan, approve berbahaya, "claim fee"
- **Aturan:** kalau ada biaya klaim selain gas, itu penipuan

### 6. Pasca-TGE

Token live dan diperdagangkan.

- **Yang masuk akal:** `pekerja-pantau` memantau saldo dan vesting
- **Catatan:** banyak program punya vesting bertahap, jadi saldo awal bukan
  jumlah akhir

---

## Cara memakai peta ini

Saat menerima task, tentukan lebih dulu **tahap mana** proyeknya:

| Tahap | Worker utama | Yang dilaporkan |
|---|---|---|
| 1 pra-pengumuman | `pekerja-riset` | kelayakan spekulatif, confidence rendah |
| 2 poin/quest | `pekerja-quest`, `pekerja-harian`, `pekerja-x`, `pekerja-discord` | progres per quest |
| 3 snapshot | `pekerja-pantau` | apakah syarat terpenuhi |
| 4 alokasi | `pekerja-pantau` | dapat / tidak dapat, dan kenapa |
| 5 klaim | **manusia**, dengan `pekerja-pantau` memverifikasi | tx hash + saldo masuk |
| 6 pasca-TGE | `pekerja-pantau` | saldo, vesting |

**Kalau tahapnya tidak bisa ditentukan, itu sendiri temuan.** Laporkan bahwa
tahapnya tidak jelas — jangan menebak lalu mengerjakan task yang tidak relevan.

---

## Yang sering salah dipahami

- **"Sudah mengerjakan semua task" tidak menjamin alokasi.** Penyaringan sybil
  berjalan terpisah dari penyelesaian task.
- **"Belum ada pengumuman" bukan berarti tidak ada kualifikasi.** Banyak proyek
  merekam aktivitas jauh sebelum mengumumkannya.
- **Task sosial bukan pengganti aktivitas on-chain.** Beberapa proyek hanya
  menghitung yang on-chain.
- **Lebih banyak wallet bukan otomatis lebih baik.** Kalau semuanya berpola
  sama, justru terdeteksi sebagai klaster. Lihat `sidik-jari.md`.
