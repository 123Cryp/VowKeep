import json
import unittest

from tests._bootstrap import (
    CHARITY, CLOCK, GEN, KEEPER, LOG_URL, MAKER, MAKER_2, OWNER, SANDBOX, appeal, check, create, expect_user_error,
    finalize, make_contract, set_caller, sync_balance, m,
)


class ViewTests(unittest.TestCase):
    def setUp(self):
        self.c = make_contract()

    def test_config(self):
        cfg = json.loads(self.c.get_config())
        self.assertEqual(cfg["mode"], "sandbox" if SANDBOX else "production")
        self.assertEqual(cfg["owner"], OWNER)
        self.assertEqual(cfg["beneficiary"], "")
        self.assertEqual(int(cfg["min_stake_wei"]), GEN)
        self.assertEqual(cfg["appeal_bond_bps"], 1000)
        self.assertEqual(cfg["min_duration_minutes"], 1 if SANDBOX else 1440)
        for key in ("version", "deployed_epoch", "appeal_window_seconds", "check_timeout_seconds", "max_note"):
            self.assertIn(key, cfg)

    def test_goal_types(self):
        goals = json.loads(self.c.get_goal_types())
        self.assertEqual([g["goal_type"] for g in goals], list(m.GOAL_ORDER))
        commits = goals[0]
        self.assertEqual(commits["hosts"], ["github.com", "api.github.com"])
        self.assertTrue(all(g["example"].startswith("https://") for g in goals))

    def test_empty_views(self):
        stats = json.loads(self.c.get_stats())
        self.assertEqual(stats["vows"], 0)
        self.assertEqual(stats["kept_bps"], 0)
        self.assertEqual(json.loads(self.c.list_vows(0, 10))["items"], [])
        self.assertEqual(json.loads(self.c.list_events(0, 10))["items"], [])
        self.assertEqual(json.loads(self.c.get_maker_vows(MAKER))["items"], [])
        acct = json.loads(self.c.get_accounting())
        self.assertTrue(acct["balanced"])
        pool = json.loads(self.c.get_pool())
        self.assertEqual(pool["balance"], "0")
        expect_user_error(self, self.c.get_vow, "1")

    def _story(self):
        a = create(self.c, stake_gen=10, target=10)
        b = create(self.c, who=MAKER_2, stake_gen=6, goal_type="LOG_ENTRIES", url=LOG_URL, target=3)
        c3 = create(self.c, stake_gen=4)
        check(self.c, a, 10)
        out = check(self.c, b, 1)
        appeal(self.c, b, who=MAKER_2)
        finalize(self.c, b, 2)
        return a, b, c3

    def test_lists_newest_first_with_timestamps_and_filter(self):
        a, b, c3 = self._story()
        page = json.loads(self.c.list_vows(0, 2))
        self.assertEqual(page["total"], 3)
        self.assertEqual([i["id"] for i in page["items"]], [c3, b])
        item = page["items"][1]
        for key in ("created_epoch", "deadline_epoch", "checked_epoch", "settled_epoch", "appeal_until", "verdict",
                    "returned", "forfeited", "appealed", "evidence_host"):
            self.assertIn(key, item)
        self.assertTrue(item["appealed"])
        self.assertEqual(item["verdict"], "PARTIAL")
        self.assertEqual(item["count"], 2)
        settled = json.loads(self.c.list_vows(0, 10, "settled"))
        self.assertEqual([i["id"] for i in settled["items"]], [b, a])
        self.assertEqual(json.loads(self.c.list_vows(1, 10, "SETTLED"))["items"][0]["id"], a)
        expect_user_error(self, self.c.list_vows, 0, 10, "LOST")
        self.assertEqual(json.loads(self.c.list_vows(0, 999))["limit"], self.c.MAX_PAGE)

    def test_stats_and_events(self):
        self._story()
        stats = json.loads(self.c.get_stats())
        self.assertEqual((stats["vows"], stats["active"], stats["settled"], stats["met"], stats["partial"]), (3, 1, 2, 1, 1))
        self.assertEqual(stats["appeals"], 1)
        self.assertEqual(stats["appeals_upheld"], 1)
        self.assertEqual(int(stats["staked_total"]), 20 * GEN)
        self.assertEqual(int(stats["locked_stakes"]), 4 * GEN)
        self.assertEqual(stats["kept_bps"], (10 * GEN + 4 * GEN) * 10000 // (16 * GEN))
        events = json.loads(self.c.list_events(0, 50))
        kinds = [e["kind"] for e in reversed(events["items"])]
        self.assertEqual(kinds, ["CREATED", "CREATED", "CREATED", "CHECKED", "SETTLED", "CHECKED", "APPEALED",
                                 "APPEAL_REVIEWED", "SETTLED"])
        self.assertTrue(all(isinstance(e["epoch"], int) and e["epoch"] > 0 for e in events["items"]))
        second = json.loads(self.c.list_events(2, 2))
        self.assertEqual([e["n"] for e in second["items"]], [6, 5])

    def test_accounting_and_pool_views(self):
        self._story()
        set_caller(OWNER)
        self.c.set_beneficiary(CHARITY, "Fund")
        set_caller(KEEPER)
        self.c.distribute_pool()
        sync_balance(self.c)
        acct = json.loads(self.c.get_accounting())
        self.assertTrue(acct["balanced"])
        self.assertEqual(int(acct["locked_stakes"]), 4 * GEN)
        pool = json.loads(self.c.get_pool())
        self.assertEqual(int(pool["distributed_total"]), 2 * GEN)
        self.assertEqual(int(pool["refunded_bonds_total"]), GEN)

    def test_get_vow_and_maker_views(self):
        a, b, c3 = self._story()
        full = json.loads(self.c.get_vow(b))
        self.assertEqual(full["appeal"]["note"], "see entries on 2026-11-22")
        self.assertEqual(int(full["appeal_bond"]), GEN)
        mine = json.loads(self.c.get_maker_vows(MAKER))
        self.assertEqual([i["id"] for i in mine["items"]], [c3, a])
        self.assertEqual(int(mine["pending_wei"]), 10 * GEN)
        preview = json.loads(self.c.preview_appeal(c3))
        self.assertEqual(preview["status"], "ACTIVE")


if __name__ == "__main__":
    unittest.main()
