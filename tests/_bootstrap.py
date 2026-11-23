"""
Shared test bootstrap: wires up the offline genlayer SDK stub, loads the
contract once (contract.py by default, or the file named by the VK_CONTRACT
environment variable, which is how the sandbox build is tested), replaces the
contract's clock with a controllable one, and provides helpers for vows,
mocked evidence pages and mocked model answers.
"""
import datetime as _dt
import importlib.util
import json as _json
import os
import sys
from unittest.mock import patch as _patch

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_STUB_DIR = os.path.join(_THIS_DIR, "genlayer_stub")
if _STUB_DIR not in sys.path:
    sys.path.insert(0, _STUB_DIR)

ROOT = os.path.dirname(_THIS_DIR)
CONTRACT_PATH = os.environ.get("VK_CONTRACT") or os.path.join(ROOT, "contract.py")
_spec = importlib.util.spec_from_file_location("vowkeep_contract", CONTRACT_PATH)
m = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(m)

VowKeep = m.VowKeep
gl = m.gl
Address = m.Address
u256 = m.u256
GEN = 10 ** 18
SANDBOX = VowKeep.MODE == "sandbox"

UTC = _dt.timezone.utc
BASE = _dt.datetime(2026, 11, 20, 9, 0, 0, tzinfo=UTC)
DAY = 86400


class Clock:
    def __init__(self):
        self.now = BASE

    def reset(self):
        self.now = BASE

    def advance(self, seconds):
        self.now = self.now + _dt.timedelta(seconds=seconds)

    def set_epoch(self, epoch):
        self.now = _dt.datetime.fromtimestamp(int(epoch), UTC)


CLOCK = Clock()
VowKeep._now_utc = staticmethod(lambda: CLOCK.now)

OWNER = "0x" + "aa" * 20
MAKER = "0x" + "b1" * 20
MAKER_2 = "0x" + "b2" * 20
KEEPER = "0x" + "c1" * 20
STRANGER = "0x" + "d1" * 20
CHARITY = "0x" + "e1" * 20

COMMITS_URL = "https://api.github.com/repos/123Cryp/VowKeep/commits?per_page=100"
LOG_URL = "https://raw.githubusercontent.com/123Cryp/VowKeep/main/proof/LOG.md"
PAGE = "2026-11-21 commit one\n2026-11-22 commit two\n2026-11-23 commit three\n" * 3

_INFLOW = [0]


def set_caller(address_text):
    gl.message.sender_address = Address(address_text)


def make_contract():
    CLOCK.reset()
    gl.evm.transfers.clear()
    _INFLOW[0] = 0
    set_caller(OWNER)
    return VowKeep()


class PaymentRejected(gl.vm.UserError):
    pass


def _snapshot(contract):
    return (dict(contract.vows), int(contract.locked_stakes), int(contract.locked_bonds), int(contract.pool_balance),
            int(contract.vow_count))


def call_payable(contract, method_name, value, *args):
    """Invoke a payable method with `value` wei attached. A returned
    rejection must credit the exact value back and change nothing else; it
    is then raised as PaymentRejected."""
    gl.message.value = u256(value)
    contract.balance = contract.balance + u256(value)
    _INFLOW[0] += int(value)
    sender = str(gl.message.sender_address).lower()
    before = _snapshot(contract)
    owed_before = int(contract.pending_withdrawals[sender]) if sender in contract.pending_withdrawals else 0
    try:
        result = getattr(contract, method_name)(*args)
    except Exception:
        contract.balance = contract.balance - u256(value)
        _INFLOW[0] -= int(value)
        raise
    finally:
        gl.message.value = u256(0)
    if isinstance(result, str) and '"rejected"' in result and '"refunded_wei"' in result:
        data = _json.loads(result)
        owed_after = int(contract.pending_withdrawals[sender]) if sender in contract.pending_withdrawals else 0
        assert data["refunded_wei"] == str(int(value)), data
        assert owed_after - owed_before == int(value), (owed_before, owed_after, value)
        assert _snapshot(contract) == before, "a rejected payable call changed state"
        raise PaymentRejected(data["rejected"])
    return result


def sync_balance(contract):
    out = sum(int(t["value"]) for t in gl.evm.transfers)
    contract.balance = u256(_INFLOW[0] - out)
    return int(contract.balance)


def assert_invariants(testcase, contract):
    sync_balance(contract)
    acct = _json.loads(contract.get_accounting())
    testcase.assertTrue(acct["balanced"], acct)
    testcase.assertEqual(int(acct["contract_balance"]), int(acct["liabilities"]), acct)
    stakes = bonds = 0
    counts = {s: 0 for s in m.STATUSES}
    for raw in contract.vows.values():
        vow = _json.loads(raw)
        counts[vow["status"]] += 1
        if vow["status"] != m.ST_SETTLED:
            stakes += int(vow["stake"])
        if vow["status"] == m.ST_APPEALED:
            bonds += int(vow["appeal"]["bond"])
        if vow["status"] == m.ST_SETTLED:
            testcase.assertEqual(int(vow["returned"]) + int(vow["forfeited"]), int(vow["stake"]))
    testcase.assertEqual(stakes, int(contract.locked_stakes))
    testcase.assertEqual(bonds, int(contract.locked_bonds))
    testcase.assertEqual(counts[m.ST_ACTIVE], int(contract.active_count))
    testcase.assertEqual(counts[m.ST_CHECKED], int(contract.checked_count))
    testcase.assertEqual(counts[m.ST_APPEALED], int(contract.appealed_count))
    testcase.assertEqual(counts[m.ST_SETTLED], int(contract.settled_count))
    testcase.assertEqual(sum(int(v) for v in contract.pending_withdrawals.values()), int(contract.owed_total))
    stats = _json.loads(contract.get_stats())
    testcase.assertEqual(stats["met"] + stats["partial"] + stats["missed"], stats["settled"])


class Web:
    """Replacement for gl.nondet.web.render: the first route whose substring
    is contained in the URL answers; an Exception body is raised."""

    def __init__(self, body=PAGE, fragment="https://"):
        self.routes = [(fragment, body)] if body is not None else []
        self.calls = []

    def render(self, url, mode="text"):
        self.calls.append(url)
        for fragment, body in self.routes:
            if fragment in url:
                if isinstance(body, Exception):
                    raise body
                return body
        raise RuntimeError("404 " + url)


class Model:
    """Replacement for gl.nondet.exec_prompt. `answers` is a single answer or
    a list consumed in order (the stub runs leader then validator)."""

    def __init__(self, answers):
        self.answers = answers if isinstance(answers, list) else None
        self.answer = None if isinstance(answers, list) else answers
        self.prompts = []

    def __call__(self, prompt, response_format="text"):
        self.prompts.append(prompt)
        answer = self.answers.pop(0) if self.answers is not None else self.answer
        if isinstance(answer, Exception):
            raise answer
        return answer


def answer(count, verdict=None, reason="counted dated items"):
    return _json.dumps({"qualifying_count": count, "verdict": verdict or "MET", "reason": reason})


def review_patch(web, model):
    return (_patch.object(gl.nondet.web, "render", side_effect=web.render),
            _patch.object(gl.nondet, "exec_prompt", side_effect=model))


def run_review(fn, *args, web=None, model=None):
    web = web or Web()
    p1, p2 = review_patch(web, model)
    with p1, p2:
        return fn(*args)


def create(c, who=MAKER, stake_gen=10, goal_type="COMMITS", title="Ship VowKeep", goal_text="commits to 123Cryp/VowKeep",
           target=10, url=COMMITS_URL, minutes=None, value=None):
    set_caller(who)
    if minutes is None:
        minutes = int(c.MIN_DURATION_MINUTES)
    raw = call_payable(c, "create_vow", stake_gen * GEN if value is None else value, goal_type, title, goal_text,
                       target, url, minutes)
    return _json.loads(raw)["vow_id"]


def vow(c, vow_id):
    return _json.loads(c.get_vow(vow_id))


def past_deadline(c, vow_id, extra=0):
    wanted = int(vow(c, vow_id)["deadline_epoch"]) + extra
    CLOCK.set_epoch(max(wanted, int(CLOCK.now.timestamp())))


def check(c, vow_id, count, caller=KEEPER, web=None, model=None, extra=0):
    past_deadline(c, vow_id, extra)
    set_caller(caller)
    model = model or Model(answer(count))
    return _json.loads(run_review(c.check, vow_id, web=web, model=model))


def appeal(c, vow_id, note="see entries on 2026-11-22", who=MAKER, value=None):
    set_caller(who)
    if value is None:
        value = int(_json.loads(c.preview_appeal(vow_id))["bond_wei"])
    return _json.loads(call_payable(c, "appeal", value, vow_id, note))


def finalize(c, vow_id, count=None, caller=KEEPER, web=None, model=None):
    set_caller(caller)
    if model is None and count is not None:
        model = Model(answer(count))
    if model is None:
        return _json.loads(c.finalize(vow_id))
    return _json.loads(run_review(c.finalize, vow_id, web=web, model=model))


def pending(c, address):
    return int(c.get_pending_withdrawal(address))


def expect_user_error(testcase, fn, *args, **kwargs):
    with testcase.assertRaises(gl.vm.UserError) as ctx:
        fn(*args, **kwargs)
    return str(ctx.exception)
