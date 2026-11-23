import json
import unittest

from tests._bootstrap import Model, Web, answer, gl, m
from unittest.mock import patch

CTX = {"goal_type": "LOG_ENTRIES", "title": "Run", "goal_text": "runs logged", "target": 20, "url": "https://x.org/log",
       "window_start": "2026-11-20", "window_end": "2026-11-27", "round": 1, "min_chars": 20, "max_chars": 14000}


def ok(count, verdict=None):
    return {"status": "OK", "count": count, "verdict": verdict or m._verdict_of(count, CTX["target"]), "reason": "r"}


class NormalizationTests(unittest.TestCase):
    def test_norm_count(self):
        self.assertEqual(m._norm_count(5, 10), 5)
        self.assertEqual(m._norm_count(50, 10), 10)
        self.assertEqual(m._norm_count("7", 10), 7)
        self.assertEqual(m._norm_count(3.9, 10), 3)
        for bad in (True, None, -1, "x", "1.5", float("nan"), [], {}):
            self.assertIsNone(m._norm_count(bad, 10), bad)

    def test_verdict_and_progress(self):
        self.assertEqual(m._verdict_of(0, 5), "MISSED")
        self.assertEqual(m._verdict_of(3, 5), "PARTIAL")
        self.assertEqual(m._verdict_of(5, 5), "MET")
        self.assertEqual(m._progress_bps(1, 3), 3333)
        self.assertEqual(m._progress_bps(9, 3), 10000)

    def test_hosts(self):
        self.assertEqual(m._host_of("https://API.GitHub.com/repos/a/b/commits"), "api.github.com")
        for bad in ("http://a.com", "https://a", "https://10.0.0.1/x", "https://box.local/x", "https://a.com/ x",
                    "https://localhost/x"):
            self.assertIsNone(m._host_of(bad), bad)

    def test_safe_json(self):
        self.assertEqual(m._safe_json_obj('{"a": 1}'), {"a": 1})
        self.assertEqual(m._safe_json_obj('noise {"a": 2} tail'), {"a": 2})
        self.assertEqual(m._safe_json_obj("[1,2]"), {})
        self.assertEqual(m._safe_json_obj({"b": 3}), {"b": 3})
        self.assertEqual(m._safe_json_obj(None), {})


class AgreementTests(unittest.TestCase):
    def test_same_verdict_within_tolerance(self):
        self.assertTrue(m._agree(ok(12), ok(13), CTX))
        self.assertTrue(m._agree(ok(12), ok(10), CTX))
        self.assertFalse(m._agree(ok(12), ok(9), CTX))

    def test_verdict_must_match(self):
        self.assertFalse(m._agree(ok(20), ok(19), CTX))
        self.assertFalse(m._agree(ok(1), ok(0), CTX))

    def test_leader_must_be_self_consistent(self):
        self.assertFalse(m._agree(ok(12, "MET"), ok(12), CTX))
        self.assertFalse(m._agree(ok(25), ok(20), CTX))
        self.assertFalse(m._agree({"status": "OK", "count": True, "verdict": "PARTIAL", "reason": "r"}, ok(1), CTX))
        self.assertFalse(m._agree({"status": "OK", "count": 3, "verdict": "PARTIAL", "reason": 5}, ok(3), CTX))

    def test_failure_statuses_agree_only_with_same_status(self):
        down = {"status": "UNREACHABLE", "count": 0, "verdict": "", "reason": "x"}
        self.assertTrue(m._agree(down, dict(down), CTX))
        self.assertFalse(m._agree(down, ok(3), CTX))
        self.assertFalse(m._agree(ok(3), down, CTX))
        self.assertFalse(m._agree({"status": "WEIRD"}, {"status": "WEIRD"}, CTX))
        self.assertFalse(m._agree("x", ok(1), CTX))

    def test_small_targets_need_exact_counts(self):
        ctx = dict(CTX, target=5)
        self.assertFalse(m._agree({"status": "OK", "count": 2, "verdict": "PARTIAL", "reason": "r"},
                                  {"status": "OK", "count": 3, "verdict": "PARTIAL", "reason": "r"}, ctx))

    def test_validator_runs_its_own_review(self):
        web = Web("2026-11-21 run\n" * 5)
        with patch.object(gl.nondet.web, "render", side_effect=web.render), \
                patch.object(gl.nondet, "exec_prompt", side_effect=Model(answer(11))):
            self.assertTrue(m._validate(gl.vm.Return(ok(12)), CTX))
            self.assertFalse(m._validate(gl.vm.Return(ok(5)), CTX))
            self.assertFalse(m._validate(ok(12), CTX))
        self.assertEqual(len(web.calls), 2)

    def test_appeal_prompt_carries_note_and_first_count(self):
        ctx = dict(CTX, round=2, first_count=4, note="entries on 21 and 22")
        prompt = m._eval_prompt(ctx, "evidence")
        self.assertIn("first review counted 4", prompt)
        self.assertIn("entries on 21 and 22", prompt)
        self.assertNotIn("appeal review", m._eval_prompt(CTX, "evidence"))


if __name__ == "__main__":
    unittest.main()
