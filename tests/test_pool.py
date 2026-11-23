import json
import random
import unittest

from tests._bootstrap import (
    CHARITY, CLOCK, GEN, KEEPER, MAKER, MAKER_2, OWNER, STRANGER, LOG_URL, Model, PaymentRejected, Web, answer, appeal,
    assert_invariants, call_payable, check, create, expect_user_error, finalize, gl, make_contract, pending, set_caller, vow,
)


class PoolTests(unittest.TestCase):
    def setUp(self):
        self.c = make_contract()

    def _missed(self, stake=10):
        vid = create(self.c, stake_gen=stake)
        out = check(self.c, vid, 0)
        CLOCK.set_epoch(out["appeal_until"])
        finalize(self.c, vid)
        return vid

    def test_owner_sets_beneficiary(self):
        set_caller(STRANGER)
        msg = expect_user_error(self, self.c.set_beneficiary, CHARITY, "Open source fund")
        self.assertIn("owner", msg)
        set_caller(OWNER)
        expect_user_error(self, self.c.set_beneficiary, "0x123", "x")
        expect_user_error(self, self.c.set_beneficiary, "0x" + "0" * 40, "zero")
        expect_user_error(self, self.c.set_beneficiary, CHARITY, "")
        self.c.set_beneficiary(CHARITY, "Open source fund")
        pool = json.loads(self.c.get_pool())
        self.assertEqual(pool["beneficiary"], CHARITY)
        self.assertEqual(pool["beneficiary_label"], "Open source fund")

    def test_distribution_needs_beneficiary_and_funds(self):
        set_caller(KEEPER)
        self.assertIn("beneficiary", expect_user_error(self, self.c.distribute_pool))
        set_caller(OWNER)
        self.c.set_beneficiary(CHARITY, "Fund")
        set_caller(KEEPER)
        self.assertIn("empty", expect_user_error(self, self.c.distribute_pool))

    def test_distribute_and_withdraw_to_beneficiary(self):
        self._missed(10)
        set_caller(OWNER)
        self.c.set_beneficiary(CHARITY, "Fund")
        set_caller(STRANGER)
        out = json.loads(self.c.distribute_pool())
        self.assertEqual(int(out["amount_wei"]), 10 * GEN)
        self.assertEqual(int(self.c.pool_balance), 0)
        self.assertEqual(pending(self.c, CHARITY), 10 * GEN)
        assert_invariants(self, self.c)
        set_caller(KEEPER)
        self.c.push_payment(CHARITY)
        self.assertEqual(gl.evm.transfers[-1]["to"].lower(), CHARITY)
        self.assertEqual(int(gl.evm.transfers[-1]["value"]), 10 * GEN)
        self.assertEqual(pending(self.c, CHARITY), 0)
        assert_invariants(self, self.c)
        pool = json.loads(self.c.get_pool())
        self.assertEqual(int(pool["distributed_total"]), 10 * GEN)
        self.assertEqual(pool["distributions"], 1)
        self.assertGreater(pool["last_distribution_epoch"], 0)

    def test_withdraw_rules(self):
        set_caller(MAKER)
        self.assertIn("no withdrawable", expect_user_error(self, self.c.withdraw))
        expect_user_error(self, self.c.push_payment, "nope")
        vid = create(self.c, stake_gen=3)
        check(self.c, vid, 10)
        set_caller(MAKER)
        self.c.withdraw()
        self.assertEqual(int(gl.evm.transfers[-1]["value"]), 3 * GEN)
        assert_invariants(self, self.c)

    def test_ownership(self):
        set_caller(STRANGER)
        expect_user_error(self, self.c.claim_ownership)
        expect_user_error(self, self.c.transfer_ownership, STRANGER)
        set_caller(OWNER)
        expect_user_error(self, self.c.transfer_ownership, "bad")
        self.c.transfer_ownership(STRANGER)
        self.assertEqual(json.loads(self.c.get_config())["owner"], STRANGER)
        set_caller(STRANGER)
        self.c.set_beneficiary(CHARITY, "Fund")

    def test_claim_ownership_when_unset(self):
        self.c.settings["owner"] = ""
        set_caller(STRANGER)
        self.c.claim_ownership()
        self.assertEqual(json.loads(self.c.get_config())["owner"], STRANGER)


class AccountingFuzzTests(unittest.TestCase):
    def test_random_lifecycles_keep_books_balanced(self):
        rng = random.Random(20261120)
        c = make_contract()
        set_caller(OWNER)
        c.set_beneficiary(CHARITY, "Fund")
        makers = [MAKER, MAKER_2, "0x" + "f1" * 20]
        open_ids = []
        for step in range(220):
            action = rng.random()
            if action < 0.35 or not open_ids:
                target = rng.randint(1, 12)
                try:
                    vid = create(c, who=rng.choice(makers), stake_gen=1, target=target, goal_type="LOG_ENTRIES",
                                 url=LOG_URL, value=rng.randint(1, 30) * GEN + rng.randint(0, 999))
                    open_ids.append(vid)
                except PaymentRejected:
                    pass
            else:
                vid = rng.choice(open_ids)
                v = vow(c, vid)
                target = int(v["target"])
                if v["status"] == "ACTIVE":
                    check(c, vid, rng.randint(0, target + 2))
                elif v["status"] == "CHECKED":
                    appealed = False
                    if rng.random() < 0.5:
                        set_caller(v["maker"])
                        bond = int(json.loads(c.preview_appeal(vid))["bond_wei"])
                        try:
                            call_payable(c, "appeal", bond + rng.randint(0, 2) * GEN, vid, "look again")
                            appealed = True
                        except PaymentRejected:
                            pass
                    if not appealed:
                        finalize(c, vid, caller=v["maker"])
                elif v["status"] == "APPEALED":
                    finalize(c, vid, rng.randint(0, target))
                else:
                    open_ids.remove(vid)
            if rng.random() < 0.1 and int(c.pool_balance) > 0:
                set_caller(KEEPER)
                c.distribute_pool()
            if rng.random() < 0.15:
                who = rng.choice(makers + [CHARITY])
                if pending(c, who) > 0:
                    set_caller(KEEPER)
                    c.push_payment(who)
            CLOCK.advance(rng.randint(0, 90))
            assert_invariants(self, c)
        stats = json.loads(c.get_stats())
        self.assertGreater(stats["settled"], 10)
        self.assertGreater(stats["appeals"], 3)


if __name__ == "__main__":
    unittest.main()
