import os
import re
import unittest

from tests._bootstrap import CONTRACT_PATH, ROOT, m

EXPECTED_HEADER = [
    "# v0.2.16",
    '# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }',
]


class FormatTests(unittest.TestCase):
    def setUp(self):
        with open(CONTRACT_PATH, encoding="utf-8") as handle:
            self.source = handle.read()
        self.lines = self.source.split("\n")

    def test_two_header_lines_then_code(self):
        self.assertEqual(self.lines[:2], EXPECTED_HEADER)
        self.assertEqual(self.lines[2], "from genlayer import *")

    def test_no_comments_or_docstrings_after_header(self):
        for number, line in enumerate(self.lines[2:], start=3):
            self.assertFalse(line.strip().startswith("#"), f"comment on line {number}")
        self.assertNotIn('"""', self.source)
        self.assertNotIn("'''", self.source)

    def test_ascii_english_only(self):
        self.assertTrue(all(ord(ch) < 128 for ch in self.source))

    def test_uses_web_llm_and_custom_equivalence(self):
        self.assertIn("gl.nondet.web.render", self.source)
        self.assertIn("gl.nondet.exec_prompt", self.source)
        self.assertIn('response_format="json"', self.source)
        self.assertIn("gl.vm.run_nondet_unsafe", self.source)

    def test_public_surface(self):
        writes = {"create_vow", "check", "appeal", "finalize", "claim_ownership", "transfer_ownership",
                  "set_beneficiary", "distribute_pool", "withdraw", "push_payment"}
        views = {"get_config", "get_goal_types", "get_stats", "get_pool", "get_accounting", "get_vow", "list_vows",
                 "get_maker_vows", "list_events", "preview_appeal", "get_pending_withdrawal"}
        found_w = set(re.findall(r"@gl\.public\.write(?:\.payable)?\n    def (\w+)", self.source))
        found_v = set(re.findall(r"@gl\.public\.view\n    def (\w+)", self.source))
        self.assertEqual(found_w, writes)
        self.assertEqual(found_v, views)
        self.assertEqual(set(re.findall(r"@gl\.public\.write\.payable\n    def (\w+)", self.source)),
                         {"create_vow", "appeal"})

    def test_sandbox_build_is_current(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("mk", os.path.join(ROOT, "tools", "make_sandbox.py"))
        mk = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mk)
        with open(os.path.join(ROOT, "contract.py"), encoding="utf-8") as handle:
            built = mk.build(handle.read())
        with open(os.path.join(ROOT, "contract_sandbox.py"), encoding="utf-8") as handle:
            self.assertEqual(handle.read(), built)


if __name__ == "__main__":
    unittest.main()
