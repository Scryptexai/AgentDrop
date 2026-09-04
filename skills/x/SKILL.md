---
name: x
description: "Pintasan Telegram: delegasikan tugas ke pekerja-x (post/reply di X untuk campaign). Ketik /x <tugas>."
version: 1.0.0
author: AgentDrop
license: MIT
platforms: [linux, macos]
metadata:
  hermes:
    tags: [telegram, delegasi, pintasan]
    related_skills: [panggil-pekerja]
---

# /x — delegasikan ke `pekerja-x`

Pintasan untuk **post/reply di X untuk campaign**.

Teks setelah perintah adalah tugasnya. Delegasikan ke `pekerja-x` lewat
`delegate_task`, tunggu hasilnya, verifikasi, lalu laporkan ringkas.

Ikuti seluruh protokol di skill `panggil-pekerja` — peta nama, cara
memverifikasi hasil pekerja, dan batasnya. Skill ini hanya pintasan namanya;
aturannya ada di sana, dan sengaja tidak diduplikasi supaya keduanya tidak
bisa berbeda.

Kalau tugasnya kosong, tanya operator apa yang harus dikerjakan. Jangan menebak.
