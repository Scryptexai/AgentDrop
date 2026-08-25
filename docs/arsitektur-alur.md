# Diagram Alur AgentDrop

Diagram ini **diturunkan dari isi repo**, bukan dari niat. Setiap panah merujuk
file yang benar-benar ada. Bagian akhir mendaftar titik yang mungkin tidak
sesuai dengan yang Anda mau — periksa bagian itu dulu.

Legenda: ✅ terpasang & terverifikasi statis · ⚠️ terpasang tapi belum diuji
hidup · ❌ belum dibangun

---

## 1. Alur utama: Telegram → orchestrator → worker

✅ Struktur delegasi terpasang. `worker-orchestrator` adalah **satu-satunya**
profil dengan `delegate_task` + `delegation`, dan satu-satunya yang punya
`platform_toolsets.telegram`.

```mermaid
flowchart TD
    U(["Operator<br/>(Telegram)"]) -->|"kirim format task"| GW["hermes gateway run<br/>profil: worker-orchestrator"]
    GW --> ORC["ORCHESTRATOR<br/>baca SOUL.md + skill airdrop-intake"]

    ORC --> K{"Klasifikasi tiap task"}

    K -->|auto| D1["delegate_task<br/>role: leaf"]
    K -->|recurring| D2["delegate_task<br/>+ butuh cron"]
    K -->|"auto:wallet"| PW["policy engine<br/>tools/signing_policy.py"]
    PW -->|ALLOW| D1
    PW -->|"ESCALATE / DENY"| H1["Operator"]
    K -->|unknown| INV["Investigasi dulu<br/>buka halaman, baca syarat"]
    INV --> K

    K -->|human:oauth| H2["Operator via noVNC"]
    K -->|human:inbox| H3["Operator"]
    K -->|human:kyc| H4["Operator"]
    K -->|blocked CAPTCHA/2FA| H5["Operator via noVNC"]

    D1 --> WA["worker-analyzer"]
    D1 --> WQ["worker-quests"]
    D1 --> WD["worker-daily"]
    D1 --> WDC["worker-discord"]
    D2 --> WD

    WA --> R["Laporan balik ke orchestrator"]
    WQ --> R
    WD --> R
    WDC --> R
    R --> ORC
    ORC -->|"rangkuman"| U

    H1 -.->|"selesai dikerjakan manusia"| ORC
    H2 -.-> ORC
```

**Batas yang terpasang** (`config/hermes/profiles/worker-orchestrator/config.yaml`):

| Setelan | Nilai | Artinya |
|---|---|---|
| `delegation.orchestrator_enabled` | `true` | delegasi aktif |
| `delegation.max_spawn_depth` | `1` | worker **tidak bisa** mendelegasikan lagi |
| `delegation.max_concurrent_children` | `3` | maksimal 3 worker paralel |
| `approvals.mode` | `smart` | aturan guardian bahasa alami |
| `approvals.cron_mode` | `deny` | job cron tidak boleh minta approval |

---

## 2. Alur browser per aksi (protokol wajib)

✅ Terpasang di **6 SOUL.md** + `skills/browser-operation/SKILL.md`.
Validator bagian `[12]` menolak build kalau bloknya hilang.

```mermaid
flowchart TD
    S(["Worker perlu bertindak di halaman"]) --> NAV["browser_navigate ke URL"]
    NAV --> SNAP["browser_snapshot<br/>accessibility tree + ref"]
    SNAP --> VER{"URL & judul cocok<br/>dengan tujuan?"}
    VER -->|tidak| NAV
    VER -->|ya| PICK["Pilih elemen dari snapshot<br/>TANPA CSS selector / XPath"]
    PICK --> ACT["browser_click ref='@eN'<br/>atau browser_type"]
    ACT --> CHK{"Verifikasi hasil:<br/>berhasil / gagal / tidak diketahui"}
    CHK -->|berhasil| CNT["Hitung progres eksplisit<br/>'3 dari 7'"]
    CHK -->|gagal| STUCK{"Sudah 2x gagal<br/>dengan cara sama?"}
    STUCK -->|belum| SNAP
    STUCK -->|ya| LADDER["Tangga kebuntuan:<br/>scroll → tutup popup →<br/>snapshot ulang → back → tab baru"]
    LADDER --> SNAP
    LADDER -->|"3x gagal"| STOP(["BERHENTI<br/>lapor ke manusia"])
    CNT --> MORE{"Masih ada aksi?"}
    MORE -->|ya| SNAP
    MORE -->|tidak| SHOT["Screenshot bukti"] --> DONE(["Selesai"])
```

Kalau accessibility tree tidak cukup (canvas, overlay, popup) → turun ke
`browser_vision` atau `computer_use(mode='som')` (Set-of-Mark, elemen bernomor
di atas screenshot).

---

## 3. Alur signature wallet

⚠️ **Mesin kebijakan: terpasang & teruji (47 test). Shim-nya: ❌ belum dibangun.**

```mermaid
flowchart TD
    SITE(["Website airdrop minta signature"]) -.->|"butuh window.ethereum"| SHIM["❌ Shim EIP-1193<br/>WebExtension Camoufox<br/>+ daemon signing lokal"]
    SHIM -.->|"POST request"| ENG["tools/signing_policy.py<br/>decide()"]

    ENG --> C0{"Input lengkap?<br/>method + chain_id terbaca?"}
    C0 -->|tidak| ESC
    C0 -->|ya| C1{"chain_id dikenal?<br/>(hex '0xaa36a7' → 11155111)"}
    C1 -->|tidak| ESC
    C1 -->|ya| C2{"Batas harian 40<br/>tercapai?"}
    C2 -->|ya| ESC
    C2 -->|tidak| C3{"Kelas method?"}

    C3 -->|"personal_sign"| MSG{"Chain?"}
    MSG -->|testnet| ALW
    MSG -->|"mainnet"| ALW

    C3 -->|"eth_signTypedData_v4"| TD{"Chain?"}
    TD -->|testnet| ALW
    TD -->|"mainnet EIP-712 bisa berisi permit"| ESC

    C3 -->|"eth_sendTransaction"| SEL{"Selector calldata?"}

    SEL -->|"approve / permit /<br/>increaseAllowance"| AMT{"Nilai allowance<br/>(posisi ABI: approve=kata 1,<br/>permit=kata 2)"}
    AMT -->|"tak terbatas / > 10.000 token"| ESC
    AMT -->|"terbatas + testnet"| ALW
    AMT -->|"terbatas + mainnet"| ESC

    SEL -->|"setApprovalForAll"| ESC
    SEL -->|"alamat di denylist"| DEN
    SEL -->|"lainnya"| VAL{"value > 0?<br/>(hex '0xde0b...' → wei)"}
    VAL -->|"ya + testnet"| ALW
    VAL -->|"ya + mainnet > cap 0"| ESC
    VAL -->|"tidak + testnet"| ALW
    VAL -->|"tidak + mainnet"| ESC

    ALW(["✅ ALLOW — exit 0<br/>tanda tangan otomatis"])
    ESC(["⚠️ ESCALATE — exit 3<br/>tanya manusia"])
    DEN(["⛔ DENY — exit 4"])
```

Postur `config/hermes/signing-policy.yaml` — **OTONOM PENUH**, sesuai keputusan
operator (wallet khusus yang dikelola agent sepenuhnya):

| Situasi | Testnet | Mainnet |
|---|---|---|
| Message signing (login/SIWE/verify) | otomatis | otomatis |
| EIP-712 typed data | otomatis | **selalu tanya** — tidak bisa dimatikan |
| Transaksi tanpa nilai (mint/claim) | otomatis | otomatis |
| Allowance terbatas | otomatis | otomatis |
| Allowance tak terbatas | otomatis | otomatis *(dicatat keras ke stderr)* |
| Transfer bernilai | otomatis | otomatis sampai **10 ETH** |
| Alamat di `spender_denylist` | **DENY** | **DENY** |
| Melebihi 1000 approve/hari | tanya | tanya |

Dua rem yang tetap aktif meski semuanya otomatis: `spender_denylist` (menang
atas semua kelonggaran, diuji di validator) dan `max_auto_approvals_per_day`
(penahan loop, bukan penahan Anda).

---

## 4. Alur eskalasi ke manusia

✅ noVNC terpasang di `config/camofox/camofox.config.json` (plugin vnc).

```mermaid
flowchart LR
    A(["Agent mentok"]) --> B{"Jenis halangan"}
    B -->|CAPTCHA / 2FA| V["Buka noVNC<br/>localhost:6080/vnc.html"]
    B -->|OAuth Twitter/Discord| V
    B -->|KYC / selfie| V
    B -->|Signature mainnet| V
    B -->|Allowance tak terbatas| V
    V --> M["Manusia menyelesaikan"]
    M --> R["Kontrol kembali ke agent"]
    R --> C["Agent lanjut, verifikasi dulu"]
```

---

## 5. Alur terjadwal (cron)

✅ Terpasang di `scripts/install-cron.sh`. Laporan dikirim ke **Telegram**
(`CRON_DELIVER=telegram`, default). Ganti ke `local` lewat env kalau perlu.

```mermaid
flowchart TD
    C09["09:00 tiap hari<br/>worker-daily<br/>skill daily-executor"] --> V13
    V13["13:00 tiap hari<br/>worker-monitor<br/>verifikasi aksi pagi"] --> R20
    R20["20:00 tiap hari<br/>worker-monitor<br/>laporan harian"] --> W21
    W21["Minggu 21:00<br/>worker-monitor<br/>ringkasan + LANJUT/EVALUASI/BERHENTI"]
    C09 --> L[("data/logs/<br/>data/campaigns/")]
    V13 --> L
    R20 --> L
    W21 --> L
    C09 -->|"--deliver telegram"| TG(["Telegram Anda"])
    V13 --> TG
    R20 --> TG
    W21 --> TG
```

`install-cron.sh` memperingatkan kalau `TELEGRAM_BOT_TOKEN` belum diisi, karena
tanpa itu laporan tidak akan sampai.

---

## 6. Alur pemasangan

```mermaid
flowchart TD
    I["bash install.sh"] --> E["Isi .env<br/>API key + Telegram"]
    E --> M["Pilih model"]
    M --> SB["scripts/start-browser.sh<br/>Camofox + noVNC"]
    SB --> LG["scripts/takeover.sh<br/>login VISUAL per platform"]
    LG --> BI["scripts/burn-in.sh<br/>Uji 1-4"]
    BI -->|hijau| G["scripts/start-gateway.sh"]
    BI -->|"gagal 3x sama"| FIX(["Perbaiki lingkungan,<br/>bukan prompt"])
    G --> USE["Pakai via Telegram"]
    USE --> CR["scripts/install-cron.sh"]
```

---

## Status temuan

Enam titik sempat ditandai tidak sesuai. Tiga sudah dibereskan, tiga masih terbuka.

### ✅ A — Kontradiksi wallet: SELESAI

`worker-orchestrator/SOUL.md` tidak lagi menulis "signature -> wajib operator".
Klasifikasi `human:wallet` dipecah:

- `auto:wallet` — signature & transaksi, agent jalan terus, **policy engine yang
  memutuskan**
- `human:wallet` — hanya kalau policy engine menjawab `ESCALATE` atau `DENY`

`Submit EVM Address` juga dikoreksi: dulu masuk `human:wallet` padahal cuma
alamat publik. Sekarang `auto`.

SOUL.md sekarang menyertakan perintah nyata untuk memanggil policy engine dan
aturan tegas: *"Saya tidak menimpa keputusan policy engine. Kalau jawabannya
ESCALATE, saya tidak mencari jalan lain untuk menandatanganinya."*

### ✅ C — Skill dibatasi per profil: SELESAI

`scripts/setup.sh` sekarang punya `declare -A PROFILE_SKILLS`. Slot terpasang
turun dari **48 (6×8) menjadi 19**. `worker-discord` tidak lagi bisa memanggil
`daily-executor`.

Folder skill **dihapus lebih dulu** sebelum disalin, jadi mengeluarkan sebuah
skill dari pemetaan benar-benar mencabutnya saat setup dijalankan ulang. Tanpa
ini pembatasan hanya berlaku pada pemasangan pertama.

Validator menolak build kalau: `browser-operation` hilang dari profil mana pun,
ada skill yang tidak dipetakan ke profil mana pun, pemetaan menyebut skill yang
tidak ada, atau baris `rm -rf` dihapus. Keempatnya sudah diuji negatif.

### ✅ D — Laporan cron ke Telegram: SELESAI

`--deliver local` diganti `--deliver "$DELIVER"` dengan `CRON_DELIVER` default
`telegram`. Ada peringatan kalau `TELEGRAM_BOT_TOKEN` belum diisi.

### ❌ B — Shim EIP-1193 belum dibangun: MASIH TERBUKA

Ini satu-satunya yang membuat rute otonom belum benar-benar jalan. Policy engine
sudah teruji 47 test, tapi **tidak ada yang memanggilnya** — website tidak punya
`window.ethereum`. Yang harus dibuat: WebExtension Camoufox + daemon signing
lokal. Harus addon, karena `camofox-browser` tidak punya `addInitScript`.

### ⚠️ E — `delegation` tidak ada di `platform_toolsets.telegram`: PERLU UJI HIDUP

Orchestrator punya `delegation` di toolset utamanya, tapi daftar untuk platform
telegram hanya `delegate_task`. Perlu dijalankan sungguhan untuk memastikan
delegasi tetap jalan saat pesan datang dari Telegram — persis jalur yang Anda
pakai.

### ⚠️ F — Belum pernah dijalankan hidup

Tidak ada `docker` maupun `hermes` di lingkungan pengembangan. Semua verifikasi
statis: 56 pemeriksaan + 47 test unit + uji CLI + uji `burn-in.sh` dengan stub.

---

## Soal klaim "70-80% quest itu signature mainnet"

Diminta diverifikasi lewat pencarian. **Angka 70-80% itu tidak saya temukan di
sumber mana pun.** Yang saya temukan justru sebaliknya untuk fase farming 2026:
Monad, Arc (testnet-only), Orbinum, DAC, Kite AI, Variational, dan Retium
semuanya berbasis testnet.

Tapi ada pembedaan teknis yang lebih penting daripada angkanya:

| Yang diminta situs | Jenis | Butuh saldo mainnet? | Status di policy engine |
|---|---|---|---|
| "Connect EVM Wallet" / verify ownership | `personal_sign` — off-chain | **tidak** | **sudah otomatis** sejak awal |
| "Sign message to verify" | `personal_sign` — off-chain | **tidak** | **sudah otomatis** sejak awal |
| Mint / claim / check-in | transaksi tanpa nilai | gas saja | otomatis (baru) |
| Swap / bridge / approve | transaksi + allowance | **ya** | otomatis (baru) |
| EIP-712 typed data | bisa berisi `permit` | tidak | **tetap tanya** di mainnet |

Jadi mayoritas task "wallet" di platform quest sebenarnya **signature off-chain**
yang tidak butuh saldo — dan itu sudah otomatis bahkan sebelum perubahan ini.
Yang baru diotomatiskan adalah transaksi dan allowance mainnet sungguhan.
