"""Atomic quick-save and final-save manifest persistence."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Mapping


REQUIRED_MANIFEST_FIELDS = {"id", "kind", "status", "created_at", "record_revisions"}


def validate_manifest(manifest: Mapping[str, object]) -> None:
    missing = REQUIRED_MANIFEST_FIELDS - set(manifest)
    if missing:
        raise ValueError(f"save manifest is missing fields: {', '.join(sorted(missing))}")
    if manifest["kind"] not in {"quick", "final"}:
        raise ValueError("save manifest kind must be quick or final")
    if manifest["status"] not in {"prepared", "validated", "committed"}:
        raise ValueError("save manifest status is invalid")
    if not isinstance(manifest["record_revisions"], list):
        raise ValueError("record revisions must be a list")


def commit_manifest(destination: Path, manifest: Mapping[str, object]) -> None:
    """Validate then atomically persist one durable save manifest."""
    validate_manifest(manifest)
    committed = dict(manifest)
    committed["status"] = "committed"
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    temporary.write_text(json.dumps(committed, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, destination)
