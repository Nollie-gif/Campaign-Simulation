from __future__ import annotations

import contextlib
import importlib.util
import io
import sys
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "install_preflight_hook.py"
SPEC = importlib.util.spec_from_file_location("campaign_simulation_install_preflight_hook", MODULE_PATH)
assert SPEC and SPEC.loader
installer = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = installer
SPEC.loader.exec_module(installer)


def completed(returncode: int = 0, stdout: str = "", stderr: str = ""):
    return installer.subprocess.CompletedProcess(
        args=[],
        returncode=returncode,
        stdout=stdout,
        stderr=stderr,
    )


class CampaignSimulationInstallerTests(unittest.TestCase):
    def _run_main(
        self,
        *,
        config_write_returncode: int,
        effective_stdout: str,
        hook_active_side_effect=None,
        initial_local_hooks_path: str | None = None,
    ):
        calls: list[tuple[str, ...]] = []
        # Simulates the actual local core.hooksPath value across the run,
        # so restore-on-failure behavior can be asserted precisely rather
        # than just inferred from call presence.
        state = {"local": initial_local_hooks_path}

        def fake_run(args, **kwargs):
            calls.append(tuple(args))
            # preflight_commit._run always inserts "-C <root>" (installer's
            # own calls never do); strip it before matching so one fake_run
            # can answer both modules' git invocations.
            normalized = list(args)
            if len(normalized) >= 2 and normalized[1] == "-C":
                normalized = [normalized[0]] + normalized[3:]
            if tuple(normalized[:2]) == ("git", "rev-parse"):
                return completed(returncode=0, stdout=str(ROOT) + "\n")
            if tuple(normalized[:4]) == ("git", "config", "--local", "--get"):
                value = state["local"]
                return completed(
                    returncode=0 if value is not None else 1,
                    stdout=f"{value}\n" if value is not None else "",
                )
            if tuple(normalized[:4]) == ("git", "config", "--local", "--unset"):
                state["local"] = None
                return completed(returncode=0)
            if tuple(normalized[:3]) == ("git", "config", "--local"):
                if config_write_returncode == 0:
                    state["local"] = normalized[4] if len(normalized) > 4 else ""
                return completed(returncode=config_write_returncode)
            if tuple(normalized[:3]) == ("git", "config", "--get"):
                return completed(returncode=0 if effective_stdout else 1, stdout=effective_stdout)
            raise AssertionError(f"unexpected command: {args}")

        with (
            mock.patch.object(installer.subprocess, "run", side_effect=fake_run),
            mock.patch.object(installer.Path, "is_file", return_value=True),
            mock.patch.object(
                installer.preflight_commit,
                "assert_hook_is_active",
                side_effect=hook_active_side_effect,
            ),
        ):
            code = installer.main()
        return code, calls, state

    def test_worktree_scoped_override_already_exists_fails_closed(self) -> None:
        # A worktree-scoped core.hooksPath ("other") outranks the local
        # value the installer just wrote ("`.githooks`"), so the effective
        # read-back must reflect "other" and installation must not report
        # HOOK-READY.
        code, _, _ = self._run_main(config_write_returncode=0, effective_stdout="other\n")
        self.assertEqual(code, 1)

    def test_local_hooks_path_shadowed_by_higher_precedence_scope_fails_closed(self) -> None:
        code, _, _ = self._run_main(config_write_returncode=0, effective_stdout="worktree/other-hooks\n")
        self.assertEqual(code, 1)

    def test_successful_effective_installation_reports_hook_ready(self) -> None:
        code, calls, _ = self._run_main(
            config_write_returncode=0, effective_stdout=f"{installer.EXPECTED_HOOKS_PATH}\n"
        )
        self.assertEqual(code, 0)
        write_calls = [c for c in calls if tuple(c[:3]) == ("git", "config", "--local")]
        self.assertTrue(write_calls)
        effective_calls = [c for c in calls if tuple(c[:3]) == ("git", "config", "--get")]
        self.assertTrue(effective_calls)
        for call in effective_calls:
            self.assertNotIn("--local", call)

    def test_repeated_installer_execution_is_idempotent(self) -> None:
        first_code, _, _ = self._run_main(
            config_write_returncode=0, effective_stdout=f"{installer.EXPECTED_HOOKS_PATH}\n"
        )
        second_code, _, _ = self._run_main(
            config_write_returncode=0, effective_stdout=f"{installer.EXPECTED_HOOKS_PATH}\n"
        )
        self.assertEqual(first_code, 0)
        self.assertEqual(second_code, 0)

    def test_failed_effective_read_back_never_reports_hook_ready(self) -> None:
        code, _, _ = self._run_main(config_write_returncode=0, effective_stdout="")
        self.assertEqual(code, 1)

    def test_local_hooks_path_restored_after_effective_shadow_failure(self) -> None:
        # Regression case for the Codex P2: when a later check fails after
        # the installer already wrote core.hooksPath locally, the
        # previously-active local value must be restored - not left
        # pointing at a hooks path this run itself just proved unusable
        # (a higher-precedence scope shadows it here).
        code, _, state = self._run_main(
            config_write_returncode=0,
            effective_stdout="worktree/other-hooks\n",
            initial_local_hooks_path="oldhooks",
        )
        self.assertEqual(code, 1)
        self.assertEqual(state["local"], "oldhooks")

    def test_local_hooks_path_unset_after_failure_when_none_was_previously_set(self) -> None:
        code, _, state = self._run_main(
            config_write_returncode=0,
            effective_stdout="worktree/other-hooks\n",
            initial_local_hooks_path=None,
        )
        self.assertEqual(code, 1)
        self.assertIsNone(state["local"])

    def test_local_hooks_path_restored_after_unusable_hook_failure(self) -> None:
        def hook_not_executable(root):
            raise installer.preflight_commit.PreflightStop(
                "HOOK-NOT-EXECUTABLE", "not executable"
            )

        code, _, state = self._run_main(
            config_write_returncode=0,
            effective_stdout=f"{installer.EXPECTED_HOOKS_PATH}\n",
            hook_active_side_effect=hook_not_executable,
            initial_local_hooks_path="oldhooks",
        )
        self.assertEqual(code, 1)
        self.assertEqual(state["local"], "oldhooks")

    def test_local_hooks_path_kept_on_success(self) -> None:
        code, _, state = self._run_main(
            config_write_returncode=0,
            effective_stdout=f"{installer.EXPECTED_HOOKS_PATH}\n",
            initial_local_hooks_path="oldhooks",
        )
        self.assertEqual(code, 0)
        self.assertEqual(state["local"], installer.EXPECTED_HOOKS_PATH)

    def test_hook_file_missing_fails_closed_before_writing_config(self) -> None:
        def fake_run(args, **kwargs):
            if tuple(args[:2]) == ("git", "rev-parse"):
                return completed(returncode=0, stdout=str(ROOT) + "\n")
            raise AssertionError(f"unexpected command: {args}")

        with (
            mock.patch.object(installer.subprocess, "run", side_effect=fake_run),
            mock.patch.object(installer.Path, "is_file", return_value=False),
        ):
            code = installer.main()
        self.assertEqual(code, 1)

    def test_local_config_write_failure_fails_closed(self) -> None:
        code, _, _ = self._run_main(config_write_returncode=1, effective_stdout="")
        self.assertEqual(code, 1)

    def test_unusable_hook_never_reports_hook_ready(self) -> None:
        # core.hooksPath resolving correctly is necessary but not
        # sufficient: a hook that lost its executable bit, whose content is
        # corrupted, or whose staged index mode regressed would pass every
        # check above while Git itself silently skips it at commit time.
        # The installer must reuse the same gate the real hook enforces
        # (assert_hook_is_active) and never report HOOK-READY when it fails.
        def hook_not_executable(root):
            raise installer.preflight_commit.PreflightStop(
                "HOOK-NOT-EXECUTABLE", "not executable"
            )

        with contextlib.redirect_stdout(io.StringIO()) as captured_stdout:
            code, _, _ = self._run_main(
                config_write_returncode=0,
                effective_stdout=f"{installer.EXPECTED_HOOKS_PATH}\n",
                hook_active_side_effect=hook_not_executable,
            )
        self.assertEqual(code, 1)
        self.assertNotIn("HOOK-READY", captured_stdout.getvalue())

    def test_installer_has_no_product_mutation_commands(self) -> None:
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


if __name__ == "__main__":
    unittest.main()
