---
name: panggil-pekerja
description: "Pintasan Telegram untuk memanggil satu pekerja tertentu: /riset, /harian, /quest, /daftar, /x, /discord, /pantau. Mendelegasikan tugas ke pekerja itu lalu melaporkan hasilnya."
version: 1.0.0
author: AgentDrop
license: MIT
platforms: [linux, macos]
metadata:
  hermes:
    tags: [telegram, delegasi, pintasan]
    related_skills: [airdrop-intake]
---

# Panggil Pekerja — pintasan dari Telegram

Skill ini ada karena **Hermes tidak punya perintah Telegram untuk berpindah
profil**, dan membangunnya sendiri bukan pilihan yang jujur:

- `gateway/profile_routing.py` merutekan chat → profil lewat
  `gateway.profile_routes`, tapi dibaca **saat gateway start** — menggantinya
  butuh restart.
- `/profile` bawaan Hermes hanya **melihat** profil mana yang melayani chat ini,
  tidak menggantinya.
- `/p/<profile>/` hanya berlaku untuk HTTP API
  (`gateway/platforms/api_server.py:35-36`), bukan Telegram.
- Perintah `/` yang tidak dikenal **tidak** diteruskan ke model — gateway
  membalas "Unknown command" (`gateway/run.py:18847`).

Yang dipakai di sini adalah mekanisme yang memang disediakan Hermes: **skill
terdaftar sebagai perintah `/nama-skill`** (`agent/skill_commands.py`,
dipanggil dari `gateway/run.py:18749`). Jadi pintasan ini berjalan lewat jalur
resmi, bukan mengakali gateway.

## Cara kerja

Operator mengirim `/panggil-pekerja <nama> <tugas>`, atau langsung menyebut nama
pekerja di awal pesan. Saya lalu **mendelegasikan** tugas itu ke pekerja yang
dimaksud lewat `delegate_task`, menunggu hasilnya, dan melaporkannya apa adanya.

Ini **debug dan kendali manual**, bukan alur utama. Tanpa pintasan, pesan masuk
ke `pekerja-koordinator` yang mengklasifikasi dan memutuskan sendiri — itu alur
normalnya. Pintasan ini untuk saat operator sudah tahu persis pekerja mana yang
diinginkan dan tidak mau menunggu klasifikasi.

## Peta nama

| Yang ditulis operator | Pekerja | Untuk apa |
| --- | --- | --- |
| `riset` / `analisis` | `pekerja-riset` | nilai kelayakan proyek |
| `harian` / `daily` | `pekerja-harian` | check-in campaign aktif |
| `quest` | `pekerja-quest` | campaign di platform quest |
| `daftar` / `register` | `pekerja-daftar` | akun baru + wallet di situs proyek |
| `x` / `twitter` | `pekerja-x` | post/reply di X |
| `discord` | `pekerja-discord` | server Discord proyek |
| `pantau` / `monitor` | `pekerja-pantau` | laporan portofolio & anomali |
| `koordinator` | `pekerja-koordinator` | pecah tugas besar jadi subtask |

## Protokol

1. **Kenali pekerja dan tugasnya.** Kalau nama pekerja tidak ada di peta, atau
   tugasnya kosong, tanya — jangan menebak. Salah pekerja berarti task
   dikerjakan dengan aturan yang salah.
2. **Delegasikan lewat `delegate_task`** dengan `goal` yang memuat tugas
   operator apa adanya, dan `context` yang menyebut ini panggilan manual.
3. **Tunggu hasilnya, lalu verifikasi.** Hasil dari pekerja **bukan** bukti
   otomatis. Periksa: apakah statusnya eksplisit, apakah ada bukti yang bisa
   dibaca ulang.
4. **Laporkan ringkas** ke Telegram: pekerja mana, status, bukti, dan apa yang
   masih butuh operator (CAPTCHA, 2FA, OTP, KYC tetap `human`).
5. **Jangan mengerjakan sendiri.** Kalau saya ikut mengeksekusi, tidak ada yang
   memeriksa hasil pekerja — dan itu justru alasan arsitektur ini dipisah.

## Sesi

Setiap pekerja punya sesi sendiri yang bertahan. Memanggil pekerja yang sama
dua kali **melanjutkan** konteks sebelumnya, bukan memulai dari nol. Kalau
operator ingin mulai bersih, ia mengirim `/new` (bawaan Hermes,
`gateway/slash_commands.py:145` → `reset_session()`).

## Batas

- Pintasan ini **tidak** mengubah profil mana yang melayani chat Telegram.
  Profil default tetap yang memegang token bot; pekerja berjalan sebagai
  subagent lewat delegasi.
- **Tidak ada** `terminal` / `code_execution` di profil mana pun (K4).
- Signing otomatis berlaku (K14), tapi CAPTCHA/2FA/OTP/KYC tetap diserahkan ke
  operator.

## Provider dan model

Pakai **`/model` bawaan Hermes** — jangan menulis `.env` dari chat.

```
/model                          lihat model sekarang
/model Qwen3.8-27B              ganti untuk sesi ini
/model Qwen3.8-27B --global     ganti DAN tulis ke config.yaml
/model --provider custom ...    ganti provider sekaligus
```

Dua hal yang harus dilaporkan ke operator, karena keduanya mudah salah dipahami:

1. **Tanpa `--global`, ganti model hanya berlaku untuk sesi itu** dan disimpan
   di session DB (`gateway/slash_commands.py:2283`). Ia bertahan setelah
   restart gateway, tapi **tidak** menjangkau pekerja lain.
2. **`/model --global` menulis `model.default` langsung ke config.yaml**
   (`gateway/slash_commands.py:2397`) dan **menimpa rujukan
   `${AGENTDROP_MODEL}`** di profil itu. Setelah itu `agentdrop model` di
   terminal tidak lagi menjangkau profil tersebut — nilainya sudah literal.
   Itu bukan bug Hermes; itu memang arti "persist to config". Tapi operator
   perlu tahu bahwa profil itu lepas dari `.env`.

Karena itu: untuk mengganti model **semua** pekerja sekaligus, jalannya tetap
`agentdrop model` di terminal, bukan `/model --global` di chat.

`/model` di gateway sudah sadar profil (`gateway/slash_commands.py:1775-1778`
menyelesaikan `config_path` dalam scope profil yang melayani chat), jadi di
gateway multiplex ia menulis ke profil yang benar — bukan ke profil default.
