---
name: daftar
description: "Pintasan Telegram: delegasikan tugas ke pekerja-daftar (register akun baru + connect wallet di situs proyek). Ketik /daftar <tugas>."
version: 1.0.0
author: AgentDrop
license: MIT
platforms: [linux, macos]
metadata:
  hermes:
    tags: [telegram, delegasi, pintasan]
    related_skills: [panggil-pekerja]
---

# /daftar — delegasikan ke `pekerja-daftar`

Pintasan untuk **register akun baru + connect wallet di situs proyek**.

Teks setelah perintah adalah tugasnya. Delegasikan ke `pekerja-daftar` lewat
`delegate_task`, tunggu hasilnya, verifikasi, lalu laporkan ringkas.

Ikuti seluruh protokol di skill `panggil-pekerja` — peta nama, cara
memverifikasi hasil pekerja, dan batasnya. Skill ini hanya pintasan namanya;
aturannya ada di sana, dan sengaja tidak diduplikasi supaya keduanya tidak
bisa berbeda.

Kalau tugasnya kosong, tanya operator apa yang harus dikerjakan. Jangan menebak.
