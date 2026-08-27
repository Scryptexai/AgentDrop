# Arbitrum One

## Fakta yang diverifikasi
- `chain_id`    : **42161** (`0xa4b1`)
- `native`      : ETH (untuk gas)
- `explorer`    : https://arbiscan.io
- `rpc`         : `https://arb1.arbitrum.io/rpc`, `https://arbitrum-one-rpc.publicnode.com`
- Diperiksa pada : 2026-08-27 (chainlist / chainlist.wtf)

## Yang perlu diketahui agent

**L2 optimistic rollup.** Salah satu chain yang paling sering menjadi syarat
kualifikasi, dan ARB airdrop adalah salah satu yang paling dikenal.

**Yang membedakan secara teknis:**
- Gas dibayar dengan ETH, tapi mekanismenya punya komponen L1 + L2. Estimasi gas
  bisa berbeda dari yang ditampilkan wallet — ini normal, bukan bug.
- Ada **Arbitrum One (42161)** dan **Arbitrum Nova (42170)**. Keduanya jaringan
  berbeda dengan token dan ekosistem berbeda.

## Yang sering salah
- **Arbitrum One vs Arbitrum Nova.** Yang biasanya dimaksud proyek adalah One
  (42161). Nova (42170) chain terpisah. Salah pilih berarti aktivitas tidak
  dihitung.
- **Arbitrum Sepolia (421614)** adalah testnet — tidak dihitung.
- Menganggap estimasi gas yang lebih tinggi dari perkiraan sebagai kegagalan.
  Di rollup, komponen L1 membuat totalnya sulit diprediksi.
