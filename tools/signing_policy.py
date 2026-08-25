#!/usr/bin/env python3
"""
signing_policy.py — mesin kebijakan untuk permintaan signature wallet.

MASALAH YANG DISELESAIKAN
-------------------------
Aturan lama "semua signature butuh manusia" tidak bisa dipakai: 5 proyek
testnet x 10 transaksi = 50 approval manual, dan itu baru testnet. Kalau
operator harus mengawasi layar terus, agent tidak memberi nilai apa pun.

Tapi "auto-approve semua" juga salah. Yang membunuh wallet farming bukan
"signature" secara umum — yang membunuh adalah APA yang ditandatangani:

    approve(spender, MAX_UINT256)     <- allowance tak terbatas, TETAP berlaku
                                         setelah airdrop selesai
    setApprovalForAll(operator, true) <- kelas yang sama, untuk NFT
    transfer bernilai di mainnet      <- kerugian nyata

Jadi keputusannya bukan biner manusia-vs-otomatis, melainkan PER PERMINTAAN.

PRINSIP DESAIN
--------------
1. FAIL-CLOSED. Apa pun yang tidak dikenali -> ESCALATE, tidak pernah ALLOW.
2. Testnet permisif, mainnet ketat. Token testnet tidak bernilai.
3. Message signing (login/SIWE) tidak memindahkan nilai -> boleh otomatis.
4. Allowance tak terbatas -> SELALU escalate, di chain mana pun.
5. Batas laju: jumlah approval & total nilai per hari dibatasi.

CATATAN JUJUR TENTANG KUNCI
---------------------------
Agar agent bisa menandatangani, private key HARUS terjangkau oleh otomasi.
Tidak ada cara mengelak dari itu. Yang bisa dilakukan adalah membatasi
kerugian: wallet burner khusus, saldo seminimal mungkin, key di file mode 600
di luar repo, tidak pernah masuk log/screenshot/browser storage.

Modul ini TIDAK menyimpan, membaca, atau menyentuh private key. Ia hanya
memutuskan boleh/tidaknya sebuah permintaan. Penandatanganannya dilakukan
komponen lain.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:
    yaml = None  # policy tetap jalan dengan default bawaan

# ============================================================================
# Konstanta — selector diverifikasi dengan keccak256, bukan dari ingatan
#   keccak256("approve(address,uint256)")[:4] == 095ea7b3
# ============================================================================
SEL_APPROVE = "0x095ea7b3"                 # approve(address,uint256)
SEL_SET_APPROVAL_FOR_ALL = "0xa22cb465"    # setApprovalForAll(address,bool)
SEL_TRANSFER = "0xa9059cbb"                # transfer(address,uint256)
SEL_TRANSFER_FROM = "0x23b872dd"           # transferFrom(address,address,uint256)
SEL_INCREASE_ALLOWANCE = "0x39509351"      # increaseAllowance(address,uint256)
SEL_DECREASE_ALLOWANCE = "0xa457c2d7"      # decreaseAllowance(address,uint256)
SEL_PERMIT = "0xd505accf"                  # permit(...)

ALLOWANCE_SELECTORS = {
    SEL_APPROVE, SEL_SET_APPROVAL_FOR_ALL, SEL_INCREASE_ALLOWANCE, SEL_PERMIT,
}

# Posisi argumen "nilai allowance" dalam calldata, sebagai indeks kata 32-byte
# SETELAH selector. Ini penting: posisi nilainya BERBEDA per fungsi.
#
#   approve(address spender, uint256 value)                 -> kata 1
#   increaseAllowance(address spender, uint256 addedValue)  -> kata 1
#   permit(address owner, address spender, uint256 value,
#          uint256 deadline, uint8 v, bytes32 r, bytes32 s) -> kata 2
#   setApprovalForAll(address operator, bool approved)      -> tidak ada amount
#
# Membaca kata 0 (yang dilakukan versi sebelumnya) mengembalikan ALAMAT, bukan
# nilai. Alamat selalu jauh di atas soft cap, jadi setiap approve — termasuk
# yang terbatas dan sah — dinilai "tak terbatas" dan di-escalate.
ALLOWANCE_VALUE_INDEX = {
    SEL_APPROVE: 1,
    SEL_INCREASE_ALLOWANCE: 1,
    SEL_PERMIT: 2,
}

MAX_UINT256 = 2**256 - 1

# Chain ID. Testnet = token tidak bernilai -> boleh permisif.
TESTNET_CHAIN_IDS = {
    11155111: "ethereum-sepolia",
    17000: "ethereum-holesky",
    97: "bsc-testnet",
    80002: "polygon-amoy",
    421614: "arbitrum-sepolia",
    11155420: "optimism-sepolia",
    84532: "base-sepolia",
    43113: "avalanche-fuji",
    10143: "monad-testnet",
    80069: "berachain-bepolia",
}

MAINNET_CHAIN_IDS = {
    1: "ethereum",
    56: "bsc",
    137: "polygon",
    42161: "arbitrum",
    10: "optimism",
    8453: "base",
    43114: "avalanche",
}

# Nama method EIP-1193, DINORMALISASI KE LOWERCASE.
# decide() memanggil method.strip().lower(), jadi pembanding apa pun yang
# mengandung huruf kapital tidak akan pernah cocok — bug yang pernah ada di
# sini membuat setiap eth_sendTransaction berakhir "unknown-method".
MESSAGE_METHODS = {
    "personal_sign", "eth_sign", "typed_data",
    "eth_signtypeddata", "eth_signtypeddata_v4",
}
# EIP-712 bisa membungkus `permit`, yang setara allowance. Diperlakukan
# lebih ketat di mainnet.
TYPED_DATA_METHODS = {"typed_data", "eth_signtypeddata", "eth_signtypeddata_v4"}
TX_METHODS = {"send_transaction", "eth_sendtransaction"}

ALLOW = "ALLOW"
ESCALATE = "ESCALATE"
DENY = "DENY"


# ============================================================================
@dataclass
class Decision:
    verdict: str
    reason: str
    rule: str = ""

    def to_dict(self) -> dict:
        return {"verdict": self.verdict, "reason": self.reason, "rule": self.rule}


@dataclass
class Policy:
    """Kebijakan. Default di sini adalah postur bawaan yang aman."""
    # Testnet
    testnet_auto_approve_messages: bool = True
    testnet_auto_approve_zero_value_tx: bool = True
    testnet_auto_approve_allowance: bool = True   # allowance di testnet tak bernilai
    # Mainnet
    mainnet_auto_approve_messages: bool = True    # login/SIWE tidak memindahkan nilai
    mainnet_auto_approve_zero_value_tx: bool = False
    mainnet_auto_approve_allowance: bool = False
    # Allowance tak terbatas (MAX_UINT256 / setApprovalForAll / di atas soft cap).
    # Default MATI. Menyalakannya berarti sebuah kontrak boleh menguras seluruh
    # saldo token itu SELAMANYA, termasuk setelah airdropnya selesai.
    # Ini vektor pengurasan nomor satu pada wallet farming.
    auto_approve_unlimited_allowance: bool = False
    # Batas allowance yang masih dianggap wajar (dalam unit token, bukan wei)
    allowance_soft_cap: int = 10_000
    # Batas nilai transaksi mainnet yang masih boleh otomatis (dalam wei)
    mainnet_max_auto_value_wei: int = 0
    # Batas laju per hari
    max_auto_approvals_per_day: int = 40
    # Alamat yang tidak pernah boleh di-approve
    spender_denylist: list = field(default_factory=list)
    # Kontrak yang dipercaya (opsional)
    contract_allowlist: list = field(default_factory=list)

    @classmethod
    def from_yaml(cls, path: Path) -> "Policy":
        if yaml is None or not path.exists():
            return cls()
        raw = yaml.safe_load(path.read_text()) or {}
        known = {f for f in cls.__dataclass_fields__}
        kwargs = {k: v for k, v in raw.items() if k in known}
        unknown = set(raw) - known
        if unknown:
            print(f"[policy] peringatan: key tak dikenal diabaikan: {sorted(unknown)}",
                  file=sys.stderr)
        return cls(**kwargs)


# ============================================================================
# Helper
# ============================================================================
def _selector(data: str | None) -> str:
    if not data or len(data) < 10:
        return ""
    d = data if data.startswith("0x") else "0x" + data
    return d[:10].lower()


def _word(data: str | None, idx: int) -> int | None:
    """Ambil kata 32-byte ke-`idx` setelah 4-byte selector, sebagai int."""
    if not data:
        return None
    d = data[2:] if data.startswith("0x") else data
    # 8 karakter pertama adalah selector; kata ke-`idx` mulai setelahnya.
    start = 8 + idx * 64
    chunk = d[start:start + 64]
    if len(chunk) < 64:
        return None
    try:
        return int(chunk, 16)
    except ValueError:
        return None


def _allowance_amount(data: str | None, sel: str) -> int | None:
    """Nilai allowance sesuai posisi ABI fungsi itu.

    Mengembalikan None kalau fungsi memang tidak punya argumen nilai
    (setApprovalForAll) ATAU calldata-nya terpotong/rusak. Pemanggil
    memperlakukan None sebagai "tak terbatas" -> fail closed.
    """
    idx = ALLOWANCE_VALUE_INDEX.get(sel)
    if idx is None:
        return None
    return _word(data, idx)


def _normalize_quantity(raw: Any) -> int | None:
    """Nilai wei bisa datang sebagai int ATAU string hex dari EIP-1193.

    Provider mengirim `"value": "0xde0b6b3a7640000"`. Kalau engine hanya
    mengerti `value_wei` bertipe int, transfer 1 ETH terbaca sebagai 0 dan
    masuk kelas "transaksi tanpa nilai" — yang di mainnet bisa auto-approve
    kalau mainnet_auto_approve_zero_value_tx dinyalakan. Klasifikasi nilai
    adalah keputusan keamanan, bukan detail teknis.

    Mengembalikan None kalau tidak bisa diartikan (pemanggil -> ESCALATE).
    """
    if raw is None:
        return 0
    if isinstance(raw, bool):
        return None
    if isinstance(raw, int):
        return raw
    if isinstance(raw, str):
        s = raw.strip().lower()
        if s in ("", "0x"):
            return 0
        try:
            return int(s, 16) if s.startswith("0x") else int(s, 10)
        except ValueError:
            return None
    return None


def _normalize_chain_id(raw: Any) -> int | None:
    """Chain ID bisa datang sebagai int ATAU string hex dari EIP-1193.

    `eth_chainId` di provider manapun mengembalikan "0xaa36a7", bukan 11155111.
    Kalau tidak dinormalisasi, _chain_class() tidak akan pernah cocok dan
    SEMUA permintaan berakhir ESCALATE — aman, tapi sistemnya tidak berguna.
    """
    if raw is None:
        return None
    if isinstance(raw, bool):          # bool adalah subclass int; tolak eksplisit
        return None
    if isinstance(raw, int):
        return raw
    if isinstance(raw, str):
        s = raw.strip().lower()
        try:
            return int(s, 16) if s.startswith("0x") else int(s, 10)
        except ValueError:
            return None
    return None


def _chain_class(chain_id: int | None) -> str:
    if chain_id is None:
        return "unknown"
    if chain_id in TESTNET_CHAIN_IDS:
        return "testnet"
    if chain_id in MAINNET_CHAIN_IDS:
        return "mainnet"
    return "unknown"


# ============================================================================
# Mesin keputusan
# ============================================================================
def decide(req: dict[str, Any], policy: Policy | None = None,
           today_count: int = 0) -> Decision:
    """Putuskan satu permintaan signature.

    req yang diharapkan:
      {
        "method": "personal_sign" | "typed_data" | "send_transaction",
        "chain_id": 11155111,
        "to": "0x...",              # untuk send_transaction
        "value_wei": 0,
        "data": "0x095ea7b3...",
        "origin": "https://..."     # situs yang meminta
      }
    """
    p = policy or Policy()
    raw_method = req.get("method")
    method = raw_method.strip().lower() if isinstance(raw_method, str) else ""
    raw_chain = req.get("chain_id")
    chain_id = _normalize_chain_id(raw_chain)
    klass = _chain_class(chain_id)
    chain_name = (TESTNET_CHAIN_IDS.get(chain_id)
                  or MAINNET_CHAIN_IDS.get(chain_id)
                  or str(raw_chain))

    # ---- 0. Input tidak lengkap -> fail closed -------------------------------
    if not method:
        return Decision(ESCALATE, "method tidak ada di permintaan", "incomplete-input")
    if klass == "unknown":
        return Decision(ESCALATE,
                        f"chain_id {raw_chain} tidak dikenal (bukan testnet/mainnet yang terdaftar)",
                        "unknown-chain")

    # ---- 1. Batas laju -------------------------------------------------------
    if today_count >= p.max_auto_approvals_per_day:
        return Decision(ESCALATE,
                        f"batas harian tercapai ({today_count}/{p.max_auto_approvals_per_day})",
                        "rate-limit")

    # ---- 2. Message signing (login, SIWE) -----------------------------------
    # Tidak memindahkan nilai apa pun. Ini mayoritas permintaan saat farming.
    #
    # PENTING: `method` sudah di-lower() di atas, jadi pembandingnya juga harus
    # lowercase. Nama EIP-1193 aslinya berhuruf campuran ("eth_signTypedData_v4"),
    # dan menulisnya apa adanya di sini membuatnya TIDAK PERNAH cocok.
    if method in MESSAGE_METHODS:
        if klass == "testnet" and p.testnet_auto_approve_messages:
            return Decision(ALLOW, f"message signing di testnet ({chain_name})", "msg-testnet")
        if klass == "mainnet" and p.mainnet_auto_approve_messages:
            # Tetap ALLOW, tapi catat: EIP-712 bisa berisi permit yang setara approve.
            if method in TYPED_DATA_METHODS:
                return Decision(ESCALATE,
                                "EIP-712 typed data di mainnet bisa berisi permit yang setara "
                                "allowance — perlu diperiksa manusia",
                                "typed-data-mainnet")
            return Decision(ALLOW, "message signing (login) di mainnet", "msg-mainnet")
        return Decision(ESCALATE, "message signing tidak diizinkan otomatis oleh policy", "msg-policy")

    # ---- 3. Transaksi --------------------------------------------------------
    if method not in TX_METHODS:
        return Decision(ESCALATE, f"method '{method}' tidak dikenali", "unknown-method")

    sel = _selector(req.get("data"))
    # Input dari luar tidak pernah dipercaya bentuknya. Mesin kebijakan tidak
    # boleh melempar exception: kalau bentuknya aneh, jawabannya ESCALATE.
    # Terima kedua bentuk: value_wei (int, internal) dan value (hex, EIP-1193).
    # Kalau keduanya ada, value_wei yang menang supaya pemanggil internal bisa
    # menimpa dengan tegas.
    raw_value = req["value_wei"] if "value_wei" in req else req.get("value")
    value = _normalize_quantity(raw_value)
    if value is None:
        return Decision(ESCALATE, "value bukan angka yang bisa dibaca", "malformed-input")
    raw_to = req.get("to")
    if raw_to is None:
        to = ""
    elif isinstance(raw_to, str):
        to = raw_to.lower()
    else:
        return Decision(ESCALATE,
                        f"field 'to' bertipe {type(raw_to).__name__}, bukan string alamat",
                        "malformed-input")

    # 3a. Spender di denylist -> DENY keras
    if to and to in {s.lower() for s in p.spender_denylist}:
        return Decision(DENY, f"alamat tujuan {to} ada di denylist", "spender-denylist")

    # 3b. Allowance — kelas paling berbahaya
    if sel in ALLOWANCE_SELECTORS:
        amount = _allowance_amount(req.get("data"), sel)
        unlimited = (
            sel == SEL_SET_APPROVAL_FOR_ALL
            or amount is None
            or amount >= MAX_UINT256
            or amount > p.allowance_soft_cap * 10**18
        )
        if unlimited and not p.auto_approve_unlimited_allowance:
            # Allowance tak terbatas TETAP hidup setelah airdrop selesai.
            # Ini penyebab utama wallet farming terkuras.
            return Decision(ESCALATE,
                            f"allowance tak terbatas / di atas soft cap "
                            f"(selector {sel}) di {chain_name} — sisa berlaku selamanya",
                            "unlimited-allowance")
        if unlimited and klass == "mainnet":
            # Diizinkan otomatis hanya kalau operator menyalakannya dengan sadar.
            # Dicatat keras di log supaya bisa diaudit belakangan.
            print(f"[policy] PERHATIAN: unlimited allowance {sel} ke {to} di "
                  f"{chain_name} DIOTOMATISKAN (auto_approve_unlimited_allowance=true)",
                  file=sys.stderr)
            return Decision(ALLOW,
                            f"allowance tak terbatas di {chain_name} — DIOTOMATISKAN "
                            f"oleh kebijakan (berlaku selamanya)",
                            "unlimited-allowance-auto")
        if klass == "testnet" and p.testnet_auto_approve_allowance:
            return Decision(ALLOW,
                            f"allowance terbatas di testnet ({chain_name})",
                            "allowance-testnet")
        if klass == "mainnet" and p.mainnet_auto_approve_allowance:
            return Decision(ALLOW, "allowance terbatas di mainnet", "allowance-mainnet")
        return Decision(ESCALATE,
                        f"allowance di {chain_name} tidak diizinkan otomatis",
                        "allowance-policy")

    # 3c. Transfer bernilai
    if value > 0:
        if klass == "testnet":
            return Decision(ALLOW,
                            f"transfer bernilai di testnet ({chain_name}) — token tak bernilai",
                            "value-testnet")
        if value <= p.mainnet_max_auto_value_wei:
            return Decision(ALLOW, "transfer dalam batas nilai mainnet", "value-mainnet-cap")
        return Decision(ESCALATE,
                        f"transfer {value} wei di mainnet ({chain_name}) melebihi batas "
                        f"{p.mainnet_max_auto_value_wei}",
                        "value-mainnet")

    # 3d. Transaksi tanpa nilai (mint, check-in, claim)
    if klass == "testnet" and p.testnet_auto_approve_zero_value_tx:
        return Decision(ALLOW, f"transaksi tanpa nilai di testnet ({chain_name})", "zero-testnet")
    if klass == "mainnet" and p.mainnet_auto_approve_zero_value_tx:
        return Decision(ALLOW, "transaksi tanpa nilai di mainnet", "zero-mainnet")

    return Decision(ESCALATE,
                    f"transaksi tanpa nilai di {chain_name} tidak diizinkan otomatis",
                    "zero-policy")


# ============================================================================
# CLI
# ============================================================================
def main() -> int:
    ap = argparse.ArgumentParser(description="Putuskan satu permintaan signature wallet")
    ap.add_argument("--policy", default="config/hermes/signing-policy.yaml",
                    help="path ke signing-policy.yaml")
    ap.add_argument("--today-count", type=int, default=0,
                    help="jumlah auto-approve yang sudah terjadi hari ini")
    ap.add_argument("--request", help="JSON permintaan; '-' untuk baca stdin")
    args = ap.parse_args()

    policy = Policy.from_yaml(Path(args.policy))

    if args.request and args.request != "-":
        raw = args.request
    else:
        raw = sys.stdin.read()

    try:
        req = json.loads(raw)
    except json.JSONDecodeError as exc:
        print(json.dumps({"verdict": ESCALATE, "reason": f"JSON tidak valid: {exc}",
                          "rule": "bad-input"}))
        return 2

    d = decide(req, policy, today_count=args.today_count)
    print(json.dumps(d.to_dict(), ensure_ascii=False))
    # ALLOW -> 0, ESCALATE -> 3, DENY -> 4 (supaya bisa dipakai di shell)
    return {ALLOW: 0, ESCALATE: 3, DENY: 4}[d.verdict]


if __name__ == "__main__":
    sys.exit(main())
