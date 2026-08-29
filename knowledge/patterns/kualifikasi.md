# Kualifikasi — apa yang membuat sebuah wallet dihitung

**Yang perlu dipahami agent:** menyelesaikan task dan **dihitung** oleh proyek
adalah dua hal berbeda. Penyaringan berjalan terpisah, dan banyak wallet yang
menyelesaikan semuanya tetap tidak mendapat apa pun.

LayerZero menghapus 803.273 wallet (59%). Linea menyaring ~800 ribu. Jadi
pertanyaan "apakah task-nya selesai?" tidak cukup — pertanyaannya "apakah
wallet ini akan lolos penyaringan?".

---

## Yang dihargai

| Faktor | Kenapa |
|---|---|
| **Umur wallet** | Wallet lama lebih mahal dibuat, jadi lebih mungkin manusia |
| **Aktivitas tersebar waktu** | "Sekali dua kali sebulan selama 8 bulan" > "50 transaksi sehari" |
| **Interaksi beragam** | Hanya satu jenis aksi terlihat mekanis |
| **Ekonomi yang masuk akal** | Rugi gas untuk transaksi tak berarti adalah tanda bot |
| **Reputasi on-chain** | Gitcoin Passport, Trusta, Nomis semakin dipakai sebagai gerbang |
| **KYC** | Di banyak proyek sudah wajib, bukan opsional |

## Yang memicu penyaringan

Yang disebut eksplisit dalam riset 2026 sebagai tanda otomatis:

- **transaksi batch** — banyak aksi dalam satu tx, atau banyak tx beruntun
- **gas yang terlalu optimal** — semua tx memakai priority fee identik
- **urutan interaksi yang kaku** — selalu sama, selalu lengkap
- **pola waktu mekanis** — tepat setiap 24 jam, pada jam yang sama

Ditambah yang lebih tua tapi tetap berlaku:

- funding dari satu sumber yang sama (klaster)
- banyak wallet memakai IP yang sama
- wallet baru yang langsung aktif intensif lalu mati

---

## Konsekuensi untuk cara agent bekerja

### Jangan seragam — dan ini bukan hiasan

Jadwal cron yang persis 24 jam pada jam yang sama **adalah sinyal**. Kalau
`pekerja-harian` dijalankan cron, variasinya harus nyata, bukan acak kosmetik.

### Sidik jari gas: alasan multi-wallet

Klaster wallet yang semuanya memakai priority fee 25 gwei **sudah ditandai**.
Setiap klien wallet menghitung gas berbeda secara default:

> "use different wallet clients — MetaMask, Rabby, Frame, Keplr, Phantom each
> compute gas differently by default"

**Ini alasan AgentDrop memasang MetaMask + OKX + Phantom.** Bukan redundansi —
tiap klien menghasilkan sidik jari yang berbeda secara alami. Memakai satu
klien untuk sepuluh wallet justru membuat semuanya identik.

### Wallet resmi, bukan bikinan

Ekstensi non-official selain berisiko di-ban, juga menghasilkan sidik jari yang
**seragam untuk semua pemakainya** — persis kebalikan dari yang dibutuhkan.

### Satu proyek, sedikit wallet, lama

Wallet yang dirotasi kalah dari wallet yang dipelihara. Kalau sebuah proyek
berjalan delapan bulan, lebih baik satu wallet yang aktif delapan bulan
daripada tiga wallet yang bergantian.

---

## Batas yang tidak bisa dilewati agent

- **KYC / identitas** — selalu manusia, tanpa pengecualian
- **IP residensial untuk DePIN** — MaxMind/IP2Location menolkan IP datacenter.
  VPS tidak memenuhi syarat dan agent tidak bisa mengubahnya
- **Umur wallet** — tidak bisa dipercepat. Wallet baru tetap wallet baru

Kalau sebuah proyek mensyaratkan salah satu dari ini, laporkan sebagai
**butuh manusia**, bukan sebagai task yang gagal.
