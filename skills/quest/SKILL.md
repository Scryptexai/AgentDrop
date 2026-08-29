---
name: quest
description: "Pintasan Telegram: delegasikan tugas ke pekerja-quest (campaign multi-langkah di platform quest). Ketik /quest <tugas>."
version: 1.0.0
author: AgentDrop
license: MIT
platforms: [linux, macos]
metadata:
  hermes:
    tags: [telegram, delegasi, pintasan]
    related_skills: [panggil-pekerja]
---

# /quest — delegasikan ke `pekerja-quest`

Pintasan untuk **campaign multi-langkah di platform quest**.

Teks setelah perintah adalah tugasnya. Delegasikan ke `pekerja-quest` lewat
`delegate_task`, tunggu hasilnya, verifikasi, lalu laporkan ringkas.

Ikuti seluruh protokol di skill `panggil-pekerja` — peta nama, cara
memverifikasi hasil pekerja, dan batasnya. Skill ini hanya pintasan namanya;
aturannya ada di sana, dan sengaja tidak diduplikasi supaya keduanya tidak
bisa berbeda.

Kalau tugasnya kosong, tanya operator apa yang harus dikerjakan. Jangan menebak.
