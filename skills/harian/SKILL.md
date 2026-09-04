---
name: harian
description: "Pintasan Telegram: delegasikan tugas ke pekerja-harian (check-in dan aksi harian campaign aktif). Ketik /harian <tugas>."
version: 1.0.0
author: AgentDrop
license: MIT
platforms: [linux, macos]
metadata:
  hermes:
    tags: [telegram, delegasi, pintasan]
    related_skills: [panggil-pekerja]
---

# /harian — delegasikan ke `pekerja-harian`

Pintasan untuk **check-in dan aksi harian campaign aktif**.

Teks setelah perintah adalah tugasnya. Delegasikan ke `pekerja-harian` lewat
`delegate_task`, tunggu hasilnya, verifikasi, lalu laporkan ringkas.

Ikuti seluruh protokol di skill `panggil-pekerja` — peta nama, cara
memverifikasi hasil pekerja, dan batasnya. Skill ini hanya pintasan namanya;
aturannya ada di sana, dan sengaja tidak diduplikasi supaya keduanya tidak
bisa berbeda.

Kalau tugasnya kosong, tanya operator apa yang harus dikerjakan. Jangan menebak.
