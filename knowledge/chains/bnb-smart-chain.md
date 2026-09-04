# BNB Smart Chain

## Fakta yang diverifikasi
- `chain_id`    : **56** (`0x38`)
- `native`      : BNB
- `explorer`    : https://bscscan.com
- `testnet`     : BSC Testnet, chain_id **97**
- Diperiksa pada : 2026-08-27 (chainlist / evmchainlist)

## RPC publik
- `https://bsc-dataseed.binance.org`
- `https://bsc-rpc.publicnode.com`

**Belum diverifikasi sesi ini.** Cek `eth_chainId` harus `0x38`.

## Verifikasi RPC

Endpoint di atas **belum diverifikasi** dan tidak bisa diverifikasi dari
lingkungan pembangunan: sandbox-nya punya allowlist egress, jadi setiap RPC
gagal di TLS handshake (`SSL_ERROR_SYSCALL`) meski DNS resolve normal dan
`github.com` menjawab 200. Ini keterbatasan lingkungan, **bukan** bukti bahwa
endpoint-nya buruk.

**Periksa sendiri sebelum dipakai:**

```bash
curl -s <RPC> -H 'content-type: application/json' \
  -d '{"jsonrpc":"2.0","id":1,"method":"eth_chainId","params":[]}'
```

Jawabannya harus cocok dengan `chain_id` di atas. RPC publik sering rate-limit,
kadang mati, dan sesekali mengarah ke chain yang salah — dan RPC yang mengarah
ke chain salah jauh lebih berbahaya daripada RPC yang mati, karena transaksinya
tetap terkirim.

## Yang perlu diketahui agent

**EVM, tapi bukan Ethereum.** Gas dibayar dengan BNB, bukan ETH. Ini sumber
kesalahan paling umum: wallet yang tidak punya BNB tidak bisa melakukan apa pun
di chain ini, berapa pun saldo token-nya.

**Karakter yang relevan untuk airdrop:**
- Gas sangat murah, jadi interaksi frekuensi tinggi masuk akal secara ekonomi —
  berbeda dari mainnet di mana itu justru mencurigakan
- Ekosistemnya besar dan banyak proyek meluncurkan campaign di sini
- PancakeSwap adalah DEX dominan; banyak quest mengarah ke sana

## Yang sering salah
- **Mengirim ETH ke BSC.** Token yang sama bisa ada di banyak chain; yang
  terkirim ke chain salah sering tidak bisa diambil kembali.
- Lupa bahwa **gas butuh BNB**. Sebelum mendelegasikan task on-chain di sini,
  pastikan wallet punya BNB — kalau tidak, worker akan buntu di langkah pertama
  dan melaporkannya sebagai kegagalan proyek.
- **BSC (56) vs BSC Testnet (97).** Testnet tidak dihitung untuk kualifikasi.
