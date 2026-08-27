# Ethereum Mainnet

## Fakta yang diverifikasi
- `chain_id`    : **1** (`0x1`)
- `native`      : ETH
- `explorer`    : https://etherscan.io
- `testnet`     : Sepolia, chain_id **11155111** (`0xaa36a7`)
- Diperiksa pada : 2026-08-27 (chainlist / evmchainlist)

## RPC publik
- `https://eth.llamarpc.com`
- `https://ethereum-rpc.publicnode.com`

**Belum diverifikasi sesi ini.** Cek dengan `curl -s <rpc> -d '{"jsonrpc":"2.0",
"id":1,"method":"eth_chainId","params":[]}'` sebelum dipakai; jawaban harus
`0x1`. RPC publik sering rate-limit dan kadang diam-diam mengarah ke chain lain.

## Yang perlu diketahui agent

**Ini chain paling mahal untuk salah.** Gas nyata, dana nyata, dan transaksi
tidak bisa diurungkan. Untuk mainnet, setiap approve dan setiap signature
diserahkan ke manusia lewat noVNC — tanpa pengecualian.

**Yang membuatnya tetap relevan untuk airdrop:** banyak proyek L2 dan DeFi
menghitung aktivitas di mainnet sebagai bagian dari kualifikasi, dan beberapa
airdrop wallet (MetaMask, Rainbow) berbasis di sini.

**Biaya adalah filter.** Interaksi mainnet yang tidak masuk akal secara ekonomi
— misalnya swap $1 dengan gas $8 — adalah tanda bot, bukan tanda rajin. Lihat
`../patterns/kualifikasi.md`.

## Yang sering salah
- Tertukar dengan **Sepolia**. Chain ID 1 vs 11155111. Salah chain berarti
  transaksi hilang atau dana terkirim ke tempat yang tidak bisa diambil.
- Menganggap "ETH" berarti mainnet. Base, Arbitrum, dan OP semuanya memakai ETH
  sebagai gas tapi chain-nya berbeda.
