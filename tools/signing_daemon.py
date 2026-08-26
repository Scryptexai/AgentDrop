#!/usr/bin/env python3
"""Daemon signing lokal untuk AgentDrop.

Ini komponen yang membuat rute otonom benar-benar jalan. Tanpa ini,
tools/signing_policy.py sudah teruji tapi tidak ada yang memanggilnya.

Arsitektur:

    halaman web
        │  window.ethereum.request({...})
        ▼
    inject.js  (page script, disuntik extension)
        │  window.postMessage
        ▼
    content.js (content script)
        │  browser.runtime.sendMessage
        ▼
    background.js
        │  HTTP + token
        ▼
    daemon ini ──► tools/signing_policy.decide()
                        │
                        ├── ALLOW    → tanda tangan, kembalikan
                        ├── ESCALATE → tolak dengan alasan, jangan tanda tangan
                        └── DENY     → tolak

KEPUTUSAN DESAIN YANG PENTING:

1. Bind 127.0.0.1 SAJA, tidak pernah 0.0.0.0. Kalau daemon ini terbuka ke
   jaringan, siapa pun di LAN bisa memakai wallet Anda.
2. Setiap request wajib membawa token. Halaman web bisa memanggil
   window.ethereum (itu memang cara kerjanya), tapi tidak bisa memanggil
   daemon ini langsung tanpa token yang hanya dipegang extension.
3. Private key dibaca dari env sekali, tidak pernah dicatat ke log, dan tidak
   pernah dikembalikan lewat HTTP dalam bentuk apa pun.
4. Policy engine adalah satu-satunya yang memutuskan. Daemon tidak punya
   jalur pintas untuk menandatanganinya.

Yang BISA diuji tanpa jaringan: decide + sign + verifikasi tanda tangan.
Yang TIDAK bisa diuji di sini: injeksi ke browser sungguhan dan broadcast.
"""
import json
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from signing_policy import ALLOW, DENY, ESCALATE, Policy, decide  # noqa: E402

# ---------------------------------------------------------------------------
# Log audit.
#
# Dibungkus supaya kegagalan logging TIDAK PERNAH menjatuhkan daemon. Daemon
# yang mati berarti extension tidak bisa signing, dan itu jauh lebih buruk
# daripada kehilangan satu baris log.
# ---------------------------------------------------------------------------
try:
    import audit_log as _audit_mod
except Exception:  # pragma: no cover
    _audit_mod = None


def _audit(event: str, name: str, **kw) -> None:
    if _audit_mod is None:
        return
    try:
        _audit_mod.write(component=event, event=name, **kw)
    except Exception:
        pass


try:
    from eth_account import Account
    from eth_account.messages import encode_defunct
except ImportError:  # pragma: no cover
    print("Butuh eth-account:  pip install eth-account", file=sys.stderr)
    raise


# ============================================================================
# Kesalahan yang punya arti khusus bagi extension
# ============================================================================
class UserRejected(Exception):
    """ESCALATE/DENY — extension harus menolaknya seperti MetaMask menolak."""


class DaemonError(Exception):
    """Kesalahan teknis: nonce tidak ada, RPC mati, dsb."""


# Method yang benar-benar diimplementasikan daemon. Apa pun di luar ini
# ditolak SEBELUM bertanya ke policy engine — daemon tidak boleh meneruskan
# method yang tidak ia mengerti, karena policy engine juga tidak mengerti
# dan hanya akan menjawab ESCALATE dengan alasan yang menyesatkan.
SUPPORTED_METHODS = {
    "eth_accounts", "eth_requestaccounts", "eth_coinbase",
    "eth_chainid", "net_version",
    "personal_sign", "eth_sign",
    "eth_sendtransaction", "send_transaction",
}


# ============================================================================
# Logika murni — bagian ini yang diuji
# ============================================================================
def to_hex(n: int) -> str:
    return hex(n)


def to_int(v) -> int:
    """EIP-1193 mengirim kuantitas sebagai string hex."""
    if v is None:
        return 0
    if isinstance(v, int):
        return v
    s = str(v).strip().lower()
    if s in ("", "0x"):
        return 0
    return int(s, 16) if s.startswith("0x") else int(s, 10)


def build_policy_request(method: str, params: list, chain_id: int,
                         origin: str) -> dict:
    """Terjemahkan request EIP-1193 ke bentuk yang dimengerti policy engine.

    Ini lapisan yang paling mudah salah: policy engine mengharapkan
    chain_id int dan value wei, sedangkan provider mengirim string hex.
    Salah terjemah = transaksi bernilai terbaca nol.
    """
    req = {"method": method, "chain_id": chain_id, "origin": origin or ""}
    m = method.lower()

    if m in ("personal_sign", "eth_sign"):
        # params: [message, address]
        req["data"] = params[0] if params else None
    elif m in ("eth_signtypeddata_v4", "eth_signtypeddata"):
        raw = params[1] if len(params) > 1 else None
        req["data"] = raw if isinstance(raw, str) else json.dumps(raw)
    elif m in ("eth_sendtransaction", "send_transaction"):
        tx = params[0] if params else {}
        req["to"] = tx.get("to")
        req["value"] = tx.get("value")
        req["data"] = tx.get("data") or "0x"
    return req


def handle_sign(method: str, params: list, *, acct, chain_id: int,
                origin: str, policy: Policy, today_count: int = 0,
                rpc=None) -> dict:
    """Tangani satu request signing. Mengembalikan dict hasil EIP-1193.

    Melempar UserRejected kalau policy tidak mengizinkan.
    """
    m = method.lower()

    if m not in SUPPORTED_METHODS:
        raise DaemonError(
            f"method '{method}' tidak ditangani daemon ini. Yang didukung: "
            f"{', '.join(sorted(SUPPORTED_METHODS))}")

    # ---- method yang tidak butuh keputusan kebijakan ----------------------
    if m in ("eth_accounts", "eth_requestaccounts", "eth_coinbase"):
        return {"result": [acct.address]}
    if m == "eth_chainid":
        return {"result": to_hex(chain_id)}
    if m == "net_version":
        return {"result": str(chain_id)}

    # ---- sisanya harus lewat policy engine --------------------------------
    preq = build_policy_request(method, params, chain_id, origin)
    d = decide(preq, policy=policy, today_count=today_count)

    if d.verdict != ALLOW:
        raise UserRejected(f"{d.verdict}: {d.reason} [rule={d.rule}]")

    if m in ("personal_sign", "eth_sign"):
        msg = params[0] if params else None
        if not isinstance(msg, str):
            raise DaemonError("personal_sign: pesan harus string hex atau teks")
        if msg.startswith("0x"):
            signable = encode_defunct(hexstr=msg)
        else:
            signable = encode_defunct(text=msg)
        signed = acct.sign_message(signable)
        return {"result": signed.signature.hex() if isinstance(signed.signature, bytes)
                else str(signed.signature), "rule": d.rule}

    if m in ("eth_sendtransaction", "send_transaction"):
        tx = dict(params[0] if params else {})
        tx.setdefault("chainId", chain_id)
        tx.setdefault("from", acct.address)
        tx["value"] = to_int(tx.get("value"))
        for k in ("gas", "maxFeePerGas", "maxPriorityFeePerGas", "gasPrice", "nonce"):
            if k in tx:
                tx[k] = to_int(tx[k])

        if "nonce" not in tx:
            if rpc is None:
                raise DaemonError(
                    "nonce tidak diberikan dan RPC tidak dikonfigurasi "
                    "(set AGENTDROP_RPC_URL)")
            tx["nonce"] = rpc.get_transaction_count(acct.address)

        # LocalAccount sudah memegang key-nya; argumen kedua di sini adalah
        # `blobs`, bukan key. Melewatkan key sebagai argumen kedua memicu
        # "Blob data is not supported for legacy transactions".
        signed = acct.sign_transaction(tx)
        raw = signed.raw_transaction if hasattr(signed, "raw_transaction") \
            else signed.rawTransaction
        out = {"result": "0x" + raw.hex(), "rule": d.rule,
               "tx_hash": "0x" + signed.hash.hex()}
        if rpc is not None:
            out["broadcast"] = rpc.send_raw_transaction("0x" + raw.hex())
        return out

    raise DaemonError(f"method '{method}' lolos allowlist tapi tidak tertangani")


# ============================================================================
# Lapisan HTTP — sengaja tipis
# ============================================================================
class Handler(BaseHTTPRequestHandler):
    server_version = "AgentDropSigner/1.0"

    def _send(self, code: int, body: dict) -> None:
        data = json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _authorized(self) -> bool:
        want = self.server.token
        got = self.headers.get("X-AgentDrop-Token", "")
        # Perbandingan panjang-konstan supaya tidak bocor lewat timing.
        import hmac
        return hmac.compare_digest(want.encode(), got.encode())

    def do_GET(self):  # noqa: N802
        if self.path == "/health":
            self._send(200, {"ok": True, "address": self.server.acct.address})
        else:
            self._send(404, {"error": "not found"})

    def do_POST(self):  # noqa: N802
        if not self._authorized():
            self._send(403, {"error": "token salah atau tidak ada"})
            return
        try:
            length = int(self.headers.get("Content-Length") or 0)
            payload = json.loads(self.rfile.read(length) or b"{}")
        except (ValueError, json.JSONDecodeError) as exc:
            self._send(400, {"error": f"payload tidak valid: {exc}"})
            return

        _m = payload.get("method", "")
        _origin = payload.get("origin", "")
        _chain = payload.get("chain_id") or self.server.chain_id
        try:
            out = handle_sign(
                _m,
                payload.get("params") or [],
                acct=self.server.acct,
                chain_id=_chain,
                origin=_origin,
                policy=self.server.policy,
                today_count=self.server.today_count(),
                rpc=self.server.rpc,
            )
        except UserRejected as exc:
            # 4001 adalah kode "user rejected" di EIP-1193.
            _audit("signing", "rejected", level="warn", tool=_m, ok=False,
                   msg=str(exc)[:300],
                   detail={"origin": _origin, "chain_id": _chain})
            self._send(200, {"rejected": True, "error": str(exc)})
        except DaemonError as exc:
            _audit("signing", "daemon-error", level="error", tool=_m, ok=False,
                   msg=str(exc)[:300],
                   detail={"origin": _origin, "chain_id": _chain})
            self._send(200, {"error": str(exc)})
        except Exception as exc:  # jaga-jaga: jangan bocorkan stack ke halaman
            _audit("signing", "internal-error", level="error", tool=_m, ok=False,
                   msg=f"{type(exc).__name__}: {exc}"[:300],
                   detail={"origin": _origin, "chain_id": _chain})
            self._send(500, {"error": f"kesalahan internal: {type(exc).__name__}"})
        else:
            # Keluaran signing TIDAK dicatat. Tanda tangan adalah kredensial;
            # yang berguna untuk audit adalah KEPUTUSANNYA, bukan hasilnya.
            _audit("signing", "signed", level="info", tool=_m, ok=True,
                   detail={"origin": _origin, "chain_id": _chain,
                           "result_keys": sorted(out.keys()) if isinstance(out, dict) else None})
            self._send(200, out)

    def log_message(self, fmt, *args):  # jangan spam, dan jangan bocorkan data
        sys.stderr.write(f"[signer] {self.address_string()} {fmt % args}\n")


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser(description="Daemon signing AgentDrop")
    ap.add_argument("--port", type=int, default=int(os.environ.get("AGENTDROP_SIGNER_PORT", "9721")))
    ap.add_argument("--chain-id", type=int,
                    default=int(os.environ.get("AGENTDROP_CHAIN_ID", "11155111")))
    ap.add_argument("--policy", default="config/hermes/signing-policy.yaml")
    args = ap.parse_args()

    key = os.environ.get("AGENTDROP_PRIVATE_KEY", "")
    key_file = os.environ.get("AGENTDROP_KEY_FILE", "")
    if not key and key_file:
        # .env.example melarang private key ditaruh di .env, dan aturan itu
        # benar: file itu ikut tersalin ke enam profil. Key ditaruh di file
        # tersendiri berizin 0600 yang sudah di-gitignore.
        kp = Path(key_file).expanduser()
        if not kp.exists():
            print(f"AGENTDROP_KEY_FILE menunjuk {kp} tapi filenya tidak ada.",
                  file=sys.stderr)
            return 2
        mode = kp.stat().st_mode & 0o777
        if mode & 0o077:
            print(f"PERINGATAN: {kp} berizin {oct(mode)} — seharusnya 600. "
                  f"Jalankan: chmod 600 {kp}", file=sys.stderr)
        key = kp.read_text().strip()
    if not key:
        print("Private key tidak ditemukan. Set AGENTDROP_KEY_FILE (disarankan) "
              "atau AGENTDROP_PRIVATE_KEY. Daemon menolak jalan tanpanya.",
              file=sys.stderr)
        return 2
    token = os.environ.get("AGENTDROP_SIGNER_TOKEN", "")
    if not token:
        print("AGENTDROP_SIGNER_TOKEN belum di-set. Daemon menolak jalan tanpa token.",
              file=sys.stderr)
        return 2

    acct = Account.from_key(key if key.startswith("0x") else "0x" + key)
    policy = Policy.from_yaml(Path(args.policy))

    srv = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    srv.acct = acct
    srv.token = token
    srv.chain_id = args.chain_id
    srv.policy = policy
    srv.rpc = None
    srv.today_count = lambda: 0

    print(f"[signer] mendengarkan 127.0.0.1:{args.port} "
          f"(chain {args.chain_id}, alamat {acct.address})", file=sys.stderr)
    print("[signer] PERHATIAN: private key ada di proses ini. Jangan expose port ini.",
          file=sys.stderr)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
