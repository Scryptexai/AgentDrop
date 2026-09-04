# Arbitrum One

## Fakta yang diverifikasi
- `chain_id`    : **42161** (`0xa4b1`)
- `native`      : ETH (untuk gas)
- `explorer`    : https://arbiscan.io
- `rpc`         : `https://arb1.arbitrum.io/rpc`, `https://arbitrum-one-rpc.publicnode.com`
- Diperiksa pada : 2026-08-27 (chainlist / chainlist.wtf)

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
