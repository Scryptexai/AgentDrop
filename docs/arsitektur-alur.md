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
    K -->|unknown| INV["Investigasi dulu<br/>buka halaman, baca syarat"]
    INV --> K

    K -->|human:wallet| H1["Operator"]
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

Postur bawaan `config/hermes/signing-policy.yaml`:

| Situasi | Testnet | Mainnet |
|---|---|---|
| Message signing (login/SIWE) | otomatis | otomatis |
| EIP-712 typed data | otomatis | **selalu tanya** |
| Transaksi tanpa nilai (mint/claim) | otomatis | **tanya** |
| Allowance terbatas | otomatis | **tanya** |
| Allowance tak terbatas | **selalu tanya** | **selalu tanya** |
| Transfer bernilai | otomatis | **tanya** (cap 0 wei) |

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

✅ Terpasang di `scripts/install-cron.sh`. **Catatan: `--deliver local`, bukan
telegram** — lihat bagian "titik yang mungkin tidak sesuai".

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
```

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

## ⚠️ Titik yang mungkin TIDAK sesuai dengan yang Anda mau

Ini temuan dari membaca repo, bukan asumsi. Mohon dikonfirmasi.

### A. Kontradiksi rute wallet — **paling penting**

Anda memilih rute otonom (policy engine), tapi
`config/hermes/profiles/worker-orchestrator/SOUL.md` masih menulis:

> `human:wallet` | "Connect EVM Wallet", sign message, bridging, deposit | **operator**
> `human:wallet` (signature -> **wajib operator**)

Artinya orchestrator akan **tetap menyerahkan semua signature ke Anda**, dan
policy engine tidak pernah dipanggil. Dua aturan ini bertentangan. Perlu
diputuskan: klasifikasi `human:wallet` dipecah jadi `auto:wallet-testnet` /
`auto:wallet-mainnet-terbatas` / `human:wallet`, atau rute otonom dibatalkan.

### B. Shim-nya belum ada

Mesin kebijakan sudah teruji, tapi tidak ada yang memanggilnya. Website tidak
punya `window.ethereum` untuk diajak bicara. Harus dibangun: WebExtension
Camoufox + daemon signing lokal. Harus addon, karena `camofox-browser` tidak
punya `addInitScript`.

### C. Semua skill disalin ke semua profil

`scripts/setup.sh` menyalin **8 skill ke 6 profil** tanpa pemetaan. Spesialisasi
hanya datang dari SOUL.md, bukan dari pembatasan skill. Kalau Anda ingin
`worker-discord` benar-benar tidak bisa memanggil `daily-executor`, itu belum
terpasang.

### D. Laporan cron tidak masuk Telegram

`install-cron.sh` memakai `--deliver local`. Laporan harian/mingguan tertulis ke
`data/logs/`, **tidak** dikirim ke Telegram Anda. Padahal alur yang Anda minta
berpusat di Telegram.

### E. `delegation` tidak ada di `platform_toolsets.telegram`

Orchestrator punya `delegation` di toolset utamanya, tapi daftar untuk platform
telegram hanya mencantumkan `delegate_task`. Perlu diuji apakah delegasi tetap
jalan saat pesan datang dari Telegram — ini persis jalur yang Anda pakai.

### F. Belum pernah dijalankan hidup

Tidak ada `docker` maupun `hermes` di lingkungan pengembangan. Semua verifikasi
bersifat statis: 54 pemeriksaan + 47 test unit + uji CLI + uji `burn-in.sh`
dengan stub.
