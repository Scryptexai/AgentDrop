---
name: pantau
description: "Pintasan Telegram: delegasikan tugas ke pekerja-pantau (laporan portofolio dan deteksi anomali). Ketik /pantau <tugas>."
version: 1.0.0
author: AgentDrop
license: MIT
platforms: [linux, macos]
metadata:
  hermes:
    tags: [telegram, delegasi, pintasan]
    related_skills: [panggil-pekerja]
---

# /pantau — delegasikan ke `pekerja-pantau`

Pintasan untuk **laporan portofolio dan deteksi anomali**.

Teks setelah perintah adalah tugasnya. Delegasikan ke `pekerja-pantau` lewat
`delegate_task`, tunggu hasilnya, verifikasi, lalu laporkan ringkas.

Ikuti seluruh protokol di skill `panggil-pekerja` — peta nama, cara
memverifikasi hasil pekerja, dan batasnya. Skill ini hanya pintasan namanya;
aturannya ada di sana, dan sengaja tidak diduplikasi supaya keduanya tidak
bisa berbeda.

Kalau tugasnya kosong, tanya operator apa yang harus dikerjakan. Jangan menebak.
