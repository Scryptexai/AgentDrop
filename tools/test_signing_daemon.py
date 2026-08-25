#!/usr/bin/env python3
"""Test tools/signing_daemon.py — lapisan yang memanggil policy engine.

Jalankan:  python3 tools/test_signing_daemon.py
"""
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from eth_account import Account  # noqa: E402
from eth_account.messages import encode_defunct  # noqa: E402

from signing_daemon import (  # noqa: E402
    DaemonError, UserRejected, build_policy_request, handle_sign, to_int, to_hex,
)
from signing_policy import Policy  # noqa: E402

TEST_KEY = "0x" + "11" * 32
ACCT = Account.from_key(TEST_KEY)
SEPOLIA = 11155111
MAINNET = 1
SPENDER = "0x" + "22" * 20
TOKEN = "0x" + "33" * 20


def approve_data(amount: int) -> str:
    return "0x095ea7b3" + f"{int(SPENDER, 16):064x}" + f"{amount:064x}"


def strict() -> Policy:
    return Policy()


def autonomous() -> Policy:
    return Policy(mainnet_auto_approve_zero_value_tx=True,
                  mainnet_auto_approve_allowance=True,
                  auto_approve_unlimited_allowance=True,
                  mainnet_max_auto_value_wei=10**19)


class TestHelpers(unittest.TestCase):
    def test_to_int_hex(self):
        self.assertEqual(to_int("0xde0b6b3a7640000"), 10**18)

    def test_to_int_empty(self):
        self.assertEqual(to_int("0x"), 0)
        self.assertEqual(to_int(None), 0)
        self.assertEqual(to_int(""), 0)

    def test_to_int_decimal_string(self):
        self.assertEqual(to_int("1000"), 1000)

    def test_to_hex(self):
        self.assertEqual(to_hex(11155111), "0xaa36a7")


class TestBuildPolicyRequest(unittest.TestCase):
    def test_sendtransaction_maps_value_as_hex(self):
        """Bug #5 dulu: value hex terbaca 0. Lapisan ini yang mencegahnya."""
        r = build_policy_request("eth_sendTransaction",
                                 [{"to": TOKEN, "value": "0xde0b6b3a7640000",
                                   "data": "0x"}], MAINNET, "https://x.test")
        self.assertEqual(r["value"], "0xde0b6b3a7640000")
        self.assertEqual(r["to"], TOKEN)
        self.assertEqual(r["chain_id"], MAINNET)

    def test_sendtransaction_defaults_data(self):
        r = build_policy_request("eth_sendTransaction", [{"to": TOKEN}], SEPOLIA, "")
        self.assertEqual(r["data"], "0x")

    def test_personal_sign_carries_message(self):
        r = build_policy_request("personal_sign", ["0xdeadbeef", ACCT.address],
                                 SEPOLIA, "https://x.test")
        self.assertEqual(r["data"], "0xdeadbeef")

    def test_origin_is_passed_through(self):
        r = build_policy_request("personal_sign", ["hi"], SEPOLIA, "https://galxe.com")
        self.assertEqual(r["origin"], "https://galxe.com")


class TestNoPolicyNeeded(unittest.TestCase):
    def test_accounts(self):
        out = handle_sign("eth_accounts", [], acct=ACCT, chain_id=SEPOLIA,
                          origin="", policy=strict())
        self.assertEqual(out["result"], [ACCT.address])

    def test_chain_id(self):
        out = handle_sign("eth_chainId", [], acct=ACCT, chain_id=SEPOLIA,
                          origin="", policy=strict())
        self.assertEqual(out["result"], "0xaa36a7")

    def test_net_version(self):
        out = handle_sign("net_version", [], acct=ACCT, chain_id=MAINNET,
                          origin="", policy=strict())
        self.assertEqual(out["result"], "1")


class TestPersonalSign(unittest.TestCase):
    def test_text_message_signs_and_verifies(self):
        out = handle_sign("personal_sign", ["Login ke Galxe"], acct=ACCT,
                          chain_id=SEPOLIA, origin="https://galxe.com",
                          policy=strict())
        sig = out["result"]
        recovered = Account.recover_message(encode_defunct(text="Login ke Galxe"),
                                            signature=sig)
        self.assertEqual(recovered, ACCT.address)

    def test_hex_message_signs_and_verifies(self):
        out = handle_sign("personal_sign", ["0xdeadbeef"], acct=ACCT,
                          chain_id=SEPOLIA, origin="", policy=strict())
        recovered = Account.recover_message(encode_defunct(hexstr="0xdeadbeef"),
                                            signature=out["result"])
        self.assertEqual(recovered, ACCT.address)

    def test_mainnet_login_allowed(self):
        out = handle_sign("personal_sign", ["siwe"], acct=ACCT, chain_id=MAINNET,
                          origin="", policy=strict())
        self.assertIn("result", out)


class TestSendTransaction(unittest.TestCase):
    def _tx(self, **kw):
        base = {"to": TOKEN, "value": "0x0", "data": "0x",
                "nonce": 0, "gas": 21000, "gasPrice": 10**9}
        base.update(kw)
        return base

    def test_testnet_limited_approve_signs(self):
        out = handle_sign("eth_sendTransaction",
                          [self._tx(data=approve_data(100 * 10**18))],
                          acct=ACCT, chain_id=SEPOLIA, origin="",
                          policy=strict())
        self.assertTrue(out["result"].startswith("0x"))
        self.assertTrue(out["tx_hash"].startswith("0x"))

    def test_unlimited_approve_rejected_under_strict_policy(self):
        with self.assertRaises(UserRejected):
            handle_sign("eth_sendTransaction",
                        [self._tx(data=approve_data(2**256 - 1))],
                        acct=ACCT, chain_id=SEPOLIA, origin="", policy=strict())

    def test_unlimited_approve_signs_under_autonomous_policy(self):
        out = handle_sign("eth_sendTransaction",
                          [self._tx(data=approve_data(2**256 - 1))],
                          acct=ACCT, chain_id=MAINNET, origin="",
                          policy=autonomous())
        self.assertEqual(out["rule"], "unlimited-allowance-auto")

    def test_denylist_beats_autonomous_policy(self):
        p = autonomous()
        p.spender_denylist = [TOKEN]
        with self.assertRaises(UserRejected):
            handle_sign("eth_sendTransaction", [self._tx()], acct=ACCT,
                        chain_id=MAINNET, origin="", policy=p)

    def test_mainnet_big_value_rejected(self):
        with self.assertRaises(UserRejected):
            handle_sign("eth_sendTransaction",
                        [self._tx(value="0x56bc75e2d631000000")],  # 100 ETH
                        acct=ACCT, chain_id=MAINNET, origin="",
                        policy=autonomous())

    def test_missing_nonce_without_rpc_raises(self):
        tx = self._tx()
        del tx["nonce"]
        with self.assertRaises(DaemonError):
            handle_sign("eth_sendTransaction", [tx], acct=ACCT,
                        chain_id=SEPOLIA, origin="", policy=strict())

    def test_hex_gas_and_value_are_normalized(self):
        tx = {"to": TOKEN, "value": "0xde0b6b3a7640000", "data": "0x",
              "nonce": "0x5", "gas": "0x5208", "gasPrice": "0x3b9aca00"}
        out = handle_sign("eth_sendTransaction", [tx], acct=ACCT,
                          chain_id=SEPOLIA, origin="", policy=strict())
        self.assertTrue(out["result"].startswith("0x"))


class TestUnknownMethods(unittest.TestCase):
    def test_unhandled_method_raises(self):
        with self.assertRaises(DaemonError):
            handle_sign("wallet_addEthereumChain", [], acct=ACCT,
                        chain_id=SEPOLIA, origin="", policy=strict())

    def test_typed_data_not_implemented(self):
        with self.assertRaises(DaemonError):
            handle_sign("eth_signTypedData_v4",
                        [ACCT.address, json.dumps({"types": {}})],
                        acct=ACCT, chain_id=SEPOLIA, origin="", policy=strict())


class FakeRpc:
    def __init__(self):
        self.broadcast = []

    def get_transaction_count(self, addr):
        return 7

    def send_raw_transaction(self, raw):
        self.broadcast.append(raw)
        return "0x" + "ab" * 32


class TestRpcIntegration(unittest.TestCase):
    def test_nonce_fetched_from_rpc(self):
        rpc = FakeRpc()
        out = handle_sign("eth_sendTransaction",
                          [{"to": TOKEN, "value": "0x0", "data": "0x",
                            "gas": 21000, "gasPrice": 10**9}],
                          acct=ACCT, chain_id=SEPOLIA, origin="",
                          policy=strict(), rpc=rpc)
        self.assertEqual(len(rpc.broadcast), 1)
        self.assertTrue(out["tx_hash"].startswith("0x"))


class TestRateLimit(unittest.TestCase):
    def test_rate_limit_rejects(self):
        with self.assertRaises(UserRejected):
            handle_sign("personal_sign", ["hi"], acct=ACCT, chain_id=SEPOLIA,
                        origin="", policy=strict(), today_count=40)


if __name__ == "__main__":
    unittest.main(verbosity=2)
