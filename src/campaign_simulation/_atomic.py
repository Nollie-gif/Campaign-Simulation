from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any, Mapping


def _fsync_parent_directory(parent: Path) -> None:
    """
    Best-effort parent-directory fsync.

    This helper is isolated so tests can patch it without interfering with
    tempfile or other os-level operations. Callers should catch and ignore
    exceptions from this helper when parent-directory fsync is optional.
    """
    # Attempt to open the directory for reading and fsync it. This may be
    # unsupported on some platforms; let callers decide whether to treat
    # failures as fatal or best-effort.
    dir_fd = os.open(str(parent), os.O_RDONLY)
    try:
        os.fsync(dir_fd)
    finally:
        os.close(dir_fd)


def write_json_atomically(destination: Path, payload: Mapping[str, Any], fsync_parent: bool = False) -> None:
    """
    Atomically write `payload` as JSON to `destination`.

    Guarantees:
    - Writes to a unique temporary file in the same directory as `destination`.
    - Flushes and fsyncs the temporary file before rename/replace.
    - Uses os.replace() to atomically move the temporary into place.
    - Optionally attempts to fsync the parent directory via _fsync_parent_directory.
      Parent fsync is best-effort: exceptions from the parent-fsync helper are
      swallowed so that platforms that don't support directory fsync do not fail.
    - On handled exceptions, attempts to remove the temporary file before re-raising.
    """
    destination.parent.mkdir(parents=True, exist_ok=True)

    descriptor, temporary_name = tempfile.mkstemp(
        dir=str(destination.parent), prefix=f".{destination.name}.", suffix=".tmp"
    )
    temporary = Path(temporary_name)
    try:
        # Write payload, flush, and fsync the file itself
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())

        # Atomically move into place
        os.replace(temporary, destination)

        # Best-effort parent-directory fsync for stronger durability.
        if fsync_parent:
            try:
                _fsync_parent_directory(destination.parent)
            except Exception:
                # Best-effort only: do not convert parent-fsync failures into write failures.
                pass

    except BaseException:
        # Attempt best-effort cleanup of the temporary file on handled failures.
        try:
            temporary.unlink(missing_ok=True)
        except Exception:
            # If cleanup fails, avoid masking original exception.
            pass
        raise
