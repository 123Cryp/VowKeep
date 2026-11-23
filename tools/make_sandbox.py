#!/usr/bin/env python3
"""
Builds contract_sandbox.py from contract.py.

The sandbox build is the same contract with five class constants changed so
a whole vow lifecycle can be tried in minutes on GenLayer Studio:

  MODE                    "production" -> "sandbox"
  MIN_DURATION_MINUTES    1440         -> 1     (a vow can end one minute after it is made)
  APPEAL_WINDOW_SECONDS   259200       -> 600   (10 minutes to appeal)
  CHECK_TIMEOUT_SECONDS   604800       -> 300
  APPEAL_TIMEOUT_SECONDS  604800       -> 300

Nothing else changes. The script refuses to run unless each constant line
exists exactly once, and --check fails when the committed file is stale.

Usage:
    python3 tools/make_sandbox.py            write contract_sandbox.py
    python3 tools/make_sandbox.py --check    exit 1 if contract_sandbox.py is stale
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SOURCE = os.path.join(ROOT, "contract.py")
TARGET = os.path.join(ROOT, "contract_sandbox.py")

CHANGES = (
    ('    MODE = "production"', '    MODE = "sandbox"'),
    ("    MIN_DURATION_MINUTES = 1440", "    MIN_DURATION_MINUTES = 1"),
    ("    APPEAL_WINDOW_SECONDS = 259200", "    APPEAL_WINDOW_SECONDS = 600"),
    ("    CHECK_TIMEOUT_SECONDS = 604800", "    CHECK_TIMEOUT_SECONDS = 300"),
    ("    APPEAL_TIMEOUT_SECONDS = 604800", "    APPEAL_TIMEOUT_SECONDS = 300"),
)


def build(source):
    lines = source.split("\n")
    for old, new in CHANGES:
        hits = [i for i, line in enumerate(lines) if line == old]
        if len(hits) != 1:
            raise SystemExit(f"expected exactly one line {old!r} in contract.py, found {len(hits)}")
        lines[hits[0]] = new
    return "\n".join(lines)


def main(argv):
    with open(SOURCE, encoding="utf-8") as handle:
        result = build(handle.read())
    if "--check" in argv:
        try:
            with open(TARGET, encoding="utf-8") as handle:
                current = handle.read()
        except FileNotFoundError:
            current = None
        if current != result:
            print("contract_sandbox.py is stale: run python3 tools/make_sandbox.py")
            return 1
        print("contract_sandbox.py is up to date")
        return 0
    with open(TARGET, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(result)
    print(f"wrote {TARGET}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
