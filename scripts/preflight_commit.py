#!/usr/bin/env python3
"""Deterministic local commit preflight for Campaign-Simulation repository engineering.

Extracted and adapted from the hardened Flight Control mechanism proven in
Mission10-Simulation-Sequel and The-Test (production use plus adversarial
review; see tests/test_preflight_commit.py and ENGINE_CHANGELOG.md). This
guardrail applies only to normal repository engineering commits — it does
not itself commit, push, merge, or perform any campaign-simulation runtime
mutation (checkpoint/manifest commit, publication). It verifies the exact
staged engineering change and writes short-lived COMMIT-READY evidence
under .git/ for the versioned pre-commit hook.

Trust boundary (found by adversarial review of this extraction — see
tests/test_preflight_commit.py and ENGINE_CHANGELOG.md's 2026-08-21 entries):
this script and the local pre-commit hook are a courtesy for a cooperating
committer, not a hardened security boundary. Anyone with write access to
their own working tree can edit this file, edit .githooks/pre-commit, or
run `git commit --no-verify` — there is no local root of trust that can
prevent someone from lying to their own local tools. The real, non-bypassable
boundary is server-side: the branch ruleset's required CI status checks, and
`tools/validate_change_ledger.py` being executed in CI from a trusted copy
fetched from `origin/main` rather than the pull request's own (possibly
weakened) copy. Do not treat a local COMMIT-READY as a security attestation;
treat it as a fast local echo of what CI will independently re-check.
"""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, Sequence


MARKER_VERSION = 1
MARKER_MAX_AGE_SECONDS = 15 * 60
# Campaign-Simulation's own established convention (INSTALLATION_GUIDE.md:
# "a focused feature, fix, hardening, test, or documentation branch") is
# broader than Mission10/The-Test's single "agent/" prefix. Adapted rather
# than copied: forcing this repository onto a foreign convention would
# reject its own already-documented, already-used branch names.
ALLOWED_BRANCH_PREFIXES = ("agent/", "feature/", "fix/", "hardening/", "test/", "docs/")
PROTECTED_BRANCHES = {"main", "master"}
EXPECTED_HOOKS_PATH = ".githooks"
EXPECTED_HOOK_FILENAME = "pre-commit"

# Trusted identity of the versioned .githooks/pre-commit hook, taken over its
# exact, unmodified bytes (see _hook_content_sha256). This is a content
# check, not a text/marker heuristic: any rewrite of the hook - comments,
# echoed marker strings, split markers, an inert exit-0 stub, or any other
# edit - changes this hash and fails closed, whether or not the rewritten
# text happens to still mention preflight_commit.py or --verify-marker.
# Line endings are part of that identity: a hook checked out with CRLF line
# endings (e.g. "#!/bin/sh\r") fails this check even though a naive
# LF-normalized comparison would call it equivalent, because CRLF in the
# shebang line breaks exec on POSIX shells and macOS/Linux CI. The
# repository's .gitattributes pins .githooks/pre-commit to eol=lf so a
# correct checkout never produces CRLF in the first place; this check does
# not compensate for a checkout that ignores that pin. Deliberately changing
# the versioned hook requires deliberately updating this constant and
# tests/test_preflight_commit.py's pinned-identity test in the same change.
EXPECTED_HOOK_SHA256 = "d1b7ef5f7693d6ec7bdbc8f663b6a0ac1418bce274707a22e6f8e39113cae75f"


class PreflightStop(RuntimeError):
    """A deliberate fail-closed stop in the engineering commit path."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True)
class StagedSnapshot:
    branch: str
    head: str
    origin_main: str
    diff_sha256: str
    files: tuple[str, ...]


def _run(
    root: Path,
    args: Sequence[str],
    *,
    text: bool = True,
) -> subprocess.CompletedProcess[str] | subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        ["git", "-C", str(root), *args],
        check=False,
        capture_output=True,
        text=text,
    )


def _git_text(root: Path, *args: str) -> str:
    result = _run(root, args)
    if result.returncode:
        raise PreflightStop("GIT-ERROR", "Git could not inspect the repository safely.")
    assert isinstance(result.stdout, str)
    return result.stdout


def _git_bytes(root: Path, *args: str) -> bytes:
    result = _run(root, args, text=False)
    if result.returncode:
        raise PreflightStop("GIT-ERROR", "Git could not inspect the repository safely.")
    assert isinstance(result.stdout, bytes)
    return result.stdout


def _nul_paths(raw: bytes) -> tuple[str, ...]:
    return tuple(part.decode("utf-8", errors="replace") for part in raw.split(b"\0") if part)


def find_repo_root() -> Path:
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode:
        raise PreflightStop(
            "NOT-A-REPOSITORY",
            "Run this command from inside Campaign-Simulation.",
        )
    return Path(result.stdout.strip()).resolve()


def current_branch(root: Path) -> str:
    branch = _git_text(root, "branch", "--show-current").strip()
    if not branch:
        raise PreflightStop("DETACHED-HEAD", "Check out a fresh feature branch before committing.")
    if branch in PROTECTED_BRANCHES:
        raise PreflightStop("PROTECTED-BRANCH", f"Direct commits to {branch} are not allowed.")
    if not branch.startswith(ALLOWED_BRANCH_PREFIXES):
        raise PreflightStop(
            "NON-FEATURE-BRANCH",
            "Normal Campaign-Simulation engineering commits must use a focused branch "
            f"prefixed with one of: {', '.join(ALLOWED_BRANCH_PREFIXES)}",
        )
    return branch


def _summarize(paths: tuple[str, ...]) -> str:
    shown = ", ".join(paths[:5])
    return shown if len(paths) <= 5 else f"{shown}, ... (+{len(paths) - 5})"


def staged_paths(root: Path) -> tuple[str, ...]:
    return _nul_paths(_git_bytes(root, "diff", "--cached", "--name-only", "-z"))


def _tracked_paths_with_hidden_index_bits(root: Path) -> tuple[str, ...]:
    # `git ls-files -v` tags every tracked path with a single status letter:
    # uppercase for a normal cached entry, lowercase if the assume-unchanged
    # bit is set on it, and "S" specifically for skip-worktree. Either bit
    # lets `git diff`/`git status` silently report no difference even when
    # the working tree genuinely differs from the blob Git will actually
    # commit - which would let run_required_checks validate different
    # content than what ends up staged, while assert_clean_staging_area's
    # `git diff --name-only` call below sees nothing to flag. Both bits are
    # therefore treated as a fail-closed condition, independent of whether
    # anything is currently staged.
    raw = _git_text(root, "ls-files", "-v")
    hidden: list[str] = []
    for line in raw.splitlines():
        if not line:
            continue
        tag, _, path = line.partition(" ")
        if tag == "S" or tag.islower():
            hidden.append(path)
    return tuple(hidden)


def _staged_paths_with_clean_filter(root: Path) -> tuple[str, ...]:
    # A `filter.<name>.clean` driver (set via a `filter=<name>` gitattribute)
    # transforms working-tree content into what `git add` actually stages.
    # The unstaged-changes check below (`git diff`, without --cached)
    # compares the index against that filtered working-tree content, not
    # the raw bytes run_required_checks reads from disk - so a clean filter
    # can make a real difference between the raw working tree and the
    # already-staged (filtered) blob invisible to that diff, letting checks
    # validate different content than what actually gets committed. Reject
    # any staged path with a filter configured rather than trying to safely
    # emulate or bypass it.
    paths = staged_paths(root)
    if not paths:
        return ()
    raw = _git_bytes(root, "check-attr", "-z", "filter", "--", *paths)
    fields = raw.split(b"\0")
    if fields and fields[-1] == b"":
        fields = fields[:-1]
    filtered: list[str] = []
    for i in range(0, len(fields) - 2, 3):
        path, _attr, value = fields[i], fields[i + 1], fields[i + 2]
        value_str = value.decode("utf-8", errors="replace")
        if value_str and value_str != "unspecified":
            filtered.append(path.decode("utf-8", errors="replace"))
    return tuple(filtered)


def assert_clean_staging_area(root: Path) -> tuple[str, ...]:
    hidden = _tracked_paths_with_hidden_index_bits(root)
    if hidden:
        raise PreflightStop(
            "HIDDEN-INDEX-WORKTREE-DIVERGENCE",
            "Tracked paths have the assume-unchanged or skip-worktree bit set, "
            "which can hide a real difference between the working tree and what "
            f"Git will actually commit: {_summarize(hidden)}. Clear these flags "
            "(git update-index --no-assume-unchanged / --no-skip-worktree) "
            "before committing.",
        )

    filtered = _staged_paths_with_clean_filter(root)
    if filtered:
        raise PreflightStop(
            "STAGED-CLEAN-FILTER-CONFIGURED",
            "Staged paths have a `filter=<name>` gitattribute (clean/smudge) "
            "configured, which can make the staged blob differ from the raw "
            f"working-tree bytes checks validate: {_summarize(filtered)}. Remove "
            "the filter configuration for these paths before committing.",
        )

    unstaged = _nul_paths(_git_bytes(root, "diff", "--name-only", "-z"))
    if unstaged:
        raise PreflightStop(
            "UNSTAGED-CHANGES",
            f"Stage or resolve tracked changes first: {_summarize(unstaged)}",
        )

    untracked = _nul_paths(_git_bytes(root, "ls-files", "--others", "--exclude-standard", "-z"))
    if untracked:
        raise PreflightStop(
            "UNTRACKED-FILES",
            f"Decide what to do with untracked files first: {_summarize(untracked)}",
        )

    staged = staged_paths(root)
    if not staged:
        raise PreflightStop(
            "NO-STAGED-CHANGES",
            "Stage the exact intended engineering files before running preflight.",
        )
    return staged


def assert_staged_diff_is_clean(root: Path) -> None:
    result = _run(root, ("diff", "--cached", "--check"))
    if result.returncode:
        raise PreflightStop(
            "INVALID-STAGED-DIFF",
            "The staged diff has whitespace errors.",
        )


def resolve_origin_main(root: Path, *, fetch: bool) -> str:
    if fetch:
        # Explicit destination refspec: fetching the bare name "main" only
        # updates refs/remotes/origin/main if remote.origin.fetch happens to
        # map it there. Writing the ref directly does not depend on that
        # configuration being present or unmodified.
        result = _run(
            root, ("fetch", "--quiet", "origin", "+refs/heads/main:refs/remotes/origin/main")
        )
        if result.returncode:
            raise PreflightStop(
                "FRESHNESS-UNKNOWN",
                "Could not refresh origin/main. Restore GitHub access and run preflight again.",
            )
    # --no-replace-objects: a local refs/replace/<sha> for origin/main's
    # commit object would otherwise let a replacement stand in for it -
    # including disguising a non-commit object as a commit for the
    # ^{commit} peel below - independent of what origin/main actually,
    # verifiably points to in the ref database.
    return _git_text(
        root, "--no-replace-objects", "rev-parse", "--verify", "origin/main^{commit}"
    ).strip()


def assert_current_with_origin_main(root: Path) -> str:
    origin_main = resolve_origin_main(root, fetch=True)
    # --no-replace-objects: see the P2 this closes - without it, a local
    # replacement for origin_main or HEAD could fabricate commit-graph
    # ancestry (e.g. via forged parents) and make this traversal report
    # the branch current when the real, pushed history is not.
    ancestry = _run(
        root, ("--no-replace-objects", "merge-base", "--is-ancestor", origin_main, "HEAD")
    )
    if ancestry.returncode:
        raise PreflightStop(
            "BRANCH-STALE",
            "Bring current origin/main into this feature branch before committing.",
        )
    return origin_main


def staged_snapshot(
    root: Path,
    *,
    branch: str | None = None,
    origin_main: str | None = None,
) -> StagedSnapshot:
    resolved_branch = branch or current_branch(root)
    resolved_origin_main = origin_main or resolve_origin_main(root, fetch=False)
    return StagedSnapshot(
        branch=resolved_branch,
        head=_git_text(root, "rev-parse", "HEAD").strip(),
        origin_main=resolved_origin_main,
        # --no-textconv: without it, a path with a configured
        # diff.<driver>.textconv filter (via .gitattributes) is hashed by
        # its textconv-rendered output, not its actual staged content. A
        # textconv driver whose rendered output stays constant makes this
        # hash identical across genuinely different staged content, letting
        # the COMMIT-READY marker's integrity check (_same_snapshot) accept
        # a swapped staged diff between preflight and commit time.
        # --ignore-submodules=none: without it, a local diff.ignoreSubmodules
        # (or per-submodule ignore=) config of "all" makes Git omit staged
        # gitlink (submodule pointer) changes from this diff entirely, so a
        # submodule could be restaged at a different commit without
        # changing this hash - the same class of blind spot as textconv.
        diff_sha256=hashlib.sha256(
            _git_bytes(
                root,
                "diff",
                "--cached",
                "--binary",
                "--no-ext-diff",
                "--no-textconv",
                "--ignore-submodules=none",
            )
        ).hexdigest(),
        files=staged_paths(root),
    )


def _git_dir(root: Path) -> Path:
    raw = Path(_git_text(root, "rev-parse", "--git-dir").strip())
    return raw if raw.is_absolute() else (root / raw).resolve()


def marker_path(root: Path) -> Path:
    return _git_dir(root) / "preflight" / "campaign-simulation-commit-ready.json"


def preflight_script_sha256() -> str:
    return hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


def write_marker(root: Path, snapshot: StagedSnapshot) -> None:
    path = marker_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "marker_version": MARKER_VERSION,
        "created_at_epoch": int(time.time()),
        "preflight_script_sha256": preflight_script_sha256(),
        "branch": snapshot.branch,
        "head": snapshot.head,
        "origin_main": snapshot.origin_main,
        "staged_diff_sha256": snapshot.diff_sha256,
        "staged_files": list(snapshot.files),
    }
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
    temporary.replace(path)


def _load_marker(root: Path) -> dict[str, object]:
    path = marker_path(root)
    if not path.is_file():
        raise PreflightStop(
            "PREFLIGHT-MARKER-MISSING",
            "Run scripts/preflight_commit.py before committing.",
        )
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise PreflightStop(
            "PREFLIGHT-MARKER-INVALID",
            "The local Campaign-Simulation preflight marker is invalid.",
        ) from exc
    if not isinstance(value, dict):
        raise PreflightStop(
            "PREFLIGHT-MARKER-INVALID",
            "The local Campaign-Simulation preflight marker is invalid.",
        )
    return value


def _same_snapshot(marker: dict[str, object], snapshot: StagedSnapshot) -> bool:
    return (
        marker.get("branch") == snapshot.branch
        and marker.get("head") == snapshot.head
        and marker.get("origin_main") == snapshot.origin_main
        and marker.get("staged_diff_sha256") == snapshot.diff_sha256
        and marker.get("staged_files") == list(snapshot.files)
    )


def verify_marker(root: Path) -> None:
    branch = current_branch(root)
    assert_clean_staging_area(root)
    marker = _load_marker(root)

    if marker.get("marker_version") != MARKER_VERSION:
        raise PreflightStop(
            "PREFLIGHT-MARKER-STALE",
            "The marker was created by a different Flight Control version.",
        )
    if marker.get("preflight_script_sha256") != preflight_script_sha256():
        raise PreflightStop(
            "PREFLIGHT-MARKER-STALE",
            "Flight Control changed after preflight ran.",
        )

    created_at = marker.get("created_at_epoch")
    if (
        not isinstance(created_at, int)
        or not 0 <= time.time() - created_at <= MARKER_MAX_AGE_SECONDS
    ):
        raise PreflightStop(
            "PREFLIGHT-MARKER-EXPIRED",
            "Run preflight again; COMMIT-READY evidence is valid for 15 minutes.",
        )

    local_origin_main = resolve_origin_main(root, fetch=False)
    snapshot = staged_snapshot(
        root,
        branch=branch,
        origin_main=local_origin_main,
    )
    if not _same_snapshot(marker, snapshot):
        raise PreflightStop(
            "PREFLIGHT-MARKER-MISMATCH",
            "Branch, HEAD, origin/main, or exact staged diff changed after preflight.",
        )


def _is_windows() -> bool:
    return os.name == "nt"


def _effective_hooks_path(root: Path) -> str | None:
    # Deliberately NOT scoped to --local: a repository with
    # extensions.worktreeConfig enabled can define a higher-priority
    # core.hooksPath in worktree-scoped config, which Git itself would use
    # instead of the local-scope value. Asking for the effective (unscoped)
    # value lets Git resolve that precedence instead of reimplementing it.
    result = _run(root, ("config", "--get", "core.hooksPath"))
    return result.stdout.strip() if result.returncode == 0 else None


def _hook_content_sha256(hook_path: Path) -> str | None:
    # No line-ending normalization: the trusted identity is over the exact
    # bytes on disk. A hook checked out with CRLF line endings is content
    # that differs from the versioned LF-only hook and must fail closed,
    # not be treated as equivalent - CRLF in "#!/bin/sh\r" breaks exec on
    # POSIX. .gitattributes pins the versioned hook to eol=lf so a correct
    # checkout never produces CRLF here.
    try:
        raw = hook_path.read_bytes()
    except OSError:
        return None
    return hashlib.sha256(raw).hexdigest()


REQUIRED_HOOK_INDEX_MODE = "100755"


def _staged_hook_index_mode(root: Path) -> str | None:
    # The Git index's recorded mode for the hook, independent of
    # core.fileMode and of the working-tree executable bit checked by
    # os.access() below. With core.fileMode=false, an index-only mode
    # change (100755 -> 100644) leaves the working-tree file's real
    # permission bits untouched, so os.access() alone would still see it as
    # executable even though the mode actually being committed is not. That
    # committed hook is then checked out non-executable on POSIX and
    # silently skips marker verification on every subsequent commit.
    result = _run(
        root, ("ls-files", "-s", "--", f"{EXPECTED_HOOKS_PATH}/{EXPECTED_HOOK_FILENAME}")
    )
    if result.returncode or not result.stdout.strip():
        return None
    return result.stdout.split()[0]


def assert_hook_is_active(root: Path) -> None:
    if _effective_hooks_path(root) != EXPECTED_HOOKS_PATH:
        raise PreflightStop(
            "HOOK-PATH-NOT-CONFIGURED",
            "Git's effective core.hooksPath for this worktree is not the "
            "versioned Campaign-Simulation hooks directory. Run "
            "scripts/install_preflight_hook.py before committing.",
        )

    hook_path = root / EXPECTED_HOOKS_PATH / EXPECTED_HOOK_FILENAME
    if not hook_path.is_file():
        raise PreflightStop(
            "HOOK-FILE-MISSING",
            "The versioned Campaign-Simulation pre-commit hook is missing from .githooks/. "
            "Run scripts/install_preflight_hook.py before committing.",
        )

    if not _is_windows() and not os.access(hook_path, os.X_OK):
        raise PreflightStop(
            "HOOK-NOT-EXECUTABLE",
            "The versioned Campaign-Simulation pre-commit hook is not executable. "
            "Run scripts/install_preflight_hook.py before committing.",
        )

    if _staged_hook_index_mode(root) != REQUIRED_HOOK_INDEX_MODE:
        raise PreflightStop(
            "HOOK-STAGED-MODE-NOT-EXECUTABLE",
            "The staged Git index mode for .githooks/pre-commit is not "
            f"{REQUIRED_HOOK_INDEX_MODE} (executable). This can happen with "
            "core.fileMode=false even while the working-tree file is still "
            "executable: the committed hook would lose its executable bit "
            "on a fresh checkout. Restore the hook's tracked executable "
            "mode (e.g. `git update-index --chmod=+x "
            f"{EXPECTED_HOOKS_PATH}/{EXPECTED_HOOK_FILENAME}`) before committing.",
        )

    if _hook_content_sha256(hook_path) != EXPECTED_HOOK_SHA256:
        raise PreflightStop(
            "HOOK-CONTRACT-MISMATCH",
            "The active pre-commit hook's content does not match the trusted "
            "versioned Campaign-Simulation hook identity. Restore the versioned hook or "
            "run scripts/install_preflight_hook.py.",
        )


def _utf8_child_env() -> dict[str, str]:
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    return env


SNAPSHOT_DIR_PREFIX = "campaign-simulation-flightcontrol-"


@contextlib.contextmanager
def materialized_staged_tree(root: Path) -> Iterator[Path]:
    """Materialize the CURRENT STAGED GIT INDEX into an isolated, temporary
    directory outside the repository, then always remove it.

    Required checks run against this snapshot instead of the live working
    tree, which closes two P2 classes the live tree cannot:

    - a staged deletion stays absent even when an ignored/untracked copy of
      the same path still physically exists in the working tree (`git
      write-tree`/`git ls-tree` on that tree emit only what the index
      actually records, independent of what else sits on disk);
    - a staged symlink can never resolve into ignored/local content: this
      snapshot never contains a real OS-level symlink. Every symlink entry
      is written as a plain file holding the index blob's literal target
      text, which is exactly what Git itself treats as that symlink's
      tracked "content" - so nothing here is ever resolved by the OS.

    Content is read blob-by-blob via `git ls-tree` + `git cat-file blob`,
    not `git archive`: archive applies attribute-driven transforms
    (`export-ignore` silently omits a staged path from the archive entirely,
    `export-subst` rewrites `$Format:...$` content) that would let genuinely
    staged content escape validation the same way the two P2s above did.
    `ls-tree`/`cat-file` are plain object-database reads with no such
    filtering.

    Every one of those reads passes `--no-replace-objects`: a local
    `refs/replace/<sha>` for a staged blob/tree would otherwise make Git
    silently substitute different content at read time, so required checks
    could validate content that is not what the committed tree actually
    references. Materialization must see exactly the real objects.

    No `.git` is copied; the snapshot is pure tracked/staged file content.
    """
    tree = _git_text(root, "--no-replace-objects", "write-tree").strip()

    snapshot_dir = Path(tempfile.mkdtemp(prefix=SNAPSHOT_DIR_PREFIX)).resolve()
    try:
        for mode, blob_sha, path in _staged_tree_entries(root, tree):
            if mode == "160000":
                # Submodule gitlink: a commit pointer, not blob content.
                continue
            if mode not in ("100644", "100755", "120000"):
                raise PreflightStop(
                    "STAGED-TREE-UNSUPPORTED-ENTRY",
                    f"Staged path {path!r} has unsupported Git mode {mode}.",
                )
            destination = _resolve_staged_path(snapshot_dir, path)
            destination.parent.mkdir(parents=True, exist_ok=True)
            # Written identically regardless of mode, including 120000
            # (symlink): a symlink blob's content IS its target path text,
            # and writing that as plain file bytes - never calling
            # os.symlink - is what keeps this snapshot free of any real
            # OS-level symlink that could resolve outside of it.
            destination.write_bytes(
                _git_bytes(root, "--no-replace-objects", "cat-file", "blob", blob_sha)
            )
        yield snapshot_dir
    finally:
        _remove_tree(snapshot_dir)


def _decode_staged_path(path_bytes: bytes) -> str:
    # Strict, not errors="replace": Git itself imposes no encoding on
    # index/tree paths, so two distinct, both-invalid-UTF-8 byte sequences
    # (e.g. b"bad_\xfe.txt" and b"bad_\xff.txt") could otherwise both
    # decode to the same U+FFFD-substituted snapshot path and silently
    # collide - one staged file's materialized content overwriting the
    # other's, so only one of the two ever gets validated. Failing closed
    # here matches how every other required check already treats staged
    # content as UTF-8 (see e.g. tools/validate_change_ledger.py's reads).
    try:
        return path_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise PreflightStop(
            "STAGED-TREE-PATH-NOT-UTF8",
            f"Staged path {path_bytes!r} is not valid UTF-8. Rename it "
            "before committing.",
        ) from exc


def _staged_tree_entries(root: Path, tree: str) -> Iterator[tuple[str, str, str]]:
    # `-r --full-tree`: every blob/gitlink at its full repo-relative path,
    # no intermediate tree entries. `-z`: NUL-terminated with no path
    # quoting, so this holds for any path bytes. `--no-replace-objects`:
    # see materialized_staged_tree's docstring - a local refs/replace/<sha>
    # for this tree must not substitute different content at read time.
    raw = _git_bytes(root, "--no-replace-objects", "ls-tree", "-r", "-z", "--full-tree", tree)
    for entry in raw.split(b"\0"):
        if not entry:
            continue
        meta, _, path_bytes = entry.partition(b"\t")
        mode_bytes, _type_bytes, sha_bytes = meta.split(b" ")
        yield (
            mode_bytes.decode("ascii"),
            sha_bytes.decode("ascii"),
            _decode_staged_path(path_bytes),
        )


def _resolve_staged_path(snapshot_dir: Path, staged_path: str) -> Path:
    candidate = (snapshot_dir / staged_path).resolve()
    if candidate != snapshot_dir and snapshot_dir not in candidate.parents:
        raise PreflightStop(
            "STAGED-TREE-PATH-ESCAPE",
            f"Staged tree entry {staged_path!r} resolves outside the "
            "isolated snapshot.",
        )
    return candidate


def _remove_tree(path: Path) -> None:
    def _on_error(func, target, exc_info):
        # Best-effort recovery for a read-only file/dir bit left by the
        # extraction (notably on Windows), so cleanup is not skipped.
        try:
            os.chmod(target, stat.S_IWRITE)
            func(target)
        except OSError:
            pass

    shutil.rmtree(path, onerror=_on_error)


def run_required_checks(root: Path, pending_exempt: Sequence[str] = ()) -> None:
    child_env = _utf8_child_env()
    # A handful of tests are inherently about real Git checkout mechanics
    # (the versioned pre-commit hook's actual interpreter-selection
    # behavior, .gitattributes-driven line-ending normalization) rather than
    # staged file content, and cannot be meaningfully exercised inside the
    # deliberately .git-less snapshot below. This tells them where the real,
    # git-backed repository is so they keep validating it directly.
    child_env["CAMPAIGN_SIMULATION_REPO_ROOT"] = str(root)
    with materialized_staged_tree(root) as snapshot_dir:
        # Without this, a child process (or a further subprocess it spawns,
        # e.g. the multi-process integration tests) resolves `campaign_simulation`
        # via whatever editable install happens to exist in the outer
        # environment - silently validating the real working tree's src/,
        # not the staged content actually materialized into this isolated
        # snapshot. Prepending the snapshot's own src/ makes the import
        # resolve to exactly what is staged, matching the whole point of
        # validating a snapshot rather than the live tree.
        snapshot_src = str(snapshot_dir / "src")
        child_env["PYTHONPATH"] = (
            snapshot_src + os.pathsep + child_env["PYTHONPATH"]
            if child_env.get("PYTHONPATH")
            else snapshot_src
        )
        # Pure file-content checks: safe to run against the isolated,
        # git-less snapshot, since none of them need real Git history.
        checks = (
            (
                "Campaign-Simulation unit tests",
                [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p", "test_*.py", "-v"],
            ),
            (
                "Blank template validation",
                [sys.executable, "tools/validate_blank_templates.py"],
            ),
            (
                "Artifact manifest validation",
                [sys.executable, "tools/validate_artifact_manifest.py"],
            ),
        )
        for name, command in checks:
            result = subprocess.run(
                command,
                cwd=snapshot_dir,
                check=False,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                env=child_env,
            )
            if result.returncode:
                diagnostic = (result.stderr or result.stdout).strip()
                if diagnostic:
                    print(diagnostic, file=sys.stderr)
                raise PreflightStop(
                    "CHECK-FAILED",
                    f"{name} failed. Resolve it before committing.",
                )
            print(f"CHECK-PASS: {name}")

    # tools/validate_change_ledger.py inherently needs real Git history
    # (merge-base, diff, log against origin/main) that the deliberately
    # .git-less materialized snapshot above cannot provide. Run it directly
    # against the real repository root instead of inside that snapshot.
    if pending_exempt:
        # The permanent, CI-enforced exemption mechanism is a commit-message
        # trailer, but that message does not exist yet at preflight time -
        # preflight runs *before* `git commit`. Without this, a legitimate
        # first-time exemption can never produce COMMIT-READY, because
        # nothing has been committed yet for the ledger check's git-log scan
        # to find (found by adversarial review, not theoretical). This env
        # var only ever affects this local, non-authoritative preflight
        # prediction; CI never sets it, and CI's own exempted_ledgers() scan
        # still requires the real trailer to be present in the actual
        # committed message, or CI fails regardless of what preflight said.
        child_env["CAMPAIGN_SIMULATION_PENDING_LEDGER_EXEMPT"] = "\n".join(
            f"Ledger-Exempt: {entry}" for entry in pending_exempt
        )
    ledger_result = subprocess.run(
        [sys.executable, "tools/validate_change_ledger.py"],
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=child_env,
    )
    if ledger_result.returncode:
        diagnostic = (ledger_result.stderr or ledger_result.stdout).strip()
        if diagnostic:
            print(diagnostic, file=sys.stderr)
        raise PreflightStop(
            "CHECK-FAILED",
            "Change ledger validation failed. Resolve it before committing.",
        )
    print("CHECK-PASS: Change ledger validation")


def run_preflight(root: Path, pending_exempt: Sequence[str] = ()) -> None:
    branch = current_branch(root)
    assert_hook_is_active(root)
    assert_clean_staging_area(root)
    assert_staged_diff_is_clean(root)
    origin_main = assert_current_with_origin_main(root)
    before = staged_snapshot(root, branch=branch, origin_main=origin_main)

    run_required_checks(root, pending_exempt)

    assert_clean_staging_area(root)
    assert_staged_diff_is_clean(root)
    after_origin_main = resolve_origin_main(root, fetch=False)
    if after_origin_main != origin_main:
        raise PreflightStop(
            "ORIGIN-MAIN-CHANGED",
            "origin/main changed while validation ran. Rebase/sync and rerun preflight.",
        )
    after = staged_snapshot(root, branch=branch, origin_main=after_origin_main)
    if before != after:
        raise PreflightStop(
            "WORKTREE-CHANGED-DURING-CHECKS",
            "The exact staged engineering scope changed while checks ran.",
        )

    write_marker(root, after)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Campaign-Simulation deterministic local engineering commit guardrail."
    )
    parser.add_argument(
        "--verify-marker",
        action="store_true",
        help="Verify existing COMMIT-READY evidence; used by the pre-commit hook.",
    )
    parser.add_argument(
        "--pending-exempt",
        action="append",
        default=[],
        metavar="\"FILE REASON\"",
        help=(
            "Predict a Ledger-Exempt trailer you are about to commit, so this "
            "first preflight run for a legitimate exemption can produce "
            "COMMIT-READY. You must still put the identical "
            "'Ledger-Exempt: FILE REASON' trailer in the real commit message "
            "- CI re-derives the exemption from the actual committed message, "
            "not from this flag. Repeatable."
        ),
    )
    args = parser.parse_args(argv)

    try:
        root = find_repo_root()
        if args.verify_marker:
            verify_marker(root)
        else:
            run_preflight(root, args.pending_exempt)
    except PreflightStop as exc:
        print(f"STOP-{exc.code}: {exc.message}", file=sys.stderr)
        return 1

    print("COMMIT-READY")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
