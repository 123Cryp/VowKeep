import json
import unittest

from tests._bootstrap import (
    CLOCK, COMMITS_URL, GEN, LOG_URL, MAKER, MAKER_2, PaymentRejected, assert_invariants, create, make_contract,
    pending, set_caller, call_payable, vow,
)


class CreateVowTests(unittest.TestCase):
    def setUp(self):
        self.c = make_contract()

    def test_create_records_vow_and_locks_stake(self):
        vid = create(self.c, stake_gen=7)
        v = vow(self.c, vid)
        self.assertEqual(vid, "1")
        self.assertEqual(v["status"], "ACTIVE")
        self.assertEqual(v["maker"], MAKER)
        self.assertEqual(int(v["stake"]), 7 * GEN)
        self.assertEqual(v["evidence_host"], "api.github.com")
        self.assertEqual(v["deadline_epoch"] - v["created_epoch"], self.c.MIN_DURATION_MINUTES * 60)
        self.assertEqual(int(self.c.locked_stakes), 7 * GEN)
        assert_invariants(self, self.c)

    def test_ids_increase_and_maker_index(self):
        a = create(self.c)
        b = create(self.c, goal_type="LOG_ENTRIES", url=LOG_URL, target=5)
        c2 = create(self.c, who=MAKER_2)
        self.assertEqual([a, b, c2], ["1", "2", "3"])
        mine = json.loads(self.c.get_maker_vows(MAKER))
        self.assertEqual([i["id"] for i in mine["items"]], ["2", "1"])
        self.assertEqual(mine["open"], 2)

    def _rejects(self, fragment, **kw):
        with self.assertRaises(PaymentRejected) as ctx:
            create(self.c, **kw)
        self.assertIn(fragment, str(ctx.exception))
        assert_invariants(self, self.c)

    def test_rejections_refund_the_stake(self):
        self._rejects("goal_type", goal_type="STEPS")
        self._rejects("title", title="")
        self._rejects("title", title="x" * 81)
        self._rejects("goal_text", goal_text="  ")
        self._rejects("target", target=0)
        self._rejects("target", target=501)
        self._rejects("target", goal_type="FILE_UPDATE", target=2, url=LOG_URL)
        self._rejects("whole number", target="ten")
        self._rejects("https", url="http://example.com/feed")
        self._rejects("https", url="https://localhost/x")
        self._rejects("https", url="https://127.0.0.1/x")
        self._rejects("https", url="ftp://example.com")
        self._rejects("github.com", url="https://gitlab.com/a/b/-/commits/main")
        self._rejects("at most", url="https://example.com/" + "a" * 300)
        self._rejects("duration_minutes", minutes=self.c.MIN_DURATION_MINUTES - 1 if self.c.MIN_DURATION_MINUTES > 1 else 0)
        self._rejects("duration_minutes", minutes=self.c.MAX_DURATION_MINUTES + 1)
        self._rejects("stake", value=GEN - 1)
        self._rejects("stake", value=100001 * GEN)
        self.assertEqual(int(self.c.vow_count), 0)
        self.assertGreater(pending(self.c, MAKER), 0)

    def test_zero_value_raises_instead_of_bounce(self):
        with self.assertRaises(Exception):
            create(self.c, value=0)
        self.assertEqual(int(self.c.vow_count), 0)

    def test_goal_type_is_case_insensitive_and_text_is_trimmed(self):
        vid = create(self.c, goal_type="posts", title="  Write   weekly  ", url="https://blog.example.org/feed.xml", target=4)
        v = vow(self.c, vid)
        self.assertEqual(v["goal_type"], "POSTS")
        self.assertEqual(v["title"], "Write weekly")

    def test_open_vow_cap(self):
        cap = self.c.MAX_OPEN_PER_MAKER
        for _ in range(cap):
            create(self.c, stake_gen=1)
        with self.assertRaises(PaymentRejected):
            create(self.c, stake_gen=1)
        assert_invariants(self, self.c)

    def test_event_logged_with_timestamp(self):
        create(self.c)
        events = json.loads(self.c.list_events(0, 5))
        self.assertEqual(events["total"], 1)
        ev = events["items"][0]
        self.assertEqual(ev["kind"], "CREATED")
        self.assertEqual(ev["vow_id"], "1")
        self.assertEqual(ev["epoch"], int(CLOCK.now.timestamp()))


if __name__ == "__main__":
    unittest.main()
