import os
import re
import unittest

from tests._bootstrap import ROOT

with open(os.path.join(ROOT, "index.html"), encoding="utf-8") as _h:
    HTML = _h.read()
CSS = HTML.split("<style>")[1].split("</style>")[0]
JS = HTML.split('<script type="module">')[1]


class FrontendTests(unittest.TestCase):
    def test_english_ascii_markup(self):
        self.assertFalse(re.search(r"[؀-ۿ]", HTML))

    def test_viewport_and_text_size_adjust(self):
        self.assertIn("viewport-fit=cover", HTML)
        self.assertIn("text-size-adjust:100%", CSS)

    def test_look_rules(self):
        self.assertIn("Public+Sans", HTML)
        self.assertNotIn("radial-gradient", CSS)
        self.assertNotIn("tabular-nums", CSS)
        self.assertNotIn("tabular", JS)
        self.assertRegex(CSS, r"--t-head:clamp\(26px,[^)]*36px\)")
        self.assertIn("prefers-color-scheme", HTML)
        self.assertIn(':root[data-theme="dark"]', CSS)
        self.assertIn("[hidden]{display:none!important}", CSS)

    def test_layout(self):
        self.assertIn("@media (min-width:1024px)", CSS)
        self.assertIn("nav.tabs", CSS)
        self.assertIn("act-first", CSS)
        self.assertIn("only-wide", CSS)
        self.assertIn("only-narrow", CSS)

    def test_home_sections(self):
        for text in ("Live contract activity", "Balanced", "Start where you are", "How a vow works", "Latest vows",
                     "Say it in one sentence", "livepill"):
            self.assertIn(text, JS + CSS)
        self.assertEqual(JS.count("class: \"role\""), 1)
        self.assertEqual(len(re.findall(r"role\(\"(?:make|keep|pool)\"", JS)), 3)

    def test_transaction_flow(self):
        for text in ("Signature", "Submitted", "Accepted", "Finalized", "You declined the request in your wallet",
                     "Your wallet is on another network", "Switch network", "Not enough GEN", "The contract refused this call",
                     "credited back to you", "confirmAction", "aria-busy"):
            self.assertIn(text, HTML)
        self.assertIn("wallet_switchEthereumChain", JS)

    def test_wallet_and_contract_address(self):
        self.assertIn("DEFAULT_CONTRACT_ADDRESS", JS)
        self.assertIn('get("contract")', JS)
        self.assertIn("Use a Studio private key", JS)
        self.assertIn("Test session", JS)
        self.assertIn("Browser wallet", JS)

    def test_every_contract_call_exists(self):
        with open(os.path.join(ROOT, "contract.py"), encoding="utf-8") as handle:
            source = handle.read()
        defined = set(re.findall(r"    def (\w+)\(self", source))
        called = set(re.findall(r'(?:read|readJson)\("(\w+)"', JS)) | set(re.findall(r'write\(\w+, "[^"]+", "(\w+)"', JS))
        called |= set(re.findall(r'"(distribute_pool|withdraw|finalize|check|appeal|create_vow|set_beneficiary)"', JS))
        self.assertTrue(called)
        self.assertEqual(called - defined, set())

    def test_no_raw_date_input_in_flow(self):
        self.assertEqual(len(re.findall(r'type: "date"', JS)), 1)
        self.assertIn("dateinp", CSS)

    def test_design_section_11_pitfalls(self):
        self.assertNotIn("min-height:70vh", CSS)
        self.assertIn("repeat(4,1fr)", CSS)
        self.assertIn("wide-only", CSS)
        self.assertIn(".vcard::before", CSS)
        self.assertNotIn("border-top:3px", CSS)
        self.assertNotIn("#${v.id}", JS)
        self.assertNotIn('"#" + v.id }', JS)
        self.assertNotIn("c-sig", JS)
        self.assertNotIn("c-part", JS)
        self.assertIn('label: "Missed", tone: "warn"', JS)
        self.assertIn("min-width: 720px", JS)
        self.assertIn("short(CONTRACT_ADDRESS)", JS)
        self.assertGreaterEqual(JS.count("netNote()"), 6)
        self.assertIn("Studio test network", JS)

    def test_no_fake_data(self):
        for bad in ("Lorem", "lorem", "Math.random()", "John Doe", "TODO"):
            self.assertNotIn(bad, HTML)


if __name__ == "__main__":
    unittest.main()
