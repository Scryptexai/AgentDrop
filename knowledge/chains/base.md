# Base

## Fakta yang diverifikasi
- `chain_id`    : **8453** (`0x2105`)
- `native`      : ETH (untuk gas)
- `explorer`    : https://basescan.org
- `testnet`     : Base Sepolia, chain_id **84532**
- Diperiksa pada : 2026-08-27 (chainlist / evmchainlist)

## RPC publik
- `https://mainnet.base.org`
- `https://base-rpc.publicnode.com`

**Belum diverifikasi sesi ini.** Cek `eth_chainId` harus `0x2105`.

## Yang perlu diketahui agent

**L2 milik Coinbase, OP Stack.** Ini salah satu chain yang paling sering disebut
proyek sebagai syarat kualifikasi — murah, cepat, dan ekosistemnya aktif.

**Yang membuat Base berbeda dalam praktik:**
- Gas jauh lebih murah dari mainnet, jadi interaksi kecil masuk akal secara
  ekonomi. Ini mengubah perhitungan "apakah tx ini terlihat seperti bot".
- Banyak proyek mengadakan campaign khusus Base. Formatnya lihat
  `../patterns/format-task.md`.
- Bridge dari mainnet ke Base adalah task yang umum diminta. Ada jalur resmi
  (bridge milik Coinbase) dan jalur pihak ketiga — bedanya penting untuk
  kualifikasi, karena sebagian proyek hanya menghitung bridge resmi.

## Yang sering salah
- **Base Sepolia (84532) bukan Base (8453).** Testnet tidak dihitung untuk
  kualifikasi mana pun.
- Menganggap semua bridge setara. Sebagian proyek secara eksplisit hanya
  menghitung bridge resminya.
- Chain ID 8453 mirip 84532 — beda satu digit, beda jaringan.
