"""Verify every historical artifact file is recorded in the SHA-256 manifest."""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ARTIFACT_DIRECTORY = ROOT / "artifacts"
MANIFEST_PATH = ARTIFACT_DIRECTORY / "ARTIFACT_MANIFEST.sha256"
ARTIFACT_EXTENSIONS = {".docx", ".pdf"}


def load_manifest(path: Path) -> dict[str, str]:
    entries: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        digest, _, relative_path = line.partition("  ")
        entries[relative_path] = digest
    return entries


def sha256_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    manifest = load_manifest(MANIFEST_PATH)
    failures: list[str] = []

    artifact_files = sorted(
        path
        for path in ARTIFACT_DIRECTORY.rglob("*")
        if path.is_file() and path.suffix.lower() in ARTIFACT_EXTENSIONS
    )

    seen: set[str] = set()
    for path in artifact_files:
        relative_path = path.relative_to(ARTIFACT_DIRECTORY).as_posix()
        seen.add(relative_path)
        if relative_path not in manifest:
            failures.append(f"missing manifest entry: {relative_path}")
            continue
        actual = sha256_of(path)
        if actual != manifest[relative_path]:
            failures.append(
                f"hash mismatch: {relative_path} (manifest={manifest[relative_path]}, actual={actual})"
            )

    for relative_path in manifest:
        if relative_path not in seen:
            failures.append(f"manifest entry has no matching file on disk: {relative_path}")

    if failures:
        print("\n".join(failures))
        return 1
    print(f"Artifact manifest validation passed ({len(artifact_files)} files).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
