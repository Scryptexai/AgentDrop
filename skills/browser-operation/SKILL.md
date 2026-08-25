---
name: browser-operation
description: "Protokol operasi browser: elemen dikenali lewat index/ref bukan selector, state dibaca ulang sebelum tiap aksi, dan setiap aksi diverifikasi sebelum dianggap berhasil."
version: 1.0.0
author: AgentDrop
license: MIT
platforms: [linux, macos]
metadata:
  hermes:
    tags: [browser, protocol, accessibility-tree, verification, anti-fragile]
    related_skills: [browser-burn-in, quest-executor, daily-executor, airdrop-intake]
---

# Browser Operation Protocol

Protokol dasar untuk SEMUA pekerjaan browser. Skill lain (quest-executor,
daily-executor, airdrop-intake, discord-engager) mengacu ke sini.

Diadaptasi dari arsitektur OpenManus (`FoundationAgents/OpenManus`) dan
dipetakan ke tool native Hermes. Lihat `docs/research.md` untuk provenance.

---

## Aturan 1 — Tidak ada selector. Titik.

**Dilarang:** CSS selector, XPath, `querySelector`, `getElementsByClassName`,
`data-testid`, index berbasis posisi DOM.

Alasannya: selector mengunci agent ke **cara halaman dibangun**. Situs
di-deploy ulang, class berganti dari `btn-primary` jadi `btn-action`, dan
selector mati — padahal tombolnya masih tombol "Submit" yang sama.

**Yang dipakai:** elemen dikenali dari **peran dan namanya**, lewat index/ref
yang dihitung ulang setiap kali state dibaca.

| OpenManus | Hermes (yang kita pakai) |
|---|---|
| `[33]<button>Submit Form</button>` | `@e5` dari `browser_snapshot` |
| `click_element(index=33)` | `browser_click(ref="@e5")` |
| tidak ada aksi klik-by-selector | tidak ada parameter selector |

Hermes `browser_snapshot` didefinisikan sebagai *"a text-based snapshot of the
current page's accessibility tree"* dan mengembalikan `refs`. OpenManus bahkan
lebih keras: **tidak ada** aksi yang menerima selector, jadi secara struktural
mustahil mengunci.

**Konsekuensi yang harus diterima:** index/ref **tidak stabil antar snapshot**.
`@e5` sekarang bisa jadi `@e9` setelah halaman berubah. Karena itu ref selalu
diambil dari snapshot **terbaru**, tidak pernah diingat dari langkah sebelumnya.

---

## Aturan 2 — Baca state sebelum bertindak. Setiap kali.

Agent tidak pernah mengandalkan UI yang diingat. Urutannya selalu:

```
browser_navigate(URL)          # eksplisit, bukan tab yang kebetulan terbuka
      ↓
browser_snapshot               # AX tree + refs + URL + judul
      ↓
cocokkan URL & judul           # Hermes bisa meng-adopsi tab yang salah
      ↓
baru putuskan aksi
```

Yang harus diperhatikan dari snapshot:

- **URL dan judul** — apakah ini halaman yang dimaksud?
- **Elemen interaktif** — apa yang benar-benar bisa diklik?
- **Konten di luar viewport** — OpenManus melacak `pixels_above` /
  `pixels_below`. Kalau masih ada konten di bawah, **scroll sebelum menyimpulkan
  sebuah tombol tidak ada.** "Tombolnya tidak ada" sering berarti "belum
  di-scroll".
- **Tab terbuka** — apakah ini tab yang benar?

---

## Aturan 3 — Verifikasi sebelum lanjut (paling penting)

Ini pola OpenManus yang paling berharga. Skema respons mereka mewajibkan field
`evaluation_previous_goal` berisi `"Success|Failed|Unknown"` **sebelum** agent
boleh menentukan langkah berikutnya.

Terapkan sebagai disiplin, sebelum setiap aksi baru:

```
SEBELUM lanjut ke aksi berikutnya, jawab tiga hal:
  1. Aksi sebelumnya berhasil, gagal, atau tidak diketahui?
  2. Apa BUKTINYA? (perubahan state yang dibaca ulang dari snapshot)
  3. Kalau tidak diketahui — apa yang akan membuatnya diketahui?
```

**Bukti yang sah:**
- Teks tombol berubah ("Submit" → "Submitted")
- Counter bertambah
- Muncul elemen baru / elemen lama hilang
- URL berpindah ke tempat yang diharapkan
- Toast/notifikasi yang terbaca di snapshot

**Bukan bukti:**
- "Kliknya tidak error"
- "Sepertinya berhasil"
- Tidak ada pesan error

**Kalau tidak ada bukti → aksi itu GAGAL.** Laporkan gagal. Laporan optimis
yang salah lebih merusak daripada laporan gagal yang jujur, karena operator
kehilangan kesempatan memperbaiki.

---

## Aturan 4 — Hitung kemajuan secara eksplisit

OpenManus mewajibkan di field `memory`:

> "Count here ALWAYS how many times you have done something and how many
> remain. E.g. **0 out of 10** websites analyzed."

Untuk task berulang (daily mission, "kerjakan untuk semua campaign", "klaim 5
reward"), tulis penghitung di setiap laporan langkah:

```
Progres: 3 dari 7 task selesai. Sisa: task 4 (Follow X), task 5 (Quiz), ...
```

Tanpa penghitung eksplisit, agent kehilangan jejak di task panjang dan berhenti
terlalu cepat atau mengulang yang sudah selesai.

---

## Aturan 5 — Tangani kebuntuan dengan mengubah pendekatan

Jangan mengulang aksi yang sama dan mengharapkan hasil berbeda. Tangga yang
harus dinaiki:

```
1. Snapshot ulang           → mungkin state sudah berubah
2. Scroll                   → elemennya mungkin di luar viewport
3. Tutup popup/overlay      → cookie banner, modal, tooltip menutupi
4. Kembali (browser_back)   → lalu coba jalan lain
5. Tab baru                 → jangan rusak tab yang sedang dipakai
6. browser_vision           → AX tree tidak cukup (canvas, overlay, gambar)
7. computer_use mode='som'  → screenshot bernomor, klik by element index
8. BERHENTI                 → laporkan, minta manusia via noVNC
```

Langkah 7 adalah Set-of-Mark: `computer_use(action="capture", mode="som")`
menghasilkan **screenshot dengan overlay elemen bernomor**, lalu
`click(element=N)`. Ini satu-satunya jalan untuk UI yang tidak punya markup
aksesibel — dan untuk jendela yang bukan halaman web biasa.

---

## Aturan 6 — Aksi berurutan boleh, dengan batas

OpenManus mengizinkan beberapa aksi dalam satu urutan untuk efisiensi, dengan
syarat:

> "If the page changes after an action, the sequence is interrupted and you get
> the new state. Only provide the action sequence until an action which changes
> the page state significantly."

Terjemahannya: **batch aksi yang tidak mengubah halaman** (isi 3 field form),
tapi **jangan batch melintasi navigasi**. Setelah halaman berubah, baca ulang
state.

---

## Aturan 7 — Jangan mengarang aksi

Dari prompt OpenManus, dan berlaku lebih keras di sini:

- Jangan mengklik ref yang tidak ada di snapshot terbaru
- Jangan mengarang URL — pakai yang ada di data campaign atau yang operator beri
- Jangan mengarang bahwa sebuah task selesai
- Kalau sebuah elemen tidak ditemukan setelah tangga di Aturan 5, **katakan
  tidak ditemukan**. Jangan menebak elemen lain yang "mirip".

---

## Batas yang tidak bisa dinegosiasikan

Berbeda dari OpenManus — yang prompt-nya menulis *"If captcha pops up, try to
solve it"* — AgentDrop **tidak** mencoba menyelesaikan CAPTCHA.

- **CAPTCHA / 2FA / verifikasi SMS → STOP.** Serahkan ke operator lewat
  `http://localhost:6080/vnc.html`.
- **OAuth (Connect Twitter/Discord) → STOP.** Butuh login akun operator.
- **Signature wallet → lihat `docs/research.md` bagian wallet.** Popup wallet
  extension tidak bisa dikendalikan lewat DOM (Playwright issue #5593 terbuka
  sejak Feb 2021; LavaMoat MetaMask memblokir inspeksi).
- **Tidak ada private key / seed phrase** di prompt, log, atau screenshot.

---

## Ringkasan per langkah

```
1. navigate eksplisit
2. snapshot
3. cocokkan URL/judul
4. pilih elemen by ref dari snapshot TERBARU
5. aksi
6. snapshot ulang
7. evaluasi: berhasil / gagal / tidak diketahui + bukti
8. update penghitung progres
9. lanjut atau berhenti
```

Langkah 6-7 bukan opsional. Di situlah perbedaan antara agent yang bisa
dipercaya dan agent yang melaporkan keberhasilan palsu.
