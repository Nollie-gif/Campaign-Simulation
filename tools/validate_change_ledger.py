"""Require the matching durable record to be touched for a meaningful change.

A pull request that touches an engineering-sensitive path must also touch
the ledger file(s) that are supposed to record why, unless a commit on the
branch explicitly declares the change exempt. This does not — and cannot —
judge whether the ledger entry is *good*; it only checks that the file was
touched or the skip was made visible and permanent in Git history.

Enforced from 2026-08-21 forward. Earlier history was not backfilled with
reconstructed entries — see CHANGELOG.md / ENGINE_CHANGELOG.md for that
boundary.

Self-defense notes (found by adversarial review, not theoretical):
- CI runs this file from a copy fetched from `origin/main`, not from the
  pull request's own branch (see the workflow step "Use ledger checker
  from main"), so a PR cannot silently weaken this script and have the
  weakened copy grade its own diff as clean. This does not stop a
  determined, already-trusted committer from weakening the *main* copy in
  a prior, separately-merged PR — that boundary is enforced by branch
  protection + review, not by this script, and this script cannot protect
  against its own maintainer.
- `check_pattern_coverage()` fails loudly if any domain pattern currently
  matches zero tracked files — the signal that a rename/move/restructure
  has silently orphaned a pattern instead of quietly stopping protecting
  the thing it was meant to protect.
- `assert_domains_sane()` alone was still not enough, found by actually
  replaying the attack against it rather than trusting the design: CI
  overwrites the *executing* copy with the trusted one before running, so
  the trusted, non-empty `LEDGER_DOMAINS` evaluates the diff — sees
  `tools/validate_change_ledger.py` changed, correctly requires
  CHANGELOG.md/ENGINE_CHANGELOG.md, and correctly honors the exemption
  trailer naming them. The PR still merges — carrying its own neutered
  file content, since overwriting the *executing* copy never touched what
  actually gets committed. The neutered version then becomes the trusted
  copy for every subsequent PR.
- The real fix is `check_committed_ledger_script_is_sane()`: when
  `tools/validate_change_ledger.py` itself is in the diff, it reads the
  pull request's *own* index version (`git show :...`, not the overwritten
  working copy, and not HEAD — see below) with `ast.parse` — never
  executed — and independently counts `LEDGER_DOMAINS` entries against this
  trusted script's own `MINIMUM_DOMAIN_COUNT`. This check is not exemptable
  and does not depend on what the PR's version of the script would have
  decided about itself.

Local-preflight-specific notes (a second round of adversarial review, found
against PR #21 by an automated reviewer before merge — real findings, not
theoretical, and none of them affect the CI-enforced boundary above):
- `changed_paths()` diffs the merge-base against the *prospective* tree
  (`git write-tree`) rather than HEAD or a union of separately-collected
  path lists — see that function's docstring for the specific scenario this
  closes (a staged revert of an already-committed ledger update, alongside
  a new unrelated sensitive change, could otherwise look satisfied).
- `check_committed_ledger_script_is_sane()` reads the index (`git show
  :path`), not `HEAD:path`, so a *staged-but-not-yet-committed* weakening of
  this file is caught immediately during local preflight instead of only
  after it lands. Identical to `HEAD:path` in CI, where the index always
  matches HEAD.
- `CAMPAIGN_SIMULATION_PENDING_LEDGER_EXEMPT` lets local preflight predict
  a `Ledger-Exempt:` trailer that does not exist yet (the commit carrying it
  hasn't been made at preflight time). This is local-only and
  non-authoritative: CI never sets it, and CI still requires the identical
  real trailer in the actual committed message regardless of what local
  preflight predicted.
- None of the three notes above change what CI enforces — CI has no staged
  state (index already equals HEAD) and never sets the pending-exemption
  variable. They fix local preflight giving an incorrect or unusable
  prediction of what CI will do, not a gap in what CI itself does.
"""

from __future__ import annotations

import ast
import fnmatch
import os
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
            "src/*",
            "schemas/*",
            ".github/workflows/*",
            "tools/*",
            "scripts/*",
        ],
    ),
    (
        "ENGINE_CHANGELOG.md",
        [
            "src/*",
            "schemas/*",
            ".github/workflows/*",
            "tools/*",
            "scripts/*",
        ],
    ),
    (
        "AGENT_HANDOFF.md",
        [
            ".github/copilot-instructions.md",
            "INSTALLATION_GUIDE.md",
            "scripts/preflight_commit.py",
            "scripts/install_preflight_hook.py",
            ".githooks/*",
        ],
    ),
]

EXEMPT_TRAILER = re.compile(r"^Ledger-Exempt:\s*(\S+)\s+\S.*$", re.MULTILINE)


def _git(*args: str) -> str:
    result = subprocess.run(
        ["git", *args], cwd=ROOT, capture_output=True, text=True, check=True
    )
    return result.stdout


def tracked_files() -> list[str]:
    output = _git("ls-files")
    return [line for line in output.splitlines() if line]


def changed_paths() -> set[str]:
    """Diff the merge-base against the *prospective* tree - what would exist
    if everything currently staged were committed right now - rather than
    against HEAD or a union of separately-collected path name lists.

    `git write-tree` writes the current index as a real tree object without
    creating a commit. In CI nothing is ever staged beyond HEAD, so this
    tree is identical to HEAD's tree and behavior there is unchanged. Locally,
    it reflects staged adds *and* staged reverts correctly, which a union of
    "paths touched in committed history" + "paths touched in the staged
    diff" cannot: adversarial review found that union could let an earlier,
    already-committed ledger update paper over a later staged change that
    reverts that very ledger update while introducing a new, unrelated
    sensitive change in the same breath - the union still "sees" the ledger
    file as touched, even though the tree about to be committed would not
    actually carry that update relative to the merge base.
    """
    base = subprocess.run(
        ["git", "merge-base", "HEAD", "origin/main"],
        cwd=ROOT, capture_output=True, text=True,
    )
    if base.returncode != 0:
        return set()
    merge_base = base.stdout.strip()
    tree = subprocess.run(
        ["git", "write-tree"], cwd=ROOT, capture_output=True, text=True,
    )
    if tree.returncode != 0:
        # Unmerged/conflicted index or similar unusual state: fall back to
        # the committed-only comparison rather than fail outright.
        committed = _git("diff", "--name-only", f"{merge_base}..HEAD")
        return {line for line in committed.splitlines() if line}
    prospective_tree = tree.stdout.strip()
    diff = _git("diff", "--name-only", merge_base, prospective_tree)
    return {line for line in diff.splitlines() if line}


def exempted_ledgers() -> set[str]:
    base = subprocess.run(
        ["git", "merge-base", "HEAD", "origin/main"],
        cwd=ROOT, capture_output=True, text=True,
    )
    if base.returncode != 0:
        return set()
    merge_base = base.stdout.strip()
    log = _git("log", f"{merge_base}..HEAD", "--format=%B")
    exempt = {m.group(1) for m in EXEMPT_TRAILER.finditer(log)}
    # Local-only, non-authoritative: a preflight run predicting a trailer it
    # is about to commit (see scripts/preflight_commit.py --pending-exempt),
    # so a first-time legitimate exemption isn't blocked by the fact that
    # the commit carrying its trailer doesn't exist yet at preflight time.
    # CI never sets this variable, so this is a no-op there; CI always
    # re-derives the exemption from the real committed trailer above.
    pending = os.environ.get("CAMPAIGN_SIMULATION_PENDING_LEDGER_EXEMPT", "")
    exempt |= {m.group(1) for m in EXEMPT_TRAILER.finditer(pending)}
    return exempt


def matches_any(path: str, patterns: list[str]) -> bool:
    return any(fnmatch.fnmatch(path, pattern) for pattern in patterns)


def check_pattern_coverage(all_files: list[str]) -> list[str]:
    """A domain pattern that matches nothing anymore means a rename/move
    silently stopped it from protecting whatever it used to protect."""
    orphaned: list[str] = []
    for ledger_file, patterns in LEDGER_DOMAINS:
        for pattern in patterns:
            if not any(fnmatch.fnmatch(f, pattern) for f in all_files):
                orphaned.append(f"{ledger_file}: pattern '{pattern}' matches no tracked file")
    return orphaned


MINIMUM_DOMAIN_COUNT = 3  # CHANGELOG.md, ENGINE_CHANGELOG.md, AGENT_HANDOFF.md


def assert_domains_sane() -> list[str]:
    """Unconditional floor: cannot be waived by an exemption trailer,
    because it does not check the *diff*, it checks this trusted script's
    own hardcoded expectations of itself."""
    problems: list[str] = []
    if len(LEDGER_DOMAINS) < MINIMUM_DOMAIN_COUNT:
        problems.append(
            f"LEDGER_DOMAINS has only {len(LEDGER_DOMAINS)} entries; expected at least {MINIMUM_DOMAIN_COUNT}."
        )
    for ledger_file, patterns in LEDGER_DOMAINS:
        if not patterns:
            problems.append(f"{ledger_file} has zero domain patterns.")
    return problems


SELF_PATH = "tools/validate_change_ledger.py"


def _count_ledger_domains_in_source(source: str) -> int | None:
    """Statically count LEDGER_DOMAINS list entries without executing
    untrusted code. Returns None if the assignment can't be found/parsed
    at all, which is itself suspicious (renamed variable, broken syntax,
    or the check restructured specifically to hide from this scan)."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return None
    for node in ast.walk(tree):
        target_matches = False
        value = None
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == "LEDGER_DOMAINS" for t in node.targets
        ):
            target_matches = True
            value = node.value
        elif (
            isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == "LEDGER_DOMAINS"
        ):
            target_matches = True
            value = node.value
        if target_matches:
            if isinstance(value, ast.List):
                return len(value.elts)
            return None
    return None


def check_committed_ledger_script_is_sane(diff: set[str]) -> list[str]:
    """Independent of assert_domains_sane(): that function checks the
    trusted executing copy; this checks what the change actually proposes to
    commit, by reading it from Git rather than the working tree (which CI
    has already overwritten) or executing it. Not waivable by exemption.

    Reads the *index* (`git show :path`), not `HEAD:path`. In CI the index
    always matches HEAD (a clean checkout, nothing staged), so this is
    unchanged there. Locally, `diff` (see changed_paths()) can already be
    "yes, SELF_PATH is part of the prospective change" purely from a staged-
    but-not-yet-committed edit; reading HEAD in that situation inspects the
    old, pre-staged content and misses a staged weakening entirely until
    after it is already committed - found by adversarial review, not
    theoretical.
    """
    if SELF_PATH not in diff:
        return []
    result = subprocess.run(
        ["git", "show", f":{SELF_PATH}"],
        cwd=ROOT, capture_output=True, text=True,
    )
    if result.returncode != 0:
        return [f"{SELF_PATH} is in the diff but could not be read from the index for inspection."]
    count = _count_ledger_domains_in_source(result.stdout)
    if count is None:
        return [
            f"{SELF_PATH}'s proposed content has no statically-parseable LEDGER_DOMAINS "
            "list. Could be a syntax error or a deliberate restructure to hide from this check."
        ]
    if count < MINIMUM_DOMAIN_COUNT:
        return [
            f"{SELF_PATH}'s proposed content would leave LEDGER_DOMAINS with only {count} "
            f"entries (expected at least {MINIMUM_DOMAIN_COUNT}). This cannot be waived by a "
            "Ledger-Exempt: trailer — raise a human decision instead."
        ]
    return []


def main() -> int:
    sanity_problems = assert_domains_sane()
    if sanity_problems:
        print("Change-ledger check failed — the checker's own domains are not sane:\n")
        print("\n".join(f"  - {p}" for p in sanity_problems))
        print(
            "\nThis check cannot be waived by a Ledger-Exempt: trailer. If LEDGER_DOMAINS "
            "was deliberately reduced, raise a human decision, not a trailer."
        )
        return 1

    all_files = tracked_files()

    orphaned = check_pattern_coverage(all_files)
    if orphaned:
        print("Change-ledger check failed — a domain pattern is orphaned (likely a rename/move):\n")
        print("\n".join(f"  - {o}" for o in orphaned))
        print("\nUpdate the pattern in tools/validate_change_ledger.py to match the new location.")
        return 1

    diff = changed_paths()
    if not diff:
        print("No branch diff against origin/main found; skipping (not on a feature branch or origin/main unavailable).")
        return 0

    self_problems = check_committed_ledger_script_is_sane(diff)
    if self_problems:
        print("Change-ledger check failed — the proposed change to this checker is not sane:\n")
        print("\n".join(f"  - {p}" for p in self_problems))
        return 1

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
