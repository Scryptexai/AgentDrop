#!/usr/bin/env python3
"""Test untuk tools/signing_policy.py — mesin keputusan signature.

Jalankan:  python3 tools/test_signing_policy.py
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from signing_policy import (  # noqa: E402
    ALLOW, DENY, ESCALATE, MAX_UINT256,
    SEL_APPROVE, SEL_PERMIT, SEL_SET_APPROVAL_FOR_ALL, SEL_TRANSFER,
    Policy, decide,
)

SEPOLIA = 11155111
MAINNET = 1


def word(x: int) -> str:
    return f"{x:064x}"


def calldata(sel: str, *words: int) -> str:
    return sel + "".join(word(w) for w in words)


def addr(n: int) -> int:
    """Bentuk alamat 20-byte dari angka kecil, supaya gampang dibaca."""
    return n


OWNER = 0x1111111111111111111111111111111111111111
SPENDER = 0x2222222222222222222222222222222222222222
TOKEN = 0x3333333333333333333333333333333333333333


def req(**kw):
    base = {"method": "send_transaction", "chain_id": SEPOLIA,
            "to": hex(TOKEN), "value_wei": 0, "data": "0x", "origin": "https://x.test"}
    base.update(kw)
    return base


class TestMessageSigning(unittest.TestCase):
    def test_testnet_personal_sign_allowed(self):
        d = decide(req(method="personal_sign"))
        self.assertEqual(d.verdict, ALLOW, d.reason)
        self.assertEqual(d.rule, "msg-testnet")

    def test_mainnet_login_sign_allowed(self):
        d = decide(req(method="personal_sign", chain_id=MAINNET))
        self.assertEqual(d.verdict, ALLOW, d.reason)

    def test_mainnet_typed_data_escalates(self):
        """EIP-712 bisa berisi permit = allowance terselubung."""
        d = decide(req(method="typed_data", chain_id=MAINNET))
        self.assertEqual(d.verdict, ESCALATE, d.reason)
        self.assertEqual(d.rule, "typed-data-mainnet")

    def test_testnet_typed_data_allowed(self):
        d = decide(req(method="typed_data"))
        self.assertEqual(d.verdict, ALLOW, d.reason)


class TestFailClosed(unittest.TestCase):
    def test_unknown_chain_escalates(self):
        d = decide(req(chain_id=424242))
        self.assertEqual(d.verdict, ESCALATE)
        self.assertEqual(d.rule, "unknown-chain")

    def test_missing_chain_escalates(self):
        d = decide(req(chain_id=None))
        self.assertEqual(d.verdict, ESCALATE)

    def test_missing_method_escalates(self):
        d = decide(req(method=""))
        self.assertEqual(d.verdict, ESCALATE)
        self.assertEqual(d.rule, "incomplete-input")

    def test_unknown_method_escalates(self):
        d = decide(req(method="eth_signTransaction"))
        self.assertEqual(d.verdict, ESCALATE)
        self.assertEqual(d.rule, "unknown-method")

    def test_rate_limit_escalates(self):
        d = decide(req(method="personal_sign"), today_count=40)
        self.assertEqual(d.verdict, ESCALATE)
        self.assertEqual(d.rule, "rate-limit")

    def test_rate_limit_boundary_still_allows(self):
        d = decide(req(method="personal_sign"), today_count=39)
        self.assertEqual(d.verdict, ALLOW, d.reason)

    def test_hex_string_chain_id_is_normalized(self):
        """eth_chainId mengirim '0xaa36a7', bukan 11155111."""
        d = decide(req(method="personal_sign", chain_id="0xaa36a7"))
        self.assertEqual(d.verdict, ALLOW,
                         f"chain id hex harus dinormalisasi ke Sepolia, dapat "
                         f"{d.verdict}/{d.rule}: {d.reason}")

    def test_hex_string_mainnet_chain_id(self):
        d = decide(req(method="typed_data", chain_id="0x1"))
        self.assertEqual(d.verdict, ESCALATE)
        self.assertEqual(d.rule, "typed-data-mainnet")

    def test_bool_chain_id_escalates(self):
        d = decide(req(method="personal_sign", chain_id=True))
        self.assertEqual(d.verdict, ESCALATE)
        self.assertEqual(d.rule, "unknown-chain")

    def test_garbage_chain_id_escalates(self):
        d = decide(req(method="personal_sign", chain_id="bukan-angka"))
        self.assertEqual(d.verdict, ESCALATE)
        self.assertEqual(d.rule, "unknown-chain")

    def test_int_to_does_not_crash(self):
        d = decide(req(to=12345))
        self.assertEqual(d.verdict, ESCALATE)
        self.assertEqual(d.rule, "malformed-input")

    def test_nonstring_method_does_not_crash(self):
        d = decide(req(method=12345))
        self.assertEqual(d.verdict, ESCALATE)
        self.assertEqual(d.rule, "incomplete-input")

    def test_truncated_calldata_fails_closed(self):
        d = decide(req(data="0x095ea7b3" + "22" * 32))
        self.assertEqual(d.verdict, ESCALATE, d.reason)
        self.assertEqual(d.rule, "unlimited-allowance")



class TestDenylist(unittest.TestCase):
    def test_denylisted_to_is_denied(self):
        p = Policy(spender_denylist=[hex(SPENDER)])
        d = decide(req(to=hex(SPENDER)), policy=p)
        self.assertEqual(d.verdict, DENY)
        self.assertEqual(d.rule, "spender-denylist")

    def test_denylist_is_case_insensitive(self):
        p = Policy(spender_denylist=[hex(SPENDER).upper()])
        d = decide(req(to=hex(SPENDER)), policy=p)
        self.assertEqual(d.verdict, DENY)


class TestAllowance(unittest.TestCase):
    def test_testnet_limited_approve_allowed(self):
        data = calldata(SEL_APPROVE, SPENDER, 100 * 10**18)
        d = decide(req(data=data))
        self.assertEqual(d.verdict, ALLOW, d.reason)

    def test_unlimited_approve_always_escalates(self):
        data = calldata(SEL_APPROVE, SPENDER, MAX_UINT256)
        d = decide(req(data=data))
        self.assertEqual(d.verdict, ESCALATE, d.reason)
        self.assertEqual(d.rule, "unlimited-allowance")

    def test_unlimited_escalates_even_on_testnet(self):
        data = calldata(SEL_APPROVE, SPENDER, MAX_UINT256)
        d = decide(req(data=data, chain_id=SEPOLIA))
        self.assertEqual(d.verdict, ESCALATE, d.rule)

    def test_set_approval_for_all_escalates(self):
        data = calldata(SEL_SET_APPROVAL_FOR_ALL, SPENDER, 1)
        d = decide(req(data=data))
        self.assertEqual(d.verdict, ESCALATE)
        self.assertEqual(d.rule, "unlimited-allowance")

    def test_mainnet_limited_approve_escalates_by_default(self):
        data = calldata(SEL_APPROVE, SPENDER, 100 * 10**18)
        d = decide(req(data=data, chain_id=MAINNET))
        self.assertEqual(d.verdict, ESCALATE)
        self.assertEqual(d.rule, "allowance-policy")

    def test_above_soft_cap_escalates(self):
        data = calldata(SEL_APPROVE, SPENDER, 10_001 * 10**18)
        d = decide(req(data=data))
        self.assertEqual(d.verdict, ESCALATE)


class TestPermit(unittest.TestCase):
    """permit(owner,spender,value,deadline,v,r,s) — value adalah kata KE-3.

    Bug yang diuji di sini: _first_uint_arg membaca kata pertama, yaitu alamat
    owner. Jadi amount yang dinilai bukan value permit-nya.
    """

    def test_permit_small_value_on_testnet_should_allow(self):
        data = calldata(SEL_PERMIT, OWNER, SPENDER, 50 * 10**18, 9999999999, 27, 1, 2)
        d = decide(req(data=data))
        self.assertEqual(d.verdict, ALLOW,
                         f"permit bernilai kecil di testnet harus ALLOW, dapat "
                         f"{d.verdict}/{d.rule}: {d.reason}")

    def test_permit_unlimited_value_escalates(self):
        data = calldata(SEL_PERMIT, OWNER, SPENDER, MAX_UINT256, 9999999999, 27, 1, 2)
        d = decide(req(data=data))
        self.assertEqual(d.verdict, ESCALATE, d.reason)
        self.assertEqual(d.rule, "unlimited-allowance")

    def test_permit_above_soft_cap_escalates(self):
        data = calldata(SEL_PERMIT, OWNER, SPENDER, 50_000 * 10**18, 9999999999, 27, 1, 2)
        d = decide(req(data=data))
        self.assertEqual(d.verdict, ESCALATE, d.reason)


class TestValue(unittest.TestCase):
    def test_testnet_value_tx_allowed(self):
        d = decide(req(value_wei=10**18))
        self.assertEqual(d.verdict, ALLOW, d.reason)

    def test_mainnet_value_tx_escalates_by_default(self):
        d = decide(req(value_wei=10**18, chain_id=MAINNET))
        self.assertEqual(d.verdict, ESCALATE)
        self.assertEqual(d.rule, "value-mainnet")

    def test_mainnet_value_within_explicit_cap_allowed(self):
        p = Policy(mainnet_max_auto_value_wei=2 * 10**18)
        d = decide(req(value_wei=10**18, chain_id=MAINNET), policy=p)
        self.assertEqual(d.verdict, ALLOW, d.reason)

    def test_mainnet_zero_value_tx_escalates_by_default(self):
        d = decide(req(data=calldata(SEL_TRANSFER, SPENDER, 1), chain_id=MAINNET))
        self.assertEqual(d.verdict, ESCALATE)
        self.assertEqual(d.rule, "zero-policy")

    def test_testnet_zero_value_tx_allowed(self):
        d = decide(req(data=calldata(SEL_TRANSFER, SPENDER, 1)))
        self.assertEqual(d.verdict, ALLOW, d.reason)



class TestRealEip1193MethodNames(unittest.TestCase):
    """Nama method harus yang ASLI dari provider, bukan snake_case.

    Celah inilah yang menyembunyikan bug lower(): test sebelumnya menulis
    method="send_transaction", yang kebetulan selamat dari .lower(), jadi
    "eth_sendTransaction" yang TIDAK PERNAH cocok tidak pernah terdeteksi.
    """

    def test_eth_sendTransaction_recognized_on_testnet(self):
        data = calldata(SEL_APPROVE, SPENDER, 100 * 10**18)
        d = decide({"method": "eth_sendTransaction", "chain_id": SEPOLIA,
                    "to": hex(TOKEN), "value": "0x0", "data": data})
        self.assertEqual(d.verdict, ALLOW,
                         f"eth_sendTransaction harus dikenali, dapat "
                         f"{d.verdict}/{d.rule}: {d.reason}")

    def test_eth_sendTransaction_unlimited_still_escalates(self):
        data = calldata(SEL_APPROVE, SPENDER, MAX_UINT256)
        d = decide({"method": "eth_sendTransaction", "chain_id": SEPOLIA,
                    "to": hex(TOKEN), "value": "0x0", "data": data})
        self.assertEqual(d.verdict, ESCALATE, d.reason)
        self.assertEqual(d.rule, "unlimited-allowance")

    def test_eth_signTypedData_v4_mainnet_escalates(self):
        d = decide({"method": "eth_signTypedData_v4", "chain_id": MAINNET})
        self.assertEqual(d.verdict, ESCALATE, d.reason)
        self.assertEqual(d.rule, "typed-data-mainnet")

    def test_eth_signTypedData_v4_testnet_allowed(self):
        d = decide({"method": "eth_signTypedData_v4", "chain_id": SEPOLIA})
        self.assertEqual(d.verdict, ALLOW, d.reason)

    def test_value_as_hex_string_treated_as_zero(self):
        """Provider mengirim value sebagai '0x0', bukan int 0."""
        d = decide({"method": "eth_sendTransaction", "chain_id": SEPOLIA,
                    "to": hex(TOKEN), "value": "0x0",
                    "data": calldata(SEL_TRANSFER, SPENDER, 1)})
        self.assertNotEqual(d.rule, "malformed-input", d.reason)

    def test_every_message_method_is_lowercase_comparable(self):
        """Jaga-jaga: tidak boleh ada pembanding berhuruf kapital lagi."""
        import signing_policy as sp
        for name in sp.MESSAGE_METHODS | sp.TX_METHODS | sp.TYPED_DATA_METHODS:
            self.assertEqual(name, name.lower(),
                             f"{name!r} mengandung huruf kapital — tidak akan pernah cocok")



class TestValueNormalization(unittest.TestCase):
    """Klasifikasi "ada nilai / tanpa nilai" adalah keputusan keamanan."""

    def test_hex_value_string_is_read_as_value(self):
        """0xde0b6b3a7640000 = 1 ETH. Harus dibaca, bukan dianggap 0."""
        d = decide({"method": "eth_sendTransaction", "chain_id": MAINNET,
                    "to": hex(TOKEN), "value": "0xde0b6b3a7640000", "data": "0x"})
        self.assertEqual(d.rule, "value-mainnet",
                         f"1 ETH di mainnet harus masuk kelas value, dapat {d.rule}")
        self.assertEqual(d.verdict, ESCALATE)

    def test_hex_value_on_testnet_allowed(self):
        d = decide({"method": "eth_sendTransaction", "chain_id": SEPOLIA,
                    "to": hex(TOKEN), "value": "0xde0b6b3a7640000", "data": "0x"})
        self.assertEqual(d.rule, "value-testnet", d.reason)
        self.assertEqual(d.verdict, ALLOW)

    def test_zero_hex_string_is_zero_value(self):
        d = decide({"method": "eth_sendTransaction", "chain_id": SEPOLIA,
                    "to": hex(TOKEN), "value": "0x0",
                    "data": calldata(SEL_TRANSFER, SPENDER, 1)})
        self.assertEqual(d.rule, "zero-testnet", d.reason)

    def test_empty_value_is_zero(self):
        d = decide({"method": "eth_sendTransaction", "chain_id": SEPOLIA,
                    "to": hex(TOKEN), "value": "0x",
                    "data": calldata(SEL_TRANSFER, SPENDER, 1)})
        self.assertEqual(d.rule, "zero-testnet", d.reason)

    def test_garbage_value_fails_closed(self):
        d = decide({"method": "eth_sendTransaction", "chain_id": SEPOLIA,
                    "to": hex(TOKEN), "value": "banyak", "data": "0x"})
        self.assertEqual(d.verdict, ESCALATE)
        self.assertEqual(d.rule, "malformed-input")

    def test_value_wei_overrides_value(self):
        d = decide({"method": "eth_sendTransaction", "chain_id": MAINNET,
                    "to": hex(TOKEN), "value": "0x0", "value_wei": 10**18,
                    "data": "0x"})
        self.assertEqual(d.rule, "value-mainnet", d.reason)


class TestPolicyLoading(unittest.TestCase):
    def test_from_yaml_ignores_unknown_keys(self):
        import tempfile
        with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False) as f:
            f.write("mainnet_auto_approve_zero_value_tx: true\nkey_ngawur: 1\n")
            path = f.name
        p = Policy.from_yaml(Path(path))
        self.assertTrue(p.mainnet_auto_approve_zero_value_tx)

    def test_policy_override_enables_mainnet_zero_value(self):
        p = Policy(mainnet_auto_approve_zero_value_tx=True)
        d = decide(req(data=calldata(SEL_TRANSFER, SPENDER, 1), chain_id=MAINNET), policy=p)
        self.assertEqual(d.verdict, ALLOW, d.reason)


if __name__ == "__main__":
    unittest.main(verbosity=2)
