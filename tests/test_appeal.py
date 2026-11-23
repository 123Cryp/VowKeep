import json
import unittest

from tests._bootstrap import (
    CLOCK, GEN, KEEPER, MAKER, STRANGER, Model, PaymentRejected, Web, answer, appeal, assert_invariants, check, create,
    expect_user_error, finalize, make_contract, pending, set_caller, vow,
)


class AppealTests(unittest.TestCase):
    def setUp(self):
        self.c = make_contract()
        self.vid = create(self.c, stake_gen=20, target=10)
        self.first = check(self.c, self.vid, 4)

    def test_bond_is_ten_percent_rounded_up_to_whole_gen(self):
        preview = json.loads(self.c.preview_appeal(self.vid))
        self.assertEqual(int(preview["bond_wei"]), 2 * GEN)
        self.assertEqual(self.c._bond_for(5 * GEN), GEN)
        self.assertEqual(self.c._bond_for(11 * GEN), 2 * GEN)
        self.assertEqual(self.c._bond_for(GEN), GEN)

    def test_upheld_appeal_refunds_bond_and_pays_new_share(self):
        appeal(self.c, self.vid)
        self.assertEqual(vow(self.c, self.vid)["status"], "APPEALED")
        assert_invariants(self, self.c)
        model = Model(answer(8))
        out = finalize(self.c, self.vid, model=model)
        self.assertIn("appeal review", model.prompts[0])
        self.assertIn("see entries on 2026-11-22", model.prompts[0])
        self.assertEqual(out["status"], "SETTLED")
        self.assertEqual(out["count"], 8)
        self.assertEqual(pending(self.c, MAKER), 16 * GEN + 2 * GEN)
        self.assertEqual(int(self.c.pool_balance), 4 * GEN)
        v = vow(self.c, self.vid)
        self.assertTrue(v["appeal"]["upheld"])
        self.assertEqual(v["final"]["source"], "appeal")
        assert_invariants(self, self.c)

    def test_appeal_to_met_returns_full_stake(self):
        appeal(self.c, self.vid)
        finalize(self.c, self.vid, 10)
        self.assertEqual(pending(self.c, MAKER), 22 * GEN)
        self.assertEqual(int(self.c.pool_balance), 0)
        assert_invariants(self, self.c)

    def test_rejected_appeal_keeps_first_verdict_and_forfeits_bond(self):
        appeal(self.c, self.vid)
        finalize(self.c, self.vid, 2)
        v = vow(self.c, self.vid)
        self.assertFalse(v["appeal"]["upheld"])
        self.assertEqual(v["final"]["count"], 4)
        self.assertEqual(pending(self.c, MAKER), 8 * GEN)
        self.assertEqual(int(self.c.pool_balance), 12 * GEN + 2 * GEN)
        self.assertEqual(int(self.c.bonds_forfeited_total), 2 * GEN)
        assert_invariants(self, self.c)

    def test_only_maker_once_and_inside_window(self):
        with self.assertRaises(PaymentRejected) as ctx:
            appeal(self.c, self.vid, who=STRANGER, value=2 * GEN)
        self.assertIn("maker", str(ctx.exception))
        with self.assertRaises(PaymentRejected):
            appeal(self.c, self.vid, value=GEN)
        with self.assertRaises(PaymentRejected):
            appeal(self.c, self.vid, note="")
        appeal(self.c, self.vid)
        with self.assertRaises(PaymentRejected) as ctx:
            appeal(self.c, self.vid, value=2 * GEN)
        self.assertIn("checked", str(ctx.exception))
        assert_invariants(self, self.c)

    def test_window_closes(self):
        CLOCK.set_epoch(self.first["appeal_until"])
        with self.assertRaises(PaymentRejected) as ctx:
            appeal(self.c, self.vid, value=2 * GEN)
        self.assertIn("closed", str(ctx.exception))

    def test_overpaid_bond_is_credited_back(self):
        out = appeal(self.c, self.vid, value=5 * GEN)
        self.assertEqual(int(out["excess_credited_wei"]), 3 * GEN)
        self.assertEqual(pending(self.c, MAKER), 3 * GEN)
        assert_invariants(self, self.c)

    def test_met_vow_cannot_be_appealed(self):
        vid = create(self.c, stake_gen=5)
        check(self.c, vid, 10)
        with self.assertRaises(PaymentRejected):
            appeal(self.c, vid, value=GEN)

    def test_finalize_rules_for_checked_vow(self):
        msg = expect_user_error(self, finalize, self.c, self.vid, caller=STRANGER)
        self.assertIn("appeal window", msg)
        out = finalize(self.c, self.vid, caller=MAKER)
        self.assertEqual(out["status"], "SETTLED")
        msg = expect_user_error(self, finalize, self.c, self.vid)
        self.assertIn("SETTLED", msg)

    def test_finalize_active_vow_fails(self):
        vid = create(self.c)
        msg = expect_user_error(self, finalize, self.c, vid)
        self.assertIn("ACTIVE", msg)

    def test_unreachable_appeal_review_waits_then_first_verdict_stands(self):
        appeal(self.c, self.vid)
        msg = expect_user_error(self, finalize, self.c, self.vid, 9, web=Web(RuntimeError("down")))
        self.assertIn("Nothing was recorded", msg)
        self.assertEqual(vow(self.c, self.vid)["status"], "APPEALED")
        CLOCK.advance(self.c.APPEAL_TIMEOUT_SECONDS)
        finalize(self.c, self.vid, 9, web=Web(RuntimeError("down")))
        v = vow(self.c, self.vid)
        self.assertEqual(v["final"]["count"], 4)
        self.assertFalse(v["appeal"]["upheld"])
        assert_invariants(self, self.c)

    def test_anyone_can_finalize_an_appeal(self):
        appeal(self.c, self.vid)
        set_caller(KEEPER)
        out = finalize(self.c, self.vid, 6, caller=STRANGER)
        self.assertEqual(out["status"], "SETTLED")


if __name__ == "__main__":
    unittest.main()
