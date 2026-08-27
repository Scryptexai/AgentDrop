---
name: browser-burn-in
description: "Uji stabilitas browser dengan SATU agent dan SATU alur sebelum agent workspace dinyalakan. Enam uji nyata berurutan dengan kriteria lolos yang bisa diverifikasi."
version: 1.0.0
author: AgentDrop
license: MIT
platforms: [linux, macos]
metadata:
  hermes:
    tags: [browser, testing, burn-in, validation, cdp, stability]
    related_skills: [quest-executor, daily-executor]
---

# Browser Burn-In

Enam uji nyata, berurutan, **satu agent, satu alur, tanpa delegasi**. Tujuannya
membuktikan browser stabil **sebelum** orchestrator dan worker workspace
dinyalakan. Menyalakan workspace di atas browser yang tidak stabil hanya
menghasilkan kegagalan yang sulit dilacak.

## Cara agent melihat halaman (penting — baca dulu)

**Sebelum menjalankan enam uji, baca `knowledge/patterns/sidik-jari.md`.**
Isinya tanda tangan otomatisasi yang dideteksi proyek — dan burn-in adalah
tempat yang tepat untuk memastikan lingkungan tidak memproduksinya.


**Jangan pernah memakai CSS selector, XPath, atau `querySelector`.** Itu mengunci
agent ke struktur DOM yang berubah setiap kali situs di-deploy.

Yang dipakai di sini, semuanya tool native Hermes:

| Langkah | Tool | Yang dikembalikan |
|---|---|---|
| Lihat halaman | `browser_snapshot` | **accessibility tree** + `refs` (mis. `@e5`) |
| Klik | `browser_click(ref="@e5")` | hasil klik |
| Ketik | `browser_type` | hasil ketik |
| Kalau AX tree tidak cukup | `browser_vision` | analisis screenshot |
| Kalau masih buntu | berhenti, serahkan ke manusia lewat noVNC | `computer_use` tidak diaktifkan di AgentDrop |

`browser_snapshot` di Hermes didefinisikan sebagai *"a text-based snapshot of
the current page's accessibility tree"*. Elemen dikenali dari **peran dan
namanya** (button "Submit"), bukan dari class CSS. UI berubah → snapshot ulang →
pilih ref baru. **Tidak ada yang terkunci.**

Urutan eskalasi kalau sebuah tombol tidak ketemu:

```
browser_snapshot (AX tree + refs)
   ↓ tidak ketemu / overlay / canvas
browser_scroll (direction="down") → snapshot ulang
   ↓ masih tidak ketemu
browser_vision (screenshot + penalaran visual)
   ↓ masih buntu
BERHENTI, laporkan, minta manusia via noVNC
```

`computer_use` (Set-of-Mark) adalah toolset terpisah dan **tidak diaktifkan**
untuk profil mana pun di AgentDrop. Jangan memanggilnya.

## Enam uji

Jalankan berurutan. **Jangan lanjut ke uji berikutnya kalau yang sekarang
gagal** — catat, lalu berhenti.

### Uji 1 — Navigasi & snapshot
- `browser_navigate("https://example.com")`
- `browser_snapshot`
- **Cocokkan URL + judul** di snapshot dengan yang diharapkan
- **Lolos kalau:** snapshot berisi heading "Example Domain" dan URL cocok
- **Yang diuji:** konektivitas CDP, sesi tab, AX tree berfungsi

### Uji 2 — Elemen dinamis & ref
- `browser_navigate` ke situs dengan UI dinamis (mis. dashboard airdrop yang sedang digarap),
  lalu **cocokkan URL + judul** sebelum lanjut
- `browser_snapshot`, temukan satu elemen interaktif, klik lewat `ref`
- Snapshot ulang
- **Lolos kalau:** klik berhasil DAN snapshot kedua menunjukkan perubahan state
- **Yang diuji:** ref valid, klik benar-benar terjadi, bukan cuma "tidak error"

### Uji 3 — Form & input
- Isi sebuah form (register/login), **jangan submit** kalau itu membuat akun nyata
- **Lolos kalau:** nilai yang diketik terbaca kembali di snapshot
- **Yang diuji:** `browser_type` berfungsi, tidak ada autofill yang mengganggu

### Uji 4 — Sesi bertahan (persistence)
- Login manual sekali via noVNC (`agentdrop browser`, lalu buka http://localhost:6080/vnc.html)
- Tutup sesi agent, buka lagi
- **Lolos kalau:** masih login tanpa perlu login ulang
- **Yang diuji:** login benar-benar bertahan di profil Chrome
  (`~/.agentdrop/chrome-profile`).
  **Ini uji paling penting** — kalau ini gagal, seluruh farming tidak berguna

### Uji 5 — Connect wallet
- `browser_navigate` ke halaman proyek, **cocokkan URL/judul**, lalu klik "Connect Wallet"
- **Lolos kalau:** agent sampai ke titik di mana wallet diminta, dan
  **melaporkan dengan tepat** apa yang dibutuhkan (popup extension? pilihan
  chain?) tanpa menebak
- **Yang diuji:** kemampuan agent mengenali batas kemampuannya sendiri.
  **Catatan jujur:** popup wallet extension TIDAK bisa dikendalikan lewat DOM.
  Lihat `docs/research.md` bagian wallet. Uji ini lolos kalau agent
  **berhenti di tempat yang benar**, bukan kalau ia berhasil sign.

### Uji 6 — Alur sosial nyata
- Buat satu post di X, lalu balas sebuah post dengan menyertakan link
- **Lolos kalau:** post terbit (terbaca di profil), dan reply terlihat di thread
- **Yang diuji:** alur multi-langkah, sesi OAuth bertahan, verifikasi hasil

## Format laporan

```
BURN-IN REPORT — <timestamp>
Browser: Chrome <versi>  |  Profil: <profil yang dipakai, default worker-daily>

Uji 1  Navigasi & snapshot      LOLOS/GAGAL   <bukti>
Uji 2  Elemen dinamis & ref     LOLOS/GAGAL   <bukti>
Uji 3  Form & input             LOLOS/GAGAL   <bukti>
Uji 4  Sesi bertahan            LOLOS/GAGAL   <bukti>
Uji 5  Connect wallet           LOLOS/GAGAL   <bukti>
Uji 6  Alur sosial              LOLOS/GAGAL   <bukti>

Hasil: <N>/6 lolos
Keputusan: SIAP / BELUM SIAP untuk agent workspace

Catatan kegagalan:
  - <apa yang gagal, gejala persisnya, dugaan penyebab>
```

## Aturan

1. **Satu agent, satu alur, tanpa delegasi.** Ini uji browser, bukan uji orkestrasi.
2. **Jangan lanjut setelah gagal.** Catat dan berhenti.
3. **Setiap uji butuh bukti** — screenshot atau perubahan state yang dibaca ulang.
4. **Verifikasi alamat sebelum bertindak:** navigasi eksplisit → snapshot →
   cocokkan URL/judul. Agent dan operator berbagi SATU browser lewat noVNC,
   jadi tab aktif bisa saja tab yang dibuka operator, bukan tab Anda.
5. **Jangan membuat akun nyata atau transaksi nyata** selama burn-in kecuali
   operator memintanya eksplisit.
6. **Uji 5 lolos karena agent berhenti di tempat yang benar**, bukan karena
   berhasil sign. Ini bukan kegagalan agent — itu batas yang memang ada.
7. **Confidence < 0.7 → laporkan, jangan tebak.**
