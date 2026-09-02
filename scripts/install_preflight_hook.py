#!/usr/bin/env python3
"""Enable Campaign-Simulation's versioned local pre-commit hook for this clone."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import preflight_commit


EXPECTED_HOOKS_PATH = ".githooks"
EXPECTED_HOOK_FILENAME = "pre-commit"


def repo_root() -> Path:
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode:
        raise RuntimeError(
            "STOP-NOT-A-REPOSITORY: Run this command from inside Campaign-Simulation."
        )
    return Path(result.stdout.strip()).resolve()


def effective_hooks_path(root: Path) -> str | None:
    # Deliberately unscoped: Git resolves system/global/local/worktree
    # config precedence itself for this query, the same way it does when
    # actually locating hooks to run. A --local-only read would miss a
    # higher-priority worktree-scoped core.hooksPath override.
    result = subprocess.run(
        ["git", "config", "--get", "core.hooksPath"],
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip() if result.returncode == 0 else None


def _local_hooks_path(root: Path) -> str | None:
    result = subprocess.run(
        ["git", "config", "--local", "--get", "core.hooksPath"],
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip() if result.returncode == 0 else None


def _restore_local_hooks_path(root: Path, previous: str | None) -> None:
    # Best-effort: this runs only while already failing closed, so a
    # restoration failure must not mask or replace the real error.
    if previous is None:
        subprocess.run(
            ["git", "config", "--local", "--unset", "core.hooksPath"],
            cwd=root,
            check=False,
            capture_output=True,
            text=True,
        )
    else:
        subprocess.run(
            ["git", "config", "--local", "core.hooksPath", previous],
            cwd=root,
            check=False,
            capture_output=True,
            text=True,
        )


def main() -> int:
    try:
        root = repo_root()
        hook = root / EXPECTED_HOOKS_PATH / EXPECTED_HOOK_FILENAME
        if not hook.is_file():
            raise RuntimeError(
                "STOP-HOOK-MISSING: The versioned Campaign-Simulation pre-commit hook is missing."
            )

        # Captured before the write below so any failure past this point
        # can restore whatever core.hooksPath was actually in effect
        # locally beforehand, instead of leaving the repository pointed at
        # a hooks path this installer itself just proved is unusable.
        previous_local_hooks_path = _local_hooks_path(root)

        def _fail(message: str) -> RuntimeError:
            _restore_local_hooks_path(root, previous_local_hooks_path)
            return RuntimeError(message)

        configured = subprocess.run(
            ["git", "config", "--local", "core.hooksPath", EXPECTED_HOOKS_PATH],
            cwd=root,
            check=False,
            capture_output=True,
            text=True,
        )
        if configured.returncode:
            raise _fail(
                "STOP-HOOK-INSTALL-FAILED: Git could not enable the local hook path."
            )

        effective = effective_hooks_path(root)
        if effective != EXPECTED_HOOKS_PATH:
            raise _fail(
                "STOP-EFFECTIVE-HOOK-PATH-SHADOWED: core.hooksPath was set to "
                f"{EXPECTED_HOOKS_PATH!r} in local scope, but a higher-precedence "
                "Git configuration (e.g. a worktree-scoped core.hooksPath) still "
                f"resolves the effective value to {effective!r}. Resolve that "
                "configuration manually; this installer will not override it."
            )

        # The checks above only prove core.hooksPath resolves to the
        # versioned hooks directory - not that the hook Git would actually
        # run there is usable. A hook that lost its executable bit, whose
        # content was corrupted, or whose staged index mode regressed would
        # still pass those checks here while assert_hook_is_active (the same
        # gate the real pre-commit hook enforces at commit time) rejects it
        # and Git silently skips a non-executable hook - so reuse that exact
        # check rather than reporting HOOK-READY for a setup that cannot
        # actually verify a commit.
        try:
            preflight_commit.assert_hook_is_active(root)
        except preflight_commit.PreflightStop as exc:
            raise _fail(f"STOP-{exc.code}: {exc.message}") from exc
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    print("HOOK-READY")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
