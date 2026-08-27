# Solana

## Fakta yang diverifikasi
- `chain_id`    : **tidak ada** — Solana bukan EVM
- `native`      : SOL
- `explorer`    : https://explorer.solana.com, https://solscan.io
- `cluster`     : `mainnet-beta`, `devnet`, `testnet` (bukan "chain id")
- Diperiksa pada : 2026-08-27

## RPC publik
- `https://api.mainnet-beta.solana.com`

Rate-limit-nya ketat untuk pemakaian publik. Untuk pemakaian serius butuh RPC
berbayar atau milik sendiri.

## Yang perlu diketahui agent

**Ini chain yang paling berbeda dari yang lain, dan perbedaannya penting.**

Solana memakai SVM dengan Ed25519, bukan EVM dengan secp256k1. Konsekuensinya:

- **Tidak ada `chain_id`.** Yang ada adalah nama cluster. `eth_chainId` tidak
  berlaku dan tidak akan pernah menjawab.
- **Tidak ada selector 4-byte.** Instruksi berupa program ID + index instruksi
  dalam `VersionedTransaction` yang sudah terserialisasi.
- **Wallet-nya Phantom**, bukan MetaMask/OKX. Provider-nya `window.solana`,
  bukan `window.ethereum`.
- **Signing lewat `signTransaction` / `signAllTransactions`**, bukan
  `eth_sendTransaction`.

### Kenapa agent tidak bisa membaca maksud transaksinya

Untuk EVM, selector calldata bisa dibaca: `0x095ea7b3` jelas berarti `approve`.
Untuk Solana, agent harus mendeserialisasi `VersionedTransaction` dan memetakan
program ID + index ke makna — dan itu tidak dilakukan AgentDrop.

**Konsekuensi praktis yang harus dipatuhi:** untuk Solana, agent **wajib**
menyerahkan ke manusia dengan **menjelaskan apa yang diminta situs**, bukan
menyajikan popup tanpa konteks. Manusia yang menyetujui di Phantom tidak bisa
mengandalkan agent untuk menerjemahkan instruksinya.

### Padanan "approve" di Solana lebih berbahaya

| EVM | Solana (SPL Token) | Catatan |
|---|---|---|
| `approve` | `Approve` (index 4) / `ApproveChecked` (13) | masih bisa dicabut dengan `Revoke` (5) |
| — | **`SetAuthority` (index 6)** | **memindahkan kepemilikan token account. Tidak bisa diurungkan dengan revoke** |

`SetAuthority` adalah yang paling berbahaya karena setelah terjadi, mencabut
approve tidak menolong — kepemilikannya sudah pindah. Ini alasan aturan lama
"SetAuthority selalu eskalasi" tetap relevan meski policy engine-nya sudah
dihapus: **agent harus menandai dan menjelaskan kalau melihatnya**, lalu
menyerahkan ke manusia.

## Yang sering salah
- Mencari `window.ethereum` di situs Solana. Yang ada `window.solana`.
- Mengira "testnet" Solana sama dengan testnet EVM. Cluster Solana berbeda
  mekanisme dan faucet-nya berbeda.
- Menganggap approval Solana bisa dicabut seperti EVM. Untuk `SetAuthority`,
  tidak bisa.
