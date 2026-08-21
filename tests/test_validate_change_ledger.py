"""Regression tests for tools/validate_change_ledger.py.

These lock in three fixes found by adversarial review of PR #21 (the Flight
Control extraction) before merge - see that file's module docstring
"Local-preflight-specific notes" and ENGINE_CHANGELOG.md's matching entry.
None of the three affect CI (CI never stages beyond HEAD and never sets the
pending-exemption variable); each test proves that concretely by asserting
what the *old* logic would have done alongside what the fixed logic does.
"""

from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "tools" / "validate_change_ledger.py"
SPEC = importlib.util.spec_from_file_location("campaign_simulation_validate_change_ledger", MODULE_PATH)
assert SPEC and SPEC.loader
vcl = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = vcl
SPEC.loader.exec_module(vcl)


class CampaignSimulationChangeLedgerTests(unittest.TestCase):
    def _git(self, repo: Path, *args: str, env: dict[str, str] | None = None) -> str:
        result = subprocess.run(
            ["git", "-C", str(repo), *args], capture_output=True, text=True, env=env
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout

    def _init_repo(self, repo: Path) -> None:
        self._git(repo, "init", "-q", "-b", "main")
        self._git(repo, "config", "user.email", "test@example.com")
        self._git(repo, "config", "user.name", "Campaign Simulation Test")

    def _write(self, repo: Path, path: str, content: str) -> None:
        target = repo / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")

    def _commit(self, repo: Path, message: str, *, add_all: bool = True) -> None:
        if add_all:
            self._git(repo, "add", "-A")
        self._git(repo, "commit", "-q", "-m", message)

    def _fake_origin_main_at_head(self, repo: Path) -> None:
        # A throwaway repo with no real remote: point refs/remotes/origin/main
        # at the current HEAD directly, which is enough for merge-base and
        # diff purposes without needing an actual second repository. Safe
        # here specifically because this repo is a fresh TemporaryDirectory
        # with no worktrees sharing its ref database - unlike a worktree of
        # the real repository, where mutating this ref would corrupt it for
        # every worktree sharing that .git.
        head = self._git(repo, "rev-parse", "HEAD").strip()
        self._git(repo, "update-ref", "refs/remotes/origin/main", head)

    def test_staged_revert_of_ledger_paired_with_new_sensitive_change_is_caught(self) -> None:
        """Finding: an already-committed ledger update must not paper over a
        later staged revert of that same update alongside a new, unrelated
        sensitive change. The old union-of-path-names logic missed this; the
        prospective-tree (`git write-tree`) diff does not."""
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            self._init_repo(repo)
            self._write(repo, "CHANGELOG.md", "base\n")
            self._write(repo, "src/main.py", "base\n")
            self._commit(repo, "init")
            self._fake_origin_main_at_head(repo)

            # Commit 1: legitimately touches CHANGELOG.md alongside a
            # sensitive change - satisfies the domain on its own.
            self._write(repo, "CHANGELOG.md", "base\n\n- did the first thing\n")
            self._write(repo, "src/main.py", "first change\n")
            self._git(repo, "add", "CHANGELOG.md", "src/main.py")
            self._commit(repo, "first sensitive change, with changelog")

            with mock.patch.object(vcl, "ROOT", repo):
                self.assertIn("CHANGELOG.md", vcl.changed_paths())

                # Now stage a revert of CHANGELOG.md back to its pre-commit-1
                # content, while staging a second, different sensitive
                # change. Nothing has been committed yet for this second
                # change.
                self._write(repo, "CHANGELOG.md", "base\n")
                self._write(repo, "src/main.py", "first change\n\nsecond change\n")
                self._git(repo, "add", "CHANGELOG.md", "src/main.py")

                # The old union-based logic would still see CHANGELOG.md in
                # the committed-history path list from commit 1 and wrongly
                # call the domain satisfied.
                merge_base = self._git(repo, "merge-base", "HEAD", "origin/main").strip()
                committed = self._git(repo, "diff", "--name-only", f"{merge_base}..HEAD")
                staged = self._git(repo, "diff", "--cached", "--name-only")
                old_union = {line for line in (committed + staged).splitlines() if line}
                self.assertIn(
                    "CHANGELOG.md", old_union,
                    "test setup sanity check: the old logic's blind spot must be reproduced",
                )

                # The fixed logic diffs the merge-base against the
                # prospective (write-tree) tree and correctly excludes
                # CHANGELOG.md, since it nets out unchanged relative to the
                # merge base.
                diff = vcl.changed_paths()
                self.assertNotIn("CHANGELOG.md", diff)
                self.assertIn("src/main.py", diff)

    def test_index_weakening_is_caught_even_when_disk_was_reverted(self) -> None:
        """Finding: check_committed_ledger_script_is_sane() must read the
        staged index, not HEAD, or a weakened self-checker that is staged
        but not yet committed - while the working tree happens to show safe
        content - passes silently until it is already committed."""
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            self._init_repo(repo)
            safe_checker = (
                'LEDGER_DOMAINS: list[tuple[str, list[str]]] = [\n'
                '    ("CHANGELOG.md", ["src/*"]),\n'
                '    ("ENGINE_CHANGELOG.md", ["src/*"]),\n'
                '    ("AGENT_HANDOFF.md", ["scripts/*"]),\n'
                ']\n'
            )
            self._write(repo, "tools/validate_change_ledger.py", safe_checker)
            self._commit(repo, "init")
            self._fake_origin_main_at_head(repo)

            weak_checker = 'LEDGER_DOMAINS: list[tuple[str, list[str]]] = [\n    ("CHANGELOG.md", ["src/*"]),\n]\n'
            self._write(repo, "tools/validate_change_ledger.py", weak_checker)
            self._git(repo, "add", "tools/validate_change_ledger.py")
            # Disk now reverted back to safe content without re-staging -
            # the index still holds the weakened version, which is exactly
            # what `git commit` (no -a) would actually commit.
            self._write(repo, "tools/validate_change_ledger.py", safe_checker)

            index_content = self._git(repo, "show", ":tools/validate_change_ledger.py")
            self.assertIn('"CHANGELOG.md", ["src/*"])', index_content)
            self.assertNotIn("ENGINE_CHANGELOG.md", index_content)

            with mock.patch.object(vcl, "ROOT", repo):
                diff = vcl.changed_paths()
                self.assertIn("tools/validate_change_ledger.py", diff)
                problems = vcl.check_committed_ledger_script_is_sane(diff)
                self.assertTrue(
                    problems,
                    "the staged (index) weakening must be caught even though disk shows safe content",
                )
                self.assertIn("only 1 entries", problems[0])

    def test_pending_exempt_env_var_is_local_only_and_does_not_leak(self) -> None:
        """Finding: the permanent Ledger-Exempt trailer cannot exist yet at
        preflight time (preflight runs before `git commit`), so a genuine
        first-time exemption could never produce COMMIT-READY through the
        primary local path. The fix must be strictly local-only: absent by
        default, and never confused with a real committed trailer."""
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            self._init_repo(repo)
            self._write(repo, "CHANGELOG.md", "base\n")
            self._commit(repo, "init")
            self._fake_origin_main_at_head(repo)

            with mock.patch.object(vcl, "ROOT", repo):
                saved = os.environ.pop("CAMPAIGN_SIMULATION_PENDING_LEDGER_EXEMPT", None)
                try:
                    self.assertEqual(vcl.exempted_ledgers(), set())

                    os.environ["CAMPAIGN_SIMULATION_PENDING_LEDGER_EXEMPT"] = (
                        "Ledger-Exempt: CHANGELOG.md test-only change"
                    )
                    self.assertEqual(vcl.exempted_ledgers(), {"CHANGELOG.md"})
                finally:
                    if saved is None:
                        os.environ.pop("CAMPAIGN_SIMULATION_PENDING_LEDGER_EXEMPT", None)
                    else:
                        os.environ["CAMPAIGN_SIMULATION_PENDING_LEDGER_EXEMPT"] = saved

                # Once unset again (the real CI environment never sets it),
                # behavior returns to exactly the committed-trailer-only path.
                self.assertEqual(vcl.exempted_ledgers(), set())

    def test_ci_like_state_is_unaffected_by_any_of_the_three_fixes(self) -> None:
        """A clean checkout (nothing staged, index == HEAD, no pending-exempt
        variable) must behave identically to before these fixes: only
        genuinely committed changes count, and only real committed trailers
        exempt them."""
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            self._init_repo(repo)
            self._write(repo, "CHANGELOG.md", "base\n")
            self._write(repo, "src/main.py", "base\n")
            self._commit(repo, "init")
            self._fake_origin_main_at_head(repo)

            self._write(repo, "src/main.py", "sensitive change, no changelog\n")
            self._git(repo, "add", "src/main.py")
            self._commit(repo, "sensitive change without ledger update")

            with mock.patch.object(vcl, "ROOT", repo):
                saved = os.environ.pop("CAMPAIGN_SIMULATION_PENDING_LEDGER_EXEMPT", None)
                try:
                    diff = vcl.changed_paths()
                    self.assertEqual(diff, {"src/main.py"})
                    self.assertEqual(vcl.exempted_ledgers(), set())
                finally:
                    if saved is not None:
                        os.environ["CAMPAIGN_SIMULATION_PENDING_LEDGER_EXEMPT"] = saved


if __name__ == "__main__":
    unittest.main()
