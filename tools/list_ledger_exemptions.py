"""List every Ledger-Exempt: trailer ever committed to this repository.

The exemption mechanism in tools/validate_change_ledger.py is deliberately
easy to use honestly and does not judge the *quality* of a reason — its
safety property is that a skip is always visible and permanent in Git
history, never silent. This script is the read side of that property: a
periodic human scan for whether exemptions are being used honestly (rare,
specific reasons) or as a rubber stamp (frequent, generic ones).
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXEMPT_TRAILER = re.compile(r"^Ledger-Exempt:\s*(\S+)\s+(\S.*)$", re.MULTILINE)


def main() -> int:
    log = subprocess.run(
        ["git", "log", "--all", "--format=%H%x00%ad%x00%B%x1e", "--date=short"],
        cwd=ROOT, capture_output=True, text=True, check=True,
    ).stdout

    found = 0
    for record in log.split("\x1e"):
        if "\x00" not in record:
            continue
        sha, date, body = record.split("\x00", 2)
        for match in EXEMPT_TRAILER.finditer(body):
            found += 1
            print(f"{date}  {sha.strip()[:8]}  {match.group(1)}: {match.group(2)}")

    if found == 0:
        print("No Ledger-Exempt: trailers found in reachable history.")
    else:
        print(f"\n{found} exemption(s) total. Review for pattern abuse periodically.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
