# Prosedur uji di mesin Anda

Dokumen ini ada karena satu alasan: supaya hasil uji bisa **dianalisis**.
Log audit tersimpan di `~/.agentdrop/logs/` — **di luar repo** — jadi `git push`
biasa tidak akan menyertakannya. Langkah 5 menutup itu.

---

## 0. Pasang

```bash
git clone https://github.com/Scryptexai/AgentDrop.git
cd AgentDrop
git checkout arena/01a037ea-agentdrop
cp .env.example .env      # lalu isi
./install.sh
```

## 1. Preflight — lakukan ini dulu

```bash
agentdrop status
```

`agentdrop status` memeriksa lima hal: biner, kredensial, profil + hook audit,
browser + ekstensi, dan keadaan repo. Selesai dalam beberapa detik.
**Kalau ada yang ✗, jangan mulai uji** — Anda akan menghabis waktu dan lognya
tidak berarti.

Yang paling sering menggagalkan:

| Gejala | Sebab | Perbaikan |
|---|---|---|
| `hooks_auto_accept bukan true` | hook diabaikan diam-diam pada cron/gateway | jalankan ulang `./install.sh` |
| `Google Chrome BRANDED` | Chrome 137+ mengabaikan `--load-extension` | pakai Chrome for Testing |
| `tidak ada ekstensi` | wallet belum dipasang | `agentdrop extensions` |
| `disabled_toolsets hilang` | agent bisa membuka browser sendiri lewat shell | jalankan ulang `./install.sh` |

## 2. Nyalakan browser

```bash
agentdrop extensions        # sekali saja
agentdrop browser
```

**Verifikasi wajib sebelum lanjut** — jangan lewati ini:

1. Buka jendelanya (di desktop: jendela Chrome for Testing; di VPS: noVNC
   `http://localhost:6080/vnc.html`), lalu buka `https://example.com`
2. Buka console, ketik:
   ```js
   window.ethereum     // harus ada
   window.solana       // harus ada kalau Phantom terpasang
   ```
3. Kalau keduanya `undefined`, **ekstensi tidak termuat**. Berhenti di sini dan
   perbaiki dulu — semua task airdrop akan gagal dengan cara yang membingungkan.

Lalu **login manual sekali per platform** lewat jendela itu: Google, Discord, X.
Agent tidak bisa dan tidak boleh melakukan itu sendiri.

## 3. Siapkan wallet

Tidak ada daemon signing yang perlu dinyalakan. Wallet yang dipakai adalah
**MetaMask / OKX / Phantom yang dipasang di browser**, dan kuncinya dipegang
manusia di dalam wallet itu.

Yang perlu dipastikan sebelum lanjut:

1. Tiap ekstensi wallet sudah dibuat atau diimpor **sekali** di jendela browser
2. Wallet punya gas yang cukup di chain yang akan dipakai — BNB Smart Chain
   butuh BNB, bukan ETH (lihat `knowledge/chains/`)
3. Chain yang benar sudah terpilih di dalam wallet

Approval dan signature ditandatangani **manusia** di jendela browser. Agent menyiapkan
transaksi sampai popup muncul, lalu berhenti dan menyerahkan.

## 4. Jalankan uji

Kirim satu task lewat Telegram ke bot. **Mulai dari yang kecil** — satu proyek,
satu task — supaya kalau gagal, runtutannya pendek dan mudah dibaca.

```bash
# pantau selama berjalan, di terminal lain
agentdrop audit tail -n 20
```

## 5. Kumpulkan dan push — INI LANGKAH YANG MEMBUAT HASILNYA BISA DIANALISIS

```bash
agentdrop logs --label uji-1
git add data/audit/
git commit -m "audit: hasil uji 1"
git push origin arena/01a037ea-agentdrop
```

Skrip itu menyalin log + konteks ke `data/audit/<stempel>/`:

| Berkas | Isi |
|---|---|
| `01-health.txt` | ringkasan per komponen |
| `02-doctor.txt` | **diagnosis + berkas yang harus dibuka** |
| `03-errors.txt` | error terperinci |
| `04-stuck.txt` | tool yang menggantung |
| `05-lingkungan.txt` | OS, versi binari, status browser |
| `06-hook.txt` | apakah hook benar-benar terpasang |
| `07-validator.txt` | keadaan repo saat uji |
| `logs/` | JSONL mentah (sudah diredaksi) |

**Gerbang keamanan:** skrip ini memindai hasilnya untuk pola secret (private
key, seed phrase, bot token, api key) dan **menolak menulis apa pun** kalau
menemukan satu. Sudah diuji: log yang sengaja berisi private key membuat skrip
berhenti dengan exit 1 dan tidak menulis ke repo.

## 6. Kalau ada yang salah sebelum push

```bash
agentdrop audit doctor              # gejala -> komponen -> berkas
agentdrop audit trace <session_id>  # runtutan satu task
agentdrop audit stuck               # tool menggantung = browser mati
```

`session_id` bisa diambil dari `01-health.txt` atau dari `tail`.

---

## Yang belum pernah diuji oleh pembuat repo

Semua ini dibangun di lingkungan tanpa Hermes terpasang dan tanpa Chrome, jadi
ada batas nyata pada apa yang sudah terbukti.

**Sudah diuji nyata:**

- penulis log audit: redaksi dua lapis (diuji per pola, dengan memutus satu pola
  pada satu waktu), rotasi, dan `flock` konkuren
- shell hook dengan bentuk payload persis dari dokumen Hermes, termasuk stdin
  rusak dan kosong
- ekstraksi CRX3 dengan CRX sintetis
- validator: **179 pemeriksaan**, exit 0
- tiap guard baru diuji **mutasi** — kondisinya benar-benak dirusak, lalu
  dipastikan validator menolaknya

**Belum pernah terbukti di lingkungan mana pun:**

- hook yang benar-benar menyala di dalam run Hermes yang hidup
- Chrome for Testing yang benar-benar memuat ekstensi wallet
- alur lengkap Telegram → orchestrator → worker → wallet

Ketiganya hanya bisa diuji di mesin Anda — dan itulah gunanya langkah 5.

**Catatan jujur soal cakupan uji.** Dulu ada tiga suite test (47 policy,
25 daemon, 9 plugin). Ketiganya **dihapus bersama subsistemnya** saat ekstensi
bikinan sendiri dan signing daemon dibuang. Yang tersisa sebagai pengaman
adalah validator 179 pemeriksaan plus uji mutasi per guard — bukan pengganti
suite test, dan tidak dimaksudkan sebagai itu. Kalau nanti ada logika Python
baru yang punya cabang keputusan, ia perlu suite test sendiri.
