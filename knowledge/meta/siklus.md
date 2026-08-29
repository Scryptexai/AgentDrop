# Siklus — kenapa strategi harus dibaca ulang tiap musim

**Poin utamanya:** meta airdrop berubah setiap siklus. Format, cara
kualifikasi, dan yang dihargai semuanya bergeser. Strategi yang berhasil musim
lalu bisa jadi justru menjadi tanda bot musim ini.

Jadi: **jangan mengandalkan ingatan tentang "cara kerja airdrop".** Baca
berkas ini, lalu periksa apakah proyek yang sedang dikerjakan masih mengikuti
pola yang sama.

---

## Yang berubah dari siklus ke siklus

| Dimensi | Dulu | Sekarang |
|---|---|---|
| Yang dihargai | **Volume** — sebanyak mungkin transaksi | **Bobot waktu** — aktivitas tersebar berbulan-bulan |
| Hukuman sybil | Pemotongan biner (lolos / tidak) | **Bertingkat** — sebagian alokasi dipotong |
| Bukti manusia | Tidak diperiksa | KYC + reputasi on-chain |
| Platform quest | Galxe, QuestN, Layer3 | Proyek membangun **quest in-house** |
| Snapshot | Satu kali, diam-diam | **Points system** yang berjalan terus |
| Kategori dominan | Bridge, L2 | DEX, perps, wallet, AI-native, DePIN |

**Angka konkret yang sudah terjadi:** LayerZero menghapus **803.273 wallet
(59%)**. Linea menyaring sekitar **800 ribu**. Ini bukan risiko teoretis.

---

## Yang TIDAK berubah

- Wallet yang **berumur panjang** mengalahkan wallet yang dirotasi.
- Aktivitas yang **tersebar waktu** mengalahkan aktivitas yang menumpuk.
- Interaksi yang **masuk akal secara ekonomi** mengalahkan yang mekanis.
- KYC dan identitas asli semakin menjadi gerbang, bukan opsional.

---

## Konsekuensi langsung untuk cara AgentDrop bekerja

### 1. Frekuensi, bukan jumlah

Riset 2026 merumuskannya begini: aktivitas **sekali atau dua kali sebulan
selama delapan bulan** peringkatnya lebih tinggi daripada **lima puluh
transaksi dalam satu hari**.

Jadi cron harian yang mengerjakan semuanya sekaligus adalah **pola yang salah**.
Yang benar: sedikit, tersebar, tidak seragam. Ini alasan `pekerja-harian` ada
sebagai worker terpisah dengan state sendiri, bukan sekadar loop.

### 2. Jangan seragam

Yang secara eksplisit disebut sebagai tanda otomatis:

- transaksi batch
- pemakaian gas yang "terlalu optimal"
- urutan interaksi yang kaku
- pola waktu yang mekanis

**Artinya:** jadwal yang persis setiap 24 jam pada jam yang sama adalah sinyal.
Variasi bukan hiasan — itu bagian dari strateginya.

### 3. Sidik jari gas

Klaster wallet yang semuanya memakai priority fee 25 gwei **sudah ditandai**.
Setiap klien wallet menghitung gas dengan cara berbeda secara default —
MetaMask, Rabby, Frame, Keplr, Phantom masing-masing lain.

**Ini alasan multi-wallet itu pertahanan, bukan redundansi.** Memakai beberapa
klien wallet resmi menghasilkan sidik jari gas yang berbeda secara alami.
Ini juga alasan AgentDrop memasang MetaMask + OKX + Phantom, bukan satu saja.

### 4. Wallet resmi, bukan bikinan

Ekstensi non-official terdeteksi sebagai klien asing. Selain risiko di-ban,
ia juga menghasilkan sidik jari yang seragam untuk semua pemakainya — persis
kebalikan dari poin 3.

### 5. IP matters untuk DePIN

Grass dan sejenisnya memeriksa IP lewat MaxMind/IP2Location dan membutuhkan
**100+ jam uptime per epoch**. **IP datacenter dinolkan.** VPS tidak memenuhi
syarat — ini batas yang tidak bisa dilewati agent.

---

## Cara memperbarui berkas ini

Setiap siklus, atau setiap kali menemukan bukti baru:

1. Tambahkan baris di tabel "Yang berubah" dengan **tanggal** dan sumbernya.
2. Jangan menghapus baris lama — tandai usang. Jejak perubahan itu sendiri
   informasi: ia menunjukkan seberapa cepat meta bergeser.
3. Kalau sebuah perubahan menuntut perubahan cara agent bekerja, **ubah juga
   SOUL.md atau SKILL.md yang bersangkutan** dan catat di sini bahwa itu
   sudah dilakukan. Pengetahuan yang tidak mengubah perilaku bukan pengetahuan.
