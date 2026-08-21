from __future__ import annotations

import contextlib
import hashlib
import importlib.util
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "preflight_commit.py"
SPEC = importlib.util.spec_from_file_location("campaign_simulation_preflight_commit", MODULE_PATH)
assert SPEC and SPEC.loader
preflight = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = preflight
SPEC.loader.exec_module(preflight)

# When this suite runs as part of Flight Control's required checks (see
# scripts/preflight_commit.py's materialized_staged_tree), ROOT above
# resolves to an isolated, index-materialized snapshot with no .git of its
# own by design. A few tests below are inherently about real Git checkout
# mechanics rather than staged file content and need the real, git-backed
# repository instead; run_required_checks passes its path via
# CAMPAIGN_SIMULATION_REPO_ROOT. A direct/manual test run (where ROOT already has a
# .git) falls back to ROOT unchanged.
REAL_ROOT = Path(os.environ.get("CAMPAIGN_SIMULATION_REPO_ROOT", str(ROOT)))


def completed(returncode: int = 0, stdout: str = "", stderr: str = ""):
    return preflight.subprocess.CompletedProcess(
        args=[],
        returncode=returncode,
        stdout=stdout,
        stderr=stderr,
    )


def hook_run_side_effect(hooks_path: str = ".githooks", staged_mode: str | None = "100755"):
    # A preflight._run stand-in that answers both queries assert_hook_is_active
    # makes - the effective core.hooksPath config lookup and the staged Git
    # index mode lookup for the hook - distinctly, by inspecting the git
    # subcommand. A single blanket return value cannot do this once both
    # checks exist: reusing one canned response for every call would make the
    # staged-mode lookup misparse the hooksPath answer as a mode, or vice
    # versa. staged_mode=None simulates the hook not being tracked in the
    # index at all (git ls-files -s finds nothing).
    def _side_effect(root, args, **kwargs):
        args = tuple(args)
        if args[:2] == ("config", "--get"):
            return completed(returncode=0, stdout=f"{hooks_path}\n")
        if args[:1] == ("ls-files",):
            if staged_mode is None:
                return completed(returncode=0, stdout="")
            path = f"{preflight.EXPECTED_HOOKS_PATH}/{preflight.EXPECTED_HOOK_FILENAME}"
            return completed(
                returncode=0,
                stdout=f"{staged_mode} 0000000000000000000000000000000000000000 0\t{path}\n",
            )
        return completed(returncode=0, stdout="")

    return _side_effect


# A synthetic trusted hook body, distinct from the real repository hook, so
# these tests exercise the identity check itself rather than depending on
# the real .githooks/pre-commit content staying byte-for-byte in sync. Tests
# that need to be "the accepted hook" patch preflight.EXPECTED_HOOK_SHA256 to
# TRUSTED_HOOK_SHA256 for the duration of the test.
TRUSTED_HOOK_BYTES = b"#!/bin/sh\nexec python3 scripts/preflight_commit.py --verify-marker\n"
TRUSTED_HOOK_SHA256 = hashlib.sha256(TRUSTED_HOOK_BYTES).hexdigest()

# A CRLF checkout of the otherwise-identical trusted hook content. This must
# be rejected, not accepted: CRLF in the shebang line ("#!/bin/sh\r") breaks
# exec on POSIX shells, so the identity check must fail closed on it rather
# than normalizing it away as equivalent to the LF original.
CRLF_TRUSTED_HOOK_BYTES = TRUSTED_HOOK_BYTES.replace(b"\n", b"\r\n")

INERT_HOOK_BYTES = b"#!/bin/sh\nexit 0\n"
MARKERS_ONLY_IN_COMMENT_HOOK_BYTES = (
    b"#!/bin/sh\n"
    b"# calls preflight_commit.py --verify-marker in spirit only\n"
    b"exit 0\n"
)
MARKERS_SPLIT_ACROSS_LINES_HOOK_BYTES = (
    b"#!/bin/sh\n"
    b"exec python3 scripts/preflight_commit.py\n"
    b'exec_marker="--verify-marker"\n'
)
ECHO_INSTEAD_OF_INVOCATION_HOOK_BYTES = (
    b"#!/bin/sh\n"
    b"echo preflight_commit.py --verify-marker\n"
    b"exit 0\n"
)


class CampaignSimulationPreflightTests(unittest.TestCase):
    def test_protected_branch_is_rejected(self) -> None:
        with mock.patch.object(preflight, "_git_text", return_value="main\n"):
            with self.assertRaises(preflight.PreflightStop) as ctx:
                preflight.current_branch(Path("."))
        self.assertEqual(ctx.exception.code, "PROTECTED-BRANCH")

    def test_non_feature_branch_is_rejected(self) -> None:
        with mock.patch.object(preflight, "_git_text", return_value="random-scratch-branch\n"):
            with self.assertRaises(preflight.PreflightStop) as ctx:
                preflight.current_branch(Path("."))
        self.assertEqual(ctx.exception.code, "NON-FEATURE-BRANCH")

    def test_each_allowed_branch_prefix_is_accepted(self) -> None:
        # Regression guard for the adaptation away from Mission10/The-Test's
        # single "agent/" prefix: every prefix this repository's own
        # INSTALLATION_GUIDE.md documents must actually be accepted, not
        # just "agent/".
        for prefix in preflight.ALLOWED_BRANCH_PREFIXES:
            branch = f"{prefix}example"
            with mock.patch.object(preflight, "_git_text", return_value=f"{branch}\n"):
                self.assertEqual(preflight.current_branch(Path(".")), branch)

    def test_stale_branch_fails_closed(self) -> None:
        with (
            mock.patch.object(preflight, "resolve_origin_main", return_value="a" * 40),
            mock.patch.object(preflight, "_run", return_value=completed(returncode=1)),
        ):
            with self.assertRaises(preflight.PreflightStop) as ctx:
                preflight.assert_current_with_origin_main(Path("."))
        self.assertEqual(ctx.exception.code, "BRANCH-STALE")

    def test_unstaged_changes_fail_closed(self) -> None:
        responses = iter((b"README.md\0", b"", b"AGENT_HANDOFF.md\0"))
        with (
            mock.patch.object(preflight, "_tracked_paths_with_hidden_index_bits", return_value=()),
            mock.patch.object(preflight, "_staged_paths_with_clean_filter", return_value=()),
            mock.patch.object(
                preflight, "_git_bytes", side_effect=lambda *args, **kwargs: next(responses)
            ),
        ):
            with self.assertRaises(preflight.PreflightStop) as ctx:
                preflight.assert_clean_staging_area(Path("."))
        self.assertEqual(ctx.exception.code, "UNSTAGED-CHANGES")

    def test_untracked_files_fail_closed(self) -> None:
        responses = iter((b"", b"scratch.txt\0", b"AGENT_HANDOFF.md\0"))
        with (
            mock.patch.object(preflight, "_tracked_paths_with_hidden_index_bits", return_value=()),
            mock.patch.object(preflight, "_staged_paths_with_clean_filter", return_value=()),
            mock.patch.object(
                preflight, "_git_bytes", side_effect=lambda *args, **kwargs: next(responses)
            ),
        ):
            with self.assertRaises(preflight.PreflightStop) as ctx:
                preflight.assert_clean_staging_area(Path("."))
        self.assertEqual(ctx.exception.code, "UNTRACKED-FILES")

    def test_staged_clean_filter_fails_closed_before_diff_based_checks(self) -> None:
        # A filter=<name> gitattribute's clean driver can make a staged
        # blob differ from the raw working-tree bytes run_required_checks
        # reads, invisibly to the diff-based unstaged-changes check below -
        # so this must be checked, and must block, first.
        with (
            mock.patch.object(preflight, "_tracked_paths_with_hidden_index_bits", return_value=()),
            mock.patch.object(
                preflight, "_staged_paths_with_clean_filter", return_value=("f.py",)
            ),
            mock.patch.object(
                preflight,
                "_git_bytes",
                side_effect=AssertionError("diff-based checks must not run first"),
            ),
        ):
            with self.assertRaises(preflight.PreflightStop) as ctx:
                preflight.assert_clean_staging_area(Path("."))
        self.assertEqual(ctx.exception.code, "STAGED-CLEAN-FILTER-CONFIGURED")

    def test_staged_paths_with_clean_filter_parses_check_attr_output(self) -> None:
        sample = b"f.py\0filter\0redact\0plain.py\0filter\0unspecified\0"
        with (
            mock.patch.object(preflight, "staged_paths", return_value=("f.py", "plain.py")),
            mock.patch.object(preflight, "_git_bytes", return_value=sample),
        ):
            filtered = preflight._staged_paths_with_clean_filter(Path("."))
        self.assertEqual(filtered, ("f.py",))

    def test_staged_paths_with_clean_filter_empty_when_no_staged_paths(self) -> None:
        with (
            mock.patch.object(preflight, "staged_paths", return_value=()),
            mock.patch.object(
                preflight, "_git_bytes", side_effect=AssertionError("must not query git")
            ),
        ):
            filtered = preflight._staged_paths_with_clean_filter(Path("."))
        self.assertEqual(filtered, ())

    def test_hidden_index_bit_fails_closed_before_diff_based_checks(self) -> None:
        # assume-unchanged/skip-worktree must be checked - and must block -
        # before assert_clean_staging_area trusts `git diff --name-only` at
        # all, since either bit is exactly what makes that diff unreliable.
        with (
            mock.patch.object(
                preflight, "_tracked_paths_with_hidden_index_bits", return_value=("f.txt",)
            ),
            mock.patch.object(
                preflight,
                "_git_bytes",
                side_effect=AssertionError("diff-based checks must not run first"),
            ),
        ):
            with self.assertRaises(preflight.PreflightStop) as ctx:
                preflight.assert_clean_staging_area(Path("."))
        self.assertEqual(ctx.exception.code, "HIDDEN-INDEX-WORKTREE-DIVERGENCE")

    def test_tracked_paths_with_hidden_index_bits_parses_ls_files_v_tags(self) -> None:
        # `git ls-files -v` tags: uppercase H is a normal cached entry (not
        # hidden); lowercase indicates assume-unchanged; "S" indicates
        # skip-worktree. Only the latter two are hidden-divergence risks.
        sample = "H normal.txt\nh assume_unchanged.txt\nS skip_worktree.txt\n? untracked.txt\n"
        with mock.patch.object(preflight, "_git_text", return_value=sample):
            hidden = preflight._tracked_paths_with_hidden_index_bits(Path("."))
        self.assertEqual(hidden, ("assume_unchanged.txt", "skip_worktree.txt"))

    def test_tracked_paths_with_hidden_index_bits_empty_when_all_normal(self) -> None:
        sample = "H a.txt\nH b.txt\n"
        with mock.patch.object(preflight, "_git_text", return_value=sample):
            hidden = preflight._tracked_paths_with_hidden_index_bits(Path("."))
        self.assertEqual(hidden, ())

    def test_changed_snapshot_during_checks_does_not_write_marker(self) -> None:
        before = preflight.StagedSnapshot(
            branch="agent/test",
            head="1" * 40,
            origin_main="2" * 40,
            diff_sha256="a" * 64,
            files=("A.md",),
        )
        after = preflight.StagedSnapshot(
            branch="agent/test",
            head="1" * 40,
            origin_main="2" * 40,
            diff_sha256="b" * 64,
            files=("A.md",),
        )
        with (
            mock.patch.object(preflight, "current_branch", return_value="agent/test"),
            mock.patch.object(preflight, "assert_hook_is_active"),
            mock.patch.object(preflight, "assert_clean_staging_area"),
            mock.patch.object(preflight, "assert_staged_diff_is_clean"),
            mock.patch.object(preflight, "assert_current_with_origin_main", return_value="2" * 40),
            mock.patch.object(preflight, "run_required_checks"),
            mock.patch.object(preflight, "resolve_origin_main", return_value="2" * 40),
            mock.patch.object(preflight, "staged_snapshot", side_effect=[before, after]),
            mock.patch.object(preflight, "write_marker") as write_marker,
        ):
            with self.assertRaises(preflight.PreflightStop) as ctx:
                preflight.run_preflight(Path("."))
        self.assertEqual(ctx.exception.code, "WORKTREE-CHANGED-DURING-CHECKS")
        write_marker.assert_not_called()

    def test_failed_required_checker_fails_closed(self) -> None:
        with (
            mock.patch.object(
                preflight.subprocess,
                "run",
                return_value=completed(returncode=1, stderr="synthetic failure"),
            ),
            mock.patch.object(
                preflight,
                "materialized_staged_tree",
                return_value=contextlib.nullcontext(Path(".")),
            ),
        ):
            with self.assertRaises(preflight.PreflightStop) as ctx:
                preflight.run_required_checks(Path("."))
        self.assertEqual(ctx.exception.code, "CHECK-FAILED")

    def test_hook_path_not_configured_fails_closed(self) -> None:
        with mock.patch.object(preflight, "_run", return_value=completed(returncode=1, stdout="")):
            with self.assertRaises(preflight.PreflightStop) as ctx:
                preflight.assert_hook_is_active(Path("."))
        self.assertEqual(ctx.exception.code, "HOOK-PATH-NOT-CONFIGURED")

    def test_hook_path_wrong_value_fails_closed(self) -> None:
        with mock.patch.object(
            preflight, "_run", return_value=completed(returncode=0, stdout="some/other/path\n")
        ):
            with self.assertRaises(preflight.PreflightStop) as ctx:
                preflight.assert_hook_is_active(Path("."))
        self.assertEqual(ctx.exception.code, "HOOK-PATH-NOT-CONFIGURED")

    def test_hook_path_check_queries_effective_git_config_not_local_scope(self) -> None:
        # A repository with extensions.worktreeConfig enabled can define a
        # higher-priority core.hooksPath in worktree-scoped config. Querying
        # with --local would miss that override; the effective (unscoped)
        # query must be used instead so Git's own precedence applies.
        captured_args: list[tuple[str, ...]] = []
        base_side_effect = hook_run_side_effect()

        def fake_run(root, args, **kwargs):
            captured_args.append(tuple(args))
            return base_side_effect(root, args, **kwargs)

        with (
            mock.patch.object(preflight, "_run", side_effect=fake_run),
            mock.patch.object(preflight.Path, "is_file", return_value=True),
            mock.patch.object(preflight, "_is_windows", return_value=True),
            mock.patch.object(preflight.Path, "read_bytes", return_value=TRUSTED_HOOK_BYTES),
            mock.patch.object(preflight, "EXPECTED_HOOK_SHA256", TRUSTED_HOOK_SHA256),
        ):
            preflight.assert_hook_is_active(Path("."))  # must not raise

        hooks_path_calls = [args for args in captured_args if "core.hooksPath" in args]
        self.assertTrue(hooks_path_calls)
        for args in hooks_path_calls:
            self.assertNotIn("--local", args)
            self.assertIn("--get", args)

    def test_effective_hooks_path_overridden_elsewhere_fails_closed(self) -> None:
        # Simulates Git resolving an effective core.hooksPath that differs
        # from the intended value, e.g. a worktree-scoped override pointing
        # at a different directory than the versioned .githooks/ hook.
        with mock.patch.object(
            preflight, "_run", return_value=completed(returncode=0, stdout="worktree/other-hooks\n")
        ):
            with self.assertRaises(preflight.PreflightStop) as ctx:
                preflight.assert_hook_is_active(Path("."))
        self.assertEqual(ctx.exception.code, "HOOK-PATH-NOT-CONFIGURED")

    def test_hook_file_missing_fails_closed(self) -> None:
        with (
            mock.patch.object(preflight, "_run", return_value=completed(returncode=0, stdout=".githooks\n")),
            mock.patch.object(preflight.Path, "is_file", return_value=False),
        ):
            with self.assertRaises(preflight.PreflightStop) as ctx:
                preflight.assert_hook_is_active(Path("."))
        self.assertEqual(ctx.exception.code, "HOOK-FILE-MISSING")

    def test_hook_not_executable_fails_closed_on_posix(self) -> None:
        with (
            mock.patch.object(preflight, "_run", return_value=completed(returncode=0, stdout=".githooks\n")),
            mock.patch.object(preflight.Path, "is_file", return_value=True),
            mock.patch.object(preflight, "_is_windows", return_value=False),
            mock.patch.object(preflight.os, "access", return_value=False),
        ):
            with self.assertRaises(preflight.PreflightStop) as ctx:
                preflight.assert_hook_is_active(Path("."))
        self.assertEqual(ctx.exception.code, "HOOK-NOT-EXECUTABLE")

    def test_staged_hook_index_mode_downgrade_fails_closed(self) -> None:
        # With core.fileMode=false, an index-only mode change
        # (100755 -> 100644) leaves the working-tree file's real permission
        # bits untouched, so the os.access()/is_windows()-gated check above
        # alone would still see it as executable. The committed hook is the
        # staged index entry, not the working-tree file, so this must be
        # checked and must fail closed independent of the working tree.
        with (
            mock.patch.object(
                preflight, "_run", side_effect=hook_run_side_effect(staged_mode="100644")
            ),
            mock.patch.object(preflight.Path, "is_file", return_value=True),
            mock.patch.object(preflight, "_is_windows", return_value=True),
            mock.patch.object(preflight.Path, "read_bytes", return_value=TRUSTED_HOOK_BYTES),
            mock.patch.object(preflight, "EXPECTED_HOOK_SHA256", TRUSTED_HOOK_SHA256),
        ):
            with self.assertRaises(preflight.PreflightStop) as ctx:
                preflight.assert_hook_is_active(Path("."))
        self.assertEqual(ctx.exception.code, "HOOK-STAGED-MODE-NOT-EXECUTABLE")

    def test_staged_hook_not_tracked_in_index_fails_closed(self) -> None:
        # git ls-files -s finding nothing for the hook path (e.g. it was
        # never staged, or the index is otherwise inconsistent) must also
        # fail closed rather than being treated as "no mode change".
        with (
            mock.patch.object(
                preflight, "_run", side_effect=hook_run_side_effect(staged_mode=None)
            ),
            mock.patch.object(preflight.Path, "is_file", return_value=True),
            mock.patch.object(preflight, "_is_windows", return_value=True),
            mock.patch.object(preflight.Path, "read_bytes", return_value=TRUSTED_HOOK_BYTES),
            mock.patch.object(preflight, "EXPECTED_HOOK_SHA256", TRUSTED_HOOK_SHA256),
        ):
            with self.assertRaises(preflight.PreflightStop) as ctx:
                preflight.assert_hook_is_active(Path("."))
        self.assertEqual(ctx.exception.code, "HOOK-STAGED-MODE-NOT-EXECUTABLE")

    def test_staged_hook_index_mode_executable_is_accepted(self) -> None:
        # The positive counterpart: a normally staged, executable
        # (100755) hook with matching trusted content must still pass.
        with (
            mock.patch.object(
                preflight, "_run", side_effect=hook_run_side_effect(staged_mode="100755")
            ),
            mock.patch.object(preflight.Path, "is_file", return_value=True),
            mock.patch.object(preflight, "_is_windows", return_value=True),
            mock.patch.object(preflight.Path, "read_bytes", return_value=TRUSTED_HOOK_BYTES),
            mock.patch.object(preflight, "EXPECTED_HOOK_SHA256", TRUSTED_HOOK_SHA256),
        ):
            preflight.assert_hook_is_active(Path("."))  # must not raise

    def test_hook_with_inert_exit_zero_script_fails_closed(self) -> None:
        # A replaced hook that is present and executable, but no longer
        # matches the trusted versioned hook's content (e.g. edited down to
        # a bare `exit 0`), must not be accepted as an active guard.
        with (
            mock.patch.object(preflight, "_run", side_effect=hook_run_side_effect()),
            mock.patch.object(preflight.Path, "is_file", return_value=True),
            mock.patch.object(preflight, "_is_windows", return_value=True),
            mock.patch.object(preflight.Path, "read_bytes", return_value=INERT_HOOK_BYTES),
        ):
            with self.assertRaises(preflight.PreflightStop) as ctx:
                preflight.assert_hook_is_active(Path("."))
        self.assertEqual(ctx.exception.code, "HOOK-CONTRACT-MISMATCH")

    def test_hook_with_markers_only_in_comment_fails_closed(self) -> None:
        # A hook can be replaced with an inert stub while leaving the
        # trusted hook's marker strings behind in a decorative comment. A
        # text/marker heuristic could be fooled by this; a content-identity
        # check cannot, because the bytes differ from the trusted hook.
        with (
            mock.patch.object(preflight, "_run", side_effect=hook_run_side_effect()),
            mock.patch.object(preflight.Path, "is_file", return_value=True),
            mock.patch.object(preflight, "_is_windows", return_value=True),
            mock.patch.object(
                preflight.Path, "read_bytes", return_value=MARKERS_ONLY_IN_COMMENT_HOOK_BYTES
            ),
        ):
            with self.assertRaises(preflight.PreflightStop) as ctx:
                preflight.assert_hook_is_active(Path("."))
        self.assertEqual(ctx.exception.code, "HOOK-CONTRACT-MISMATCH")

    def test_hook_with_markers_split_across_unrelated_lines_fails_closed(self) -> None:
        # Both marker strings are present in the file, but on separate,
        # unrelated lines rather than the trusted hook's exact content.
        with (
            mock.patch.object(preflight, "_run", side_effect=hook_run_side_effect()),
            mock.patch.object(preflight.Path, "is_file", return_value=True),
            mock.patch.object(preflight, "_is_windows", return_value=True),
            mock.patch.object(
                preflight.Path, "read_bytes", return_value=MARKERS_SPLIT_ACROSS_LINES_HOOK_BYTES
            ),
        ):
            with self.assertRaises(preflight.PreflightStop) as ctx:
                preflight.assert_hook_is_active(Path("."))
        self.assertEqual(ctx.exception.code, "HOOK-CONTRACT-MISMATCH")

    def test_hook_with_echo_instead_of_invocation_fails_closed(self) -> None:
        # A hook that merely echoes the marker strings on a single
        # non-comment line (rather than the trusted hook's actual
        # invocation) is exactly the demonstrated bypass of a text-based
        # same-line marker check. A content-identity check rejects it
        # because its bytes are not the trusted hook's bytes, regardless of
        # what strings that line happens to contain.
        with (
            mock.patch.object(preflight, "_run", side_effect=hook_run_side_effect()),
            mock.patch.object(preflight.Path, "is_file", return_value=True),
            mock.patch.object(preflight, "_is_windows", return_value=True),
            mock.patch.object(
                preflight.Path, "read_bytes", return_value=ECHO_INSTEAD_OF_INVOCATION_HOOK_BYTES
            ),
        ):
            with self.assertRaises(preflight.PreflightStop) as ctx:
                preflight.assert_hook_is_active(Path("."))
        self.assertEqual(ctx.exception.code, "HOOK-CONTRACT-MISMATCH")

    def test_hook_with_crlf_line_endings_fails_closed(self) -> None:
        # A checkout that produced CRLF line endings for the otherwise
        # byte-identical trusted hook (e.g. .gitattributes not honored, or a
        # tool that rewrites line endings after checkout) must fail closed.
        # CRLF is a real content difference - "#!/bin/sh\r" breaks exec on
        # POSIX shells - not a cosmetic variation to normalize away.
        with (
            mock.patch.object(preflight, "_run", side_effect=hook_run_side_effect()),
            mock.patch.object(preflight.Path, "is_file", return_value=True),
            mock.patch.object(preflight, "_is_windows", return_value=True),
            mock.patch.object(preflight.Path, "read_bytes", return_value=CRLF_TRUSTED_HOOK_BYTES),
            mock.patch.object(preflight, "EXPECTED_HOOK_SHA256", TRUSTED_HOOK_SHA256),
        ):
            with self.assertRaises(preflight.PreflightStop) as ctx:
                preflight.assert_hook_is_active(Path("."))
        self.assertEqual(ctx.exception.code, "HOOK-CONTRACT-MISMATCH")

    def test_hook_with_crlf_line_endings_and_different_content_fails_closed(self) -> None:
        # A hook that is both rewritten (the inert stub) and CRLF-terminated
        # must fail closed for the same content-identity reason as any other
        # rewritten hook, independent of the CRLF-specific case above.
        with (
            mock.patch.object(preflight, "_run", side_effect=hook_run_side_effect()),
            mock.patch.object(preflight.Path, "is_file", return_value=True),
            mock.patch.object(preflight, "_is_windows", return_value=True),
            mock.patch.object(
                preflight.Path,
                "read_bytes",
                return_value=INERT_HOOK_BYTES.replace(b"\n", b"\r\n"),
            ),
            mock.patch.object(preflight, "EXPECTED_HOOK_SHA256", TRUSTED_HOOK_SHA256),
        ):
            with self.assertRaises(preflight.PreflightStop) as ctx:
                preflight.assert_hook_is_active(Path("."))
        self.assertEqual(ctx.exception.code, "HOOK-CONTRACT-MISMATCH")

    def test_hook_with_lf_line_endings_matching_trusted_content_is_accepted(self) -> None:
        # The positive counterpart to the CRLF-rejection tests above: the
        # exact trusted LF bytes, unmodified, must still be accepted. This
        # guards against a fix for CRLF rejection accidentally becoming
        # over-strict (e.g. rejecting valid LF content too).
        with (
            mock.patch.object(preflight, "_run", side_effect=hook_run_side_effect()),
            mock.patch.object(preflight.Path, "is_file", return_value=True),
            mock.patch.object(preflight, "_is_windows", return_value=True),
            mock.patch.object(preflight.Path, "read_bytes", return_value=TRUSTED_HOOK_BYTES),
            mock.patch.object(preflight, "EXPECTED_HOOK_SHA256", TRUSTED_HOOK_SHA256),
        ):
            preflight.assert_hook_is_active(Path("."))  # must not raise

    def test_pinned_hook_identity_matches_versioned_repository_hook(self) -> None:
        # The trusted identity constant is deliberately pinned, not derived:
        # legitimately changing the versioned .githooks/pre-commit hook must
        # require deliberately updating EXPECTED_HOOK_SHA256 (and this test)
        # in the same change, not merely editing the hook file.
        real_hook_path = ROOT / preflight.EXPECTED_HOOKS_PATH / preflight.EXPECTED_HOOK_FILENAME
        actual_hash = preflight._hook_content_sha256(real_hook_path)
        self.assertEqual(actual_hash, preflight.EXPECTED_HOOK_SHA256)

    def test_gitattributes_pins_hook_directory_to_lf(self) -> None:
        # Since the content-identity check no longer normalizes CRLF, the
        # repository must prevent CRLF from being produced by a checkout in
        # the first place. This asserts Git itself resolves the versioned
        # hook's checkout line ending to LF via .gitattributes, on any
        # platform/config, independent of the identity check above.
        hook_relpath = f"{preflight.EXPECTED_HOOKS_PATH}/{preflight.EXPECTED_HOOK_FILENAME}"
        result = subprocess.run(
            # --cached: consult .gitattributes from REAL_ROOT's staged
            # index, not its live working tree. Without it, a staged
            # deletion of .gitattributes with an ignored survivor left on
            # disk would still read that survivor and report eol: lf even
            # though the committed tree carries no LF guarantee at all.
            ["git", "-C", str(REAL_ROOT), "check-attr", "--cached", "text", "eol", "--", hook_relpath],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(f"{hook_relpath}: text: set", result.stdout)
        self.assertIn(f"{hook_relpath}: eol: lf", result.stdout)

    def test_gitattributes_check_uses_staged_index_not_live_worktree_survivor(self) -> None:
        # Regression case for the Codex P2: an unscoped `git check-attr`
        # reads attributes from the live working tree, not the staged
        # index. If .gitattributes is staged for deletion while an
        # ignored/untracked survivor remains on disk, that survivor would
        # still be consulted - incorrectly reporting the LF pin as intact
        # even though the committed tree carries no such guarantee.
        # --cached must read the staged (now-absent) .gitattributes
        # instead, which is what test_gitattributes_pins_hook_directory_to_lf
        # above now uses.
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)

            def _git(*args: str) -> str:
                result = subprocess.run(
                    ["git", "-C", str(repo), *args], capture_output=True, text=True
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                return result.stdout

            _git("init", "-q")
            _git("config", "user.email", "test@example.com")
            _git("config", "user.name", "Campaign Simulation Test")
            hook_dir = repo / ".githooks"
            hook_dir.mkdir()
            (hook_dir / "pre-commit").write_text(
                "#!/bin/sh\nexit 0\n", encoding="utf-8", newline="\n"
            )
            (repo / ".gitattributes").write_text(
                ".githooks/pre-commit eol=lf\n", encoding="utf-8", newline="\n"
            )
            _git("add", ".gitattributes", ".githooks/pre-commit")
            _git("commit", "-q", "-m", "init")

            _git("rm", "--cached", "-q", ".gitattributes")
            (repo / ".gitignore").write_text(".gitattributes\n", encoding="utf-8")

            live = subprocess.run(
                ["git", "-C", str(repo), "check-attr", "eol", "--", ".githooks/pre-commit"],
                capture_output=True,
                text=True,
            )
            self.assertEqual(live.returncode, 0, live.stderr)
            self.assertIn("eol: lf", live.stdout)

            staged = subprocess.run(
                [
                    "git", "-C", str(repo), "check-attr", "--cached",
                    "eol", "--", ".githooks/pre-commit",
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(staged.returncode, 0, staged.stderr)
            self.assertNotIn("eol: lf", staged.stdout)

    def test_correctly_installed_hook_is_accepted_on_posix(self) -> None:
        with (
            mock.patch.object(preflight, "_run", side_effect=hook_run_side_effect()),
            mock.patch.object(preflight.Path, "is_file", return_value=True),
            mock.patch.object(preflight, "_is_windows", return_value=False),
            mock.patch.object(preflight.os, "access", return_value=True),
            mock.patch.object(preflight.Path, "read_bytes", return_value=TRUSTED_HOOK_BYTES),
            mock.patch.object(preflight, "EXPECTED_HOOK_SHA256", TRUSTED_HOOK_SHA256),
        ):
            preflight.assert_hook_is_active(Path("."))  # must not raise

    def test_correctly_installed_hook_is_accepted_on_windows_without_exec_bit(self) -> None:
        with (
            mock.patch.object(preflight, "_run", side_effect=hook_run_side_effect()),
            mock.patch.object(preflight.Path, "is_file", return_value=True),
            mock.patch.object(preflight, "_is_windows", return_value=True),
            mock.patch.object(preflight.os, "access", return_value=False),
            mock.patch.object(preflight.Path, "read_bytes", return_value=TRUSTED_HOOK_BYTES),
            mock.patch.object(preflight, "EXPECTED_HOOK_SHA256", TRUSTED_HOOK_SHA256),
        ):
            # Windows has no POSIX executable bit; the check must not block a
            # correctly installed hook there even if os.access(X_OK) is False.
            preflight.assert_hook_is_active(Path("."))  # must not raise

    def test_run_preflight_fails_closed_when_hook_not_active(self) -> None:
        with (
            mock.patch.object(preflight, "current_branch", return_value="agent/test"),
            mock.patch.object(
                preflight,
                "assert_hook_is_active",
                side_effect=preflight.PreflightStop("HOOK-PATH-NOT-CONFIGURED", "x"),
            ),
            mock.patch.object(preflight, "write_marker") as write_marker,
        ):
            with self.assertRaises(preflight.PreflightStop) as ctx:
                preflight.run_preflight(Path("."))
        self.assertEqual(ctx.exception.code, "HOOK-PATH-NOT-CONFIGURED")
        write_marker.assert_not_called()

    def test_run_preflight_reaches_write_marker_when_hook_is_active(self) -> None:
        snapshot = preflight.StagedSnapshot(
            branch="agent/test",
            head="1" * 40,
            origin_main="2" * 40,
            diff_sha256="a" * 64,
            files=("A.md",),
        )
        with (
            mock.patch.object(preflight, "current_branch", return_value="agent/test"),
            mock.patch.object(preflight, "assert_hook_is_active"),
            mock.patch.object(preflight, "assert_clean_staging_area"),
            mock.patch.object(preflight, "assert_staged_diff_is_clean"),
            mock.patch.object(preflight, "assert_current_with_origin_main", return_value="2" * 40),
            mock.patch.object(preflight, "run_required_checks"),
            mock.patch.object(preflight, "resolve_origin_main", return_value="2" * 40),
            mock.patch.object(preflight, "staged_snapshot", side_effect=[snapshot, snapshot]),
            mock.patch.object(preflight, "write_marker") as write_marker,
        ):
            preflight.run_preflight(Path("."))
        write_marker.assert_called_once_with(Path("."), snapshot)

    def test_required_checks_run_in_utf8_safe_child_environment(self) -> None:
        calls: list[dict[str, object]] = []

        def fake_run(command, **kwargs):
            calls.append(kwargs)
            return completed(returncode=0)

        fake_snapshot = Path("fake-snapshot")
        with (
            mock.patch.object(preflight.subprocess, "run", side_effect=fake_run),
            mock.patch.object(
                preflight,
                "materialized_staged_tree",
                return_value=contextlib.nullcontext(fake_snapshot),
            ),
        ):
            preflight.run_required_checks(Path("."))

        self.assertTrue(calls)
        for kwargs in calls:
            # Regression guard: child processes must not inherit a console/pipe
            # codec (e.g. Windows cp1252) that cannot encode non-ASCII output
            # from checks such as tools/validate_change_ledger.py.
            env = kwargs.get("env")
            self.assertIsNotNone(env)
            self.assertEqual(env.get("PYTHONIOENCODING"), "utf-8")
            self.assertEqual(env.get("PYTHONUTF8"), "1")
            self.assertEqual(kwargs.get("encoding"), "utf-8")
            self.assertEqual(kwargs.get("errors"), "replace")

    def test_required_checks_run_against_materialized_snapshot_not_live_root(self) -> None:
        # Regression guard for the architectural repair: the three
        # pure-file-content checks must run against the isolated
        # index-materialized snapshot, not the live working tree at `root`.
        # tools/validate_change_ledger.py is the deliberate exception: it
        # inherently needs real Git history (merge-base/diff/log against
        # origin/main), which the deliberately .git-less snapshot cannot
        # provide, so it must run directly against the real root instead.
        calls: list[dict[str, object]] = []
        commands: list[list[str]] = []

        def fake_run(command, **kwargs):
            commands.append(list(command))
            calls.append(kwargs)
            return completed(returncode=0)

        real_root = Path("real-root")
        fake_snapshot = Path("fake-snapshot")
        with (
            mock.patch.object(preflight.subprocess, "run", side_effect=fake_run),
            mock.patch.object(
                preflight,
                "materialized_staged_tree",
                return_value=contextlib.nullcontext(fake_snapshot),
            ),
        ):
            preflight.run_required_checks(real_root)

        ledger_calls = [
            (cmd, kwargs)
            for cmd, kwargs in zip(commands, calls)
            if any("validate_change_ledger.py" in str(part) for part in cmd)
        ]
        self.assertEqual(len(ledger_calls), 1)
        self.assertEqual(ledger_calls[0][1].get("cwd"), real_root)

        snapshot_calls = [
            (cmd, kwargs)
            for cmd, kwargs in zip(commands, calls)
            if not any("validate_change_ledger.py" in str(part) for part in cmd)
        ]
        self.assertTrue(snapshot_calls)
        for _cmd, kwargs in snapshot_calls:
            self.assertEqual(kwargs.get("cwd"), fake_snapshot)

    def test_ledger_check_always_runs_with_list_missing_domains(self) -> None:
        # No environment variable is ever set for the ledger subprocess -
        # see tools/validate_change_ledger.py's exempted_ledgers() docstring
        # for why that was rejected (a real CI bypass via workflow env).
        # --list-missing-domains is the only, safe signalling mechanism.
        def fake_run(command, **kwargs):
            if any("validate_change_ledger.py" in str(part) for part in command):
                self.assertIn("--list-missing-domains", command)
                self.assertNotIn(
                    "CAMPAIGN_SIMULATION_PENDING_LEDGER_EXEMPT", kwargs.get("env", {})
                )
                return completed(returncode=0)
            return completed(returncode=0)

        with (
            mock.patch.object(preflight.subprocess, "run", side_effect=fake_run),
            mock.patch.object(
                preflight, "materialized_staged_tree",
                return_value=contextlib.nullcontext(Path("fake-snapshot")),
            ),
        ):
            preflight.run_required_checks(Path("real-root"), pending_exempt=["CHANGELOG.md some reason"])

    def test_pending_exempt_only_covers_reported_missing_domains(self) -> None:
        # The coverage decision must be exact: every MISSING-DOMAIN: line
        # the checker reports must be named on --pending-exempt, or this
        # must still fail closed - it must never treat "some are covered"
        # as "good enough".
        def fake_run(command, **kwargs):
            if any("validate_change_ledger.py" in str(part) for part in command):
                return completed(
                    returncode=1,
                    stdout=(
                        "Change-ledger check failed:\n\n"
                        "  - CHANGELOG.md was not updated...\n"
                        "  - ENGINE_CHANGELOG.md was not updated...\n\n"
                        "MISSING-DOMAIN:CHANGELOG.md\n"
                        "MISSING-DOMAIN:ENGINE_CHANGELOG.md\n"
                    ),
                )
            return completed(returncode=0)

        with (
            mock.patch.object(preflight.subprocess, "run", side_effect=fake_run),
            mock.patch.object(
                preflight, "materialized_staged_tree",
                return_value=contextlib.nullcontext(Path("fake-snapshot")),
            ),
        ):
            # Only one of the two reported domains is covered - must still
            # raise, not silently pass.
            with self.assertRaises(preflight.PreflightStop) as ctx:
                preflight.run_required_checks(
                    Path("real-root"), pending_exempt=["CHANGELOG.md some reason"]
                )
            self.assertEqual(ctx.exception.code, "CHECK-FAILED")

        with (
            mock.patch.object(preflight.subprocess, "run", side_effect=fake_run),
            mock.patch.object(
                preflight, "materialized_staged_tree",
                return_value=contextlib.nullcontext(Path("fake-snapshot")),
            ),
        ):
            # Both reported domains are covered - now it may pass.
            preflight.run_required_checks(
                Path("real-root"),
                pending_exempt=["CHANGELOG.md some reason", "ENGINE_CHANGELOG.md some reason"],
            )

    def test_non_exemptable_ledger_failure_ignores_pending_exempt(self) -> None:
        # A failure with no MISSING-DOMAIN: lines at all (the sane-domains /
        # pattern-orphan / self-check categories) must never be treated as
        # coverable, no matter what --pending-exempt claims.
        def fake_run(command, **kwargs):
            if any("validate_change_ledger.py" in str(part) for part in command):
                return completed(
                    returncode=1,
                    stdout="Change-ledger check failed — the checker's own domains are not sane:\n\n  - ...\n",
                )
            return completed(returncode=0)

        with (
            mock.patch.object(preflight.subprocess, "run", side_effect=fake_run),
            mock.patch.object(
                preflight, "materialized_staged_tree",
                return_value=contextlib.nullcontext(Path("fake-snapshot")),
            ),
        ):
            with self.assertRaises(preflight.PreflightStop) as ctx:
                preflight.run_required_checks(
                    Path("real-root"), pending_exempt=["CHANGELOG.md some reason"]
                )
            self.assertEqual(ctx.exception.code, "CHECK-FAILED")

    def _valid_marker(
        self,
        *,
        version: int = preflight.MARKER_VERSION,
        created_at: int | None = None,
        diff_sha: str = "d" * 64,
    ) -> tuple[dict[str, object], preflight.StagedSnapshot]:
        snapshot = preflight.StagedSnapshot(
            branch="agent/test",
            head="1" * 40,
            origin_main="2" * 40,
            diff_sha256=diff_sha,
            files=("A.md",),
        )
        marker = {
            "marker_version": version,
            "created_at_epoch": int(time.time()) if created_at is None else created_at,
            "preflight_script_sha256": preflight.preflight_script_sha256(),
            "branch": snapshot.branch,
            "head": snapshot.head,
            "origin_main": snapshot.origin_main,
            "staged_diff_sha256": snapshot.diff_sha256,
            "staged_files": list(snapshot.files),
        }
        return marker, snapshot

    def test_expired_marker_fails_closed(self) -> None:
        marker, snapshot = self._valid_marker(
            created_at=int(time.time()) - preflight.MARKER_MAX_AGE_SECONDS - 10
        )
        with (
            mock.patch.object(preflight, "current_branch", return_value="agent/test"),
            mock.patch.object(preflight, "assert_clean_staging_area"),
            mock.patch.object(preflight, "_load_marker", return_value=marker),
            mock.patch.object(preflight, "resolve_origin_main", return_value=snapshot.origin_main),
            mock.patch.object(preflight, "staged_snapshot", return_value=snapshot),
        ):
            with self.assertRaises(preflight.PreflightStop) as ctx:
                preflight.verify_marker(Path("."))
        self.assertEqual(ctx.exception.code, "PREFLIGHT-MARKER-EXPIRED")

    def test_stale_marker_version_fails_closed(self) -> None:
        marker, snapshot = self._valid_marker(version=999)
        with (
            mock.patch.object(preflight, "current_branch", return_value="agent/test"),
            mock.patch.object(preflight, "assert_clean_staging_area"),
            mock.patch.object(preflight, "_load_marker", return_value=marker),
            mock.patch.object(preflight, "resolve_origin_main", return_value=snapshot.origin_main),
            mock.patch.object(preflight, "staged_snapshot", return_value=snapshot),
        ):
            with self.assertRaises(preflight.PreflightStop) as ctx:
                preflight.verify_marker(Path("."))
        self.assertEqual(ctx.exception.code, "PREFLIGHT-MARKER-STALE")

    def test_changed_staged_diff_blocks_commit_boundary(self) -> None:
        marker, snapshot = self._valid_marker()
        changed = preflight.StagedSnapshot(
            branch=snapshot.branch,
            head=snapshot.head,
            origin_main=snapshot.origin_main,
            diff_sha256="e" * 64,
            files=snapshot.files,
        )
        with (
            mock.patch.object(preflight, "current_branch", return_value="agent/test"),
            mock.patch.object(preflight, "assert_clean_staging_area"),
            mock.patch.object(preflight, "_load_marker", return_value=marker),
            mock.patch.object(preflight, "resolve_origin_main", return_value=snapshot.origin_main),
            mock.patch.object(preflight, "staged_snapshot", return_value=changed),
        ):
            with self.assertRaises(preflight.PreflightStop) as ctx:
                preflight.verify_marker(Path("."))
        self.assertEqual(ctx.exception.code, "PREFLIGHT-MARKER-MISMATCH")

    def test_guardrail_has_no_product_mutation_commands(self) -> None:
        source = MODULE_PATH.read_text(encoding="utf-8")
        forbidden = (
            '"commit"',
            '"push"',
            "commit_checkpoint(",
            "commit_manifest(",
            "validate_gated_checkpoint(",
        )
        for token in forbidden:
            self.assertNotIn(token, source)


@unittest.skipUnless(shutil.which("sh"), "sh is not available on PATH")
class CampaignSimulationPreCommitHookInterpreterSelectionTests(unittest.TestCase):
    """Exercises the real, versioned .githooks/pre-commit script (not a copy)
    with a minimal, controlled PATH so the interpreter it actually execs can
    be observed directly, rather than re-implementing its selection logic in
    Python and testing that instead."""

    HOOK_PATH = REAL_ROOT / preflight.EXPECTED_HOOKS_PATH / preflight.EXPECTED_HOOK_FILENAME

    @staticmethod
    def _write_executable(path: Path, body: str) -> None:
        path.write_text(body, encoding="utf-8", newline="\n")
        path.chmod(path.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)

    def _write_stub_interpreter(self, bin_dir: Path, name: str) -> None:
        # Prints which stub was invoked and its exact arguments, then exits
        # 0. Since the hook execs (not calls) the chosen interpreter, only
        # one stub's output can ever appear per run.
        self._write_executable(bin_dir / name, f'#!/bin/sh\necho "INVOKED:{name}:$*"\n')

    def _write_uname_stub(self, bin_dir: Path, kernel_name: str) -> None:
        self._write_executable(bin_dir / "uname", f'#!/bin/sh\necho "{kernel_name}"\n')

    def _write_git_wrapper(self, bin_dir: Path) -> None:
        # The hook itself calls plain "git", which must still resolve to the
        # real git - but real git's own directory (e.g. /usr/bin on many
        # Linux distributions) commonly also contains the system's real
        # python3, which would defeat the isolation this PATH is meant to
        # provide. Wrap the real, absolute git path instead of adding its
        # directory to PATH.
        real_git = shutil.which("git")
        assert real_git, "git must be resolvable to build the test's isolated PATH"
        self._write_executable(bin_dir / "git", f'#!/bin/sh\nexec "{real_git}" "$@"\n')

    def _minimal_path(self, bin_dir: Path) -> str:
        # Only the stub directory - not the ambient PATH, and not any real
        # directory that happens to also host git or sh - so real py/
        # python3/python installations on the test machine cannot mask the
        # behavior under test.
        return str(bin_dir)

    def _run_hook(self, bin_dir: Path) -> subprocess.CompletedProcess[str]:
        real_sh = shutil.which("sh")
        assert real_sh, "sh must be resolvable to run this test"
        env = dict(os.environ)
        env["PATH"] = self._minimal_path(bin_dir)
        return subprocess.run(
            [real_sh, str(self.HOOK_PATH)],
            cwd=str(REAL_ROOT),
            env=env,
            capture_output=True,
            text=True,
        )

    def test_windows_shell_uses_py_launcher(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            bin_dir = Path(tmp)
            self._write_git_wrapper(bin_dir)
            self._write_uname_stub(bin_dir, "MINGW64_NT-10.0-26200")
            self._write_stub_interpreter(bin_dir, "py")
            self._write_stub_interpreter(bin_dir, "python3")
            self._write_stub_interpreter(bin_dir, "python")
            result = self._run_hook(bin_dir)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(
            "INVOKED:py:-3 scripts/preflight_commit.py --verify-marker", result.stdout
        )
        self.assertNotIn("INVOKED:python3:", result.stdout)
        self.assertNotIn("INVOKED:python:", result.stdout)

    @unittest.skipIf(
        os.name == "nt",
        "Git for Windows' MSYS sh resolves 'uname' to a MINGW/MSYS-identifying "
        "string via its own runtime, independent of an isolated PATH override on "
        "this host - confirmed by a real Windows CI failure, not assumed. There is "
        "no reliable way to make sh believe it is running on a non-Windows kernel "
        "while it is actually on Windows. The behavior this test targets (ignoring "
        "an unrelated 'py' on a genuinely POSIX host) is still fully exercised on "
        "Linux/macOS CI, where no such override is needed in the first place.",
    )
    def test_posix_shell_ignores_unrelated_py_and_uses_python3(self) -> None:
        # This is the regression case for the P2: a "py" executable present
        # on a POSIX PATH must not be selected, since it may be unrelated to
        # the Windows launcher and reject "-3", which would otherwise block
        # every commit instead of falling through to python3/python.
        with tempfile.TemporaryDirectory() as tmp:
            bin_dir = Path(tmp)
            self._write_git_wrapper(bin_dir)
            self._write_uname_stub(bin_dir, "Linux")
            self._write_stub_interpreter(bin_dir, "py")
            self._write_stub_interpreter(bin_dir, "python3")
            result = self._run_hook(bin_dir)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(
            "INVOKED:python3:scripts/preflight_commit.py --verify-marker", result.stdout
        )
        self.assertNotIn("INVOKED:py:", result.stdout)

    @unittest.skipIf(
        os.name == "nt",
        "Same MSYS-runtime uname leak as "
        "test_posix_shell_ignores_unrelated_py_and_uses_python3 - see that test's "
        "skip reason. Fully exercised on Linux/macOS CI.",
    )
    def test_posix_shell_falls_back_to_python_when_python3_absent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            bin_dir = Path(tmp)
            self._write_git_wrapper(bin_dir)
            self._write_uname_stub(bin_dir, "Darwin")
            self._write_stub_interpreter(bin_dir, "py")
            self._write_stub_interpreter(bin_dir, "python")
            result = self._run_hook(bin_dir)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(
            "INVOKED:python:scripts/preflight_commit.py --verify-marker", result.stdout
        )
        self.assertNotIn("INVOKED:py:", result.stdout)
        self.assertNotIn("INVOKED:python3:", result.stdout)

    def test_fails_closed_when_no_interpreter_is_found(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            bin_dir = Path(tmp)
            self._write_git_wrapper(bin_dir)
            self._write_uname_stub(bin_dir, "Linux")
            result = self._run_hook(bin_dir)
        self.assertEqual(result.returncode, 1)
        self.assertIn("STOP-PYTHON-NOT-FOUND", result.stderr)


@unittest.skipUnless(
    shutil.which("git") and shutil.which("sh"), "git and sh must both be available"
)
class CampaignSimulationStagedSnapshotTextconvTests(unittest.TestCase):
    def _git(self, repo: Path, *args: str) -> str:
        result = subprocess.run(
            ["git", "-C", str(repo), *args], capture_output=True, text=True
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout

    def test_staged_diff_hash_ignores_textconv_and_detects_real_content_change(self) -> None:
        # This is the regression case for the P2: a diff.<driver>.textconv
        # filter (configured via .gitattributes) whose rendered output
        # stays constant must not make staged_snapshot's diff_sha256
        # identical across genuinely different staged content - that would
        # let a COMMIT-READY marker written for one staged diff silently
        # accept a swapped-in, unvalidated staged diff before the actual
        # commit, since _same_snapshot trusts this hash unchanged.
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            self._git(repo, "init", "-q")
            self._git(repo, "config", "user.email", "test@example.com")
            self._git(repo, "config", "user.name", "Campaign Simulation Test")
            self._git(repo, "config", "diff.constant.textconv", 'sh -c "printf CONSTANT"')
            (repo / ".gitattributes").write_text("f.bin diff=constant\n", encoding="utf-8", newline="\n")
            (repo / "f.bin").write_text("v1\n", encoding="utf-8", newline="\n")
            self._git(repo, "add", ".gitattributes", "f.bin")
            self._git(repo, "commit", "-q", "-m", "init")

            (repo / "f.bin").write_text("v2\n", encoding="utf-8", newline="\n")
            self._git(repo, "add", "f.bin")
            first = preflight.staged_snapshot(repo, branch="agent/test", origin_main="0" * 40)

            (repo / "f.bin").write_text("v3_completely_different\n", encoding="utf-8", newline="\n")
            self._git(repo, "add", "f.bin")
            second = preflight.staged_snapshot(repo, branch="agent/test", origin_main="0" * 40)

        self.assertNotEqual(first.diff_sha256, second.diff_sha256)


@unittest.skipUnless(
    shutil.which("git") and shutil.which("sh"), "git and sh must both be available"
)
class CampaignSimulationStagedSnapshotSubmoduleTests(unittest.TestCase):
    def _git(self, repo: Path, *args: str, env: dict[str, str] | None = None) -> str:
        result = subprocess.run(
            ["git", "-C", str(repo), *args], capture_output=True, text=True, env=env
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout

    def test_staged_diff_hash_ignores_diff_ignoresubmodules_config(self) -> None:
        # This is the regression case for the P2: a local diff.ignoreSubmodules
        # (or per-submodule ignore=) config of "all" makes `git diff` omit
        # staged gitlink (submodule pointer) changes entirely, so
        # staged_snapshot's diff_sha256 must not be fooled by it - a
        # submodule restaged at a different commit must change the hash
        # just like any other staged content change would.
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            sub = base / "sub"
            sub.mkdir()
            self._git(sub, "init", "-q")
            self._git(sub, "config", "user.email", "test@example.com")
            self._git(sub, "config", "user.name", "Campaign Simulation Test")
            sub_commits = []
            for value in ("v1", "v2", "v3"):
                (sub / "s.txt").write_text(f"{value}\n", encoding="utf-8", newline="\n")
                self._git(sub, "add", "s.txt")
                self._git(sub, "commit", "-q", "-m", value)
                sub_commits.append(self._git(sub, "rev-parse", "HEAD").strip())

            main = base / "main"
            main.mkdir()
            self._git(main, "init", "-q")
            self._git(main, "config", "user.email", "test@example.com")
            self._git(main, "config", "user.name", "Campaign Simulation Test")
            sub_url = str(sub).replace("\\", "/")
            allow_file_env = dict(os.environ, GIT_ALLOW_PROTOCOL="file")
            self._git(main, "submodule", "add", "-q", sub_url, "sub", env=allow_file_env)
            self._git(main, "commit", "-q", "-m", "add submodule")
            self._git(main, "config", "diff.ignoreSubmodules", "all")

            sub_worktree = main / "sub"
            self._git(sub_worktree, "checkout", "-q", sub_commits[0])
            self._git(main, "add", "sub")
            first = preflight.staged_snapshot(main, branch="agent/test", origin_main="0" * 40)

            self._git(sub_worktree, "checkout", "-q", sub_commits[2])
            self._git(main, "add", "sub")
            second = preflight.staged_snapshot(main, branch="agent/test", origin_main="0" * 40)

        self.assertNotEqual(first.diff_sha256, second.diff_sha256)


@unittest.skipUnless(shutil.which("git"), "git must be available")
class CampaignSimulationFreshnessReplaceRefTests(unittest.TestCase):
    def _git(self, repo: Path, *args: str) -> str:
        result = subprocess.run(
            ["git", "-C", str(repo), *args], capture_output=True, text=True
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout

    def test_git_replace_ref_does_not_fake_freshness_against_origin_main(self) -> None:
        # Regression case for the Codex P2: a local refs/replace/<sha> for
        # HEAD could make `merge-base --is-ancestor` traverse a forged
        # replacement commit graph and report origin/main as merged in
        # when the real, pushed HEAD does not actually contain it.
        # --no-replace-objects must make this gate see the real history.
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            origin_repo = base / "origin"
            origin_repo.mkdir()
            self._git(origin_repo, "init", "-q", "-b", "main")
            self._git(origin_repo, "config", "user.email", "test@example.com")
            self._git(origin_repo, "config", "user.name", "Campaign Simulation Test")
            (origin_repo / "a.txt").write_text("a\n", encoding="utf-8")
            self._git(origin_repo, "add", "a.txt")
            self._git(origin_repo, "commit", "-q", "-m", "origin main commit")
            origin_main_sha = self._git(origin_repo, "rev-parse", "HEAD").strip()

            local_repo = base / "local"
            local_repo.mkdir()
            self._git(local_repo, "init", "-q")
            self._git(local_repo, "config", "user.email", "test@example.com")
            self._git(local_repo, "config", "user.name", "Campaign Simulation Test")
            self._git(local_repo, "remote", "add", "origin", str(origin_repo))
            (local_repo / "b.txt").write_text("b\n", encoding="utf-8")
            self._git(local_repo, "add", "b.txt")
            self._git(local_repo, "commit", "-q", "-m", "unrelated local commit")
            head_sha = self._git(local_repo, "rev-parse", "HEAD").strip()

            # Sanity: without any replacement, the real history is stale.
            with self.assertRaises(preflight.PreflightStop) as ctx:
                preflight.assert_current_with_origin_main(local_repo)
            self.assertEqual(ctx.exception.code, "BRANCH-STALE")

            # Forge a replacement for HEAD whose parent is origin/main's
            # commit, so a replacement-honoring ancestry walk would
            # (incorrectly) see origin/main as merged in.
            head_tree = self._git(local_repo, "rev-parse", "HEAD^{tree}").strip()
            forged = subprocess.run(
                [
                    "git", "-C", str(local_repo), "commit-tree", head_tree,
                    "-p", origin_main_sha, "-m", "forged ancestry",
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(forged.returncode, 0, forged.stderr)
            forged_sha = forged.stdout.strip()
            self._git(local_repo, "replace", head_sha, forged_sha)

            # Confirm the replacement does what it claims to a
            # replacement-honoring merge-base, so this test would actually
            # have caught the regression before the fix.
            replacement_honored = subprocess.run(
                ["git", "-C", str(local_repo), "merge-base", "--is-ancestor",
                 origin_main_sha, "HEAD"],
                capture_output=True, text=True,
            )
            self.assertEqual(replacement_honored.returncode, 0)

            with self.assertRaises(preflight.PreflightStop) as ctx:
                preflight.assert_current_with_origin_main(local_repo)
            self.assertEqual(ctx.exception.code, "BRANCH-STALE")


class CampaignSimulationMaterializedStagedTreeTests(unittest.TestCase):
    def _git(self, repo: Path, *args: str) -> str:
        result = subprocess.run(
            ["git", "-C", str(repo), *args], capture_output=True, text=True
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout

    def _init_repo(self, repo: Path) -> None:
        self._git(repo, "init", "-q")
        self._git(repo, "config", "user.email", "test@example.com")
        self._git(repo, "config", "user.name", "Campaign Simulation Test")

    def _stage_symlink(self, repo: Path, path: str, target: str) -> None:
        # Stages a real Git symlink index entry (mode 120000) directly via
        # plumbing, independent of whether this OS/filesystem can create an
        # actual symlink - this keeps the regression test meaningful on
        # Windows, where core.symlinks is commonly false.
        blob = subprocess.run(
            ["git", "-C", str(repo), "hash-object", "-w", "--stdin"],
            input=target,
            capture_output=True,
            text=True,
        )
        self.assertEqual(blob.returncode, 0, blob.stderr)
        sha = blob.stdout.strip()
        self._git(repo, "update-index", "--add", "--cacheinfo", f"120000,{sha},{path}")

    def test_staged_deletion_is_absent_even_when_an_ignored_copy_survives_on_disk(self) -> None:
        # P2 class 1: `git rm --cached` stages a deletion but leaves the
        # file on disk. If that path is then (re)covered by .gitignore, it
        # is invisible to both the unstaged-diff check and the
        # --exclude-standard untracked-files check, yet a live-working-tree
        # validation run would still see and pass against its content. The
        # materialized snapshot must not contain it at all.
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            self._init_repo(repo)
            (repo / "secret.txt").write_text("committed-content\n", encoding="utf-8")
            self._git(repo, "add", "secret.txt")
            self._git(repo, "commit", "-q", "-m", "init")

            self._git(repo, "rm", "--cached", "-q", "secret.txt")
            (repo / ".gitignore").write_text("secret.txt\n", encoding="utf-8")

            self.assertTrue((repo / "secret.txt").exists())

            with preflight.materialized_staged_tree(repo) as snapshot_dir:
                self.assertFalse((snapshot_dir / "secret.txt").exists())

    def test_staged_symlink_is_materialized_without_resolving_into_ignored_content(self) -> None:
        # P2 class 2: a staged symlink's live working-tree resolution can
        # point at ignored/local content. The snapshot must never contain a
        # real OS symlink - only the recorded target text as inert file
        # content - so nothing can resolve outside the snapshot.
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            self._init_repo(repo)
            (repo / "README.md").write_text("base\n", encoding="utf-8")
            self._git(repo, "add", "README.md")
            self._git(repo, "commit", "-q", "-m", "init")

            (repo / "ignored_target.txt").write_text("LIVE-SECRET\n", encoding="utf-8")
            (repo / ".gitignore").write_text("ignored_target.txt\n", encoding="utf-8")
            self._stage_symlink(repo, "link.txt", "ignored_target.txt")

            with preflight.materialized_staged_tree(repo) as snapshot_dir:
                materialized = snapshot_dir / "link.txt"
                self.assertTrue(materialized.is_file())
                self.assertFalse(materialized.is_symlink())
                content = materialized.read_text(encoding="utf-8")
                self.assertEqual(content, "ignored_target.txt")
                self.assertNotIn("LIVE-SECRET", content)

    def test_materialized_content_comes_from_the_index_not_the_worktree(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            self._init_repo(repo)
            (repo / "f.txt").write_text("v0\n", encoding="utf-8")
            self._git(repo, "add", "f.txt")
            self._git(repo, "commit", "-q", "-m", "init")

            (repo / "f.txt").write_text("staged-content\n", encoding="utf-8")
            self._git(repo, "add", "f.txt")
            (repo / "f.txt").write_text("live-only-content\n", encoding="utf-8")

            with preflight.materialized_staged_tree(repo) as snapshot_dir:
                self.assertEqual(
                    (snapshot_dir / "f.txt").read_text(encoding="utf-8"),
                    "staged-content\n",
                )

    def test_ordinary_staged_file_is_materialized(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            self._init_repo(repo)
            nested = repo / "docs" / "note.md"
            nested.parent.mkdir(parents=True)
            nested.write_text("hello\n", encoding="utf-8")
            self._git(repo, "add", "docs/note.md")

            with preflight.materialized_staged_tree(repo) as snapshot_dir:
                self.assertEqual(
                    (snapshot_dir / "docs" / "note.md").read_text(encoding="utf-8"),
                    "hello\n",
                )
                self.assertFalse((snapshot_dir / ".git").exists())

    def test_snapshot_is_removed_after_successful_use(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            self._init_repo(repo)
            (repo / "f.txt").write_text("v0\n", encoding="utf-8")
            self._git(repo, "add", "f.txt")

            with preflight.materialized_staged_tree(repo) as snapshot_dir:
                self.assertTrue(snapshot_dir.exists())
            self.assertFalse(snapshot_dir.exists())

    def test_snapshot_is_removed_even_when_the_caller_raises(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            self._init_repo(repo)
            (repo / "f.txt").write_text("v0\n", encoding="utf-8")
            self._git(repo, "add", "f.txt")

            captured: list[Path] = []
            with self.assertRaises(RuntimeError):
                with preflight.materialized_staged_tree(repo) as snapshot_dir:
                    captured.append(snapshot_dir)
                    raise RuntimeError("synthetic failure during checks")
            self.assertTrue(captured)
            self.assertFalse(captured[0].exists())

    def test_staged_path_escape_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            snapshot_dir = Path(tmp) / "snapshot"
            snapshot_dir.mkdir()
            with self.assertRaises(preflight.PreflightStop) as ctx:
                preflight._resolve_staged_path(snapshot_dir, "../escaped.txt")
        self.assertEqual(ctx.exception.code, "STAGED-TREE-PATH-ESCAPE")

    def test_staged_export_ignore_attribute_does_not_hide_content(self) -> None:
        # Regression case for the Codex P2: `git archive` honors a staged
        # `export-ignore` gitattribute by silently omitting that path from
        # the archive, which would let genuinely staged content (here, a
        # secret-shaped literal) escape validation entirely. Materialization
        # must read straight from the object database (ls-tree/cat-file),
        # not archive, so nothing indexed can be skipped this way.
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            self._init_repo(repo)
            (repo / ".gitattributes").write_text(
                "leak.txt export-ignore\n", encoding="utf-8"
            )
            (repo / "leak.txt").write_text("staged-secret-content\n", encoding="utf-8")
            self._git(repo, "add", ".gitattributes", "leak.txt")

            with preflight.materialized_staged_tree(repo) as snapshot_dir:
                self.assertEqual(
                    (snapshot_dir / "leak.txt").read_text(encoding="utf-8"),
                    "staged-secret-content\n",
                )

    def test_non_utf8_staged_path_fails_closed_instead_of_colliding(self) -> None:
        # Regression case for the Codex P2: decoding staged paths with
        # errors="replace" could map two distinct non-UTF-8 byte sequences
        # (e.g. b"bad_\xfe.txt" and b"bad_\xff.txt") to the same
        # U+FFFD-substituted snapshot path, silently overwriting one
        # staged file's materialized content with the other's. Decoding
        # must fail closed instead of ever producing a lossy, collision-
        # prone path.
        with self.assertRaises(preflight.PreflightStop) as ctx:
            preflight._decode_staged_path(b"bad_\xfe.txt")
        self.assertEqual(ctx.exception.code, "STAGED-TREE-PATH-NOT-UTF8")

    def test_staged_gitlink_is_skipped_without_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            repo = base / "repo"
            repo.mkdir()
            self._init_repo(repo)
            self._git(repo, "update-index", "--add", "--cacheinfo", f"160000,{'a' * 40},sub")
            (repo / "f.txt").write_text("v0\n", encoding="utf-8")
            self._git(repo, "add", "f.txt")

            with preflight.materialized_staged_tree(repo) as snapshot_dir:
                self.assertFalse((snapshot_dir / "sub").exists())
                self.assertEqual(
                    (snapshot_dir / "f.txt").read_text(encoding="utf-8"), "v0\n"
                )

    def test_git_replace_ref_does_not_alter_materialized_blob_content(self) -> None:
        # Regression case for the Codex P2: `git cat-file blob <sha>`
        # honors a local `refs/replace/<sha>` by default, silently
        # substituting different content at read time even though the
        # committed tree still references the original blob. Materializing
        # must see the real staged content regardless of any local replace
        # ref.
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            self._init_repo(repo)
            (repo / "f.txt").write_text("BAD\n", encoding="utf-8")
            self._git(repo, "add", "f.txt")
            original_sha = self._git(repo, "rev-parse", ":f.txt").strip()

            replacement = subprocess.run(
                ["git", "-C", str(repo), "hash-object", "-w", "--stdin"],
                input="GOOD\n",
                capture_output=True,
                text=True,
            )
            self.assertEqual(replacement.returncode, 0, replacement.stderr)
            replacement_sha = replacement.stdout.strip()
            self._git(repo, "replace", original_sha, replacement_sha)

            with preflight.materialized_staged_tree(repo) as snapshot_dir:
                self.assertEqual(
                    (snapshot_dir / "f.txt").read_text(encoding="utf-8"), "BAD\n"
                )


if __name__ == "__main__":
    unittest.main()
