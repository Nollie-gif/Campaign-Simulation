"""Require the matching durable record to be touched for a meaningful change.

A pull request that touches an engineering-sensitive path must also touch
the ledger file(s) that are supposed to record why, unless a commit on the
branch explicitly declares the change exempt. This does not — and cannot —
judge whether the ledger entry is *good*; it only checks that the file was
touched or the skip was made visible and permanent in Git history.
"""

from __future__ import annotations

import fnmatch
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# (ledger file, path patterns that require it to be touched)
LEDGER_DOMAINS: list[tuple[str, list[str]]] = [
    (
        "CHANGELOG.md",
        [
            "src/campaign_simulation/*",
            "schemas/*",
            ".github/workflows/*",
            "tools/*",
        ],
    ),
    (
        "ENGINE_CHANGELOG.md",
        [
            "src/campaign_simulation/*",
            "schemas/*",
            ".github/workflows/*",
            "tools/*",
        ],
    ),
    (
        "AGENT_HANDOFF.md",
        [
            ".github/copilot-instructions.md",
            "INSTALLATION_GUIDE.md",
        ],
    ),
]

EXEMPT_TRAILER = re.compile(r"^Ledger-Exempt:\s*(\S+)\s+\S.*$", re.MULTILINE)


def _git(*args: str) -> str:
    result = subprocess.run(
        ["git", *args], cwd=ROOT, capture_output=True, text=True, check=True
    )
    return result.stdout


def changed_paths() -> set[str]:
    base = subprocess.run(
        ["git", "merge-base", "HEAD", "origin/main"],
        cwd=ROOT, capture_output=True, text=True,
    )
    if base.returncode != 0:
        return set()
    merge_base = base.stdout.strip()
    output = _git("diff", "--name-only", f"{merge_base}..HEAD")
    return {line for line in output.splitlines() if line}


def exempted_ledgers() -> set[str]:
    base = subprocess.run(
        ["git", "merge-base", "HEAD", "origin/main"],
        cwd=ROOT, capture_output=True, text=True,
    )
    if base.returncode != 0:
        return set()
    merge_base = base.stdout.strip()
    log = _git("log", f"{merge_base}..HEAD", "--format=%B")
    return {m.group(1) for m in EXEMPT_TRAILER.finditer(log)}


def matches_any(path: str, patterns: list[str]) -> bool:
    return any(fnmatch.fnmatch(path, pattern) for pattern in patterns)


def main() -> int:
    diff = changed_paths()
    if not diff:
        print("No branch diff against origin/main found; skipping (not on a feature branch or origin/main unavailable).")
        return 0

    exempt = exempted_ledgers()
    failures: list[str] = []

    for ledger_file, patterns in LEDGER_DOMAINS:
        sensitive_touched = [p for p in diff if matches_any(p, patterns) and p != ledger_file]
        if not sensitive_touched:
            continue
        if ledger_file in diff:
            continue
        if ledger_file in exempt:
            continue
        failures.append(
            f"{ledger_file} was not updated, but this branch touches: {', '.join(sorted(sensitive_touched))}. "
            f"Update {ledger_file}, or add a commit trailer 'Ledger-Exempt: {ledger_file} <reason>'."
        )

    if failures:
        print("Change-ledger check failed:\n")
        print("\n".join(f"  - {f}" for f in failures))
        return 1
    print("Change-ledger check passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
