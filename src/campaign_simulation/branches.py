"""Branch-neutral exploration choices around a protected Main Campaign."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any, Mapping


PREQUEL_MODE = "prequel"
SEQUEL_MODE = "sequel"
SIMULATION_MODES = (PREQUEL_MODE, SEQUEL_MODE)


def _require_text(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"simulation branch requires a non-empty {field}")
    return value.strip()


def build_exploration_menu() -> dict[str, Any]:
    """Describe the two first-class ways to explore the Main Campaign."""

    return {
        "title": "Choose what you want to explore",
        "message": "Your Main Campaign is protected. Explore its past or its future without changing canon.",
        "options": [
            {
                "id": PREQUEL_MODE,
                "label": "Explore the past — Prequel",
                "description": "Choose a historical anchor before the Main Campaign and simulate forward toward canon.",
            },
            {
                "id": SEQUEL_MODE,
                "label": "Explore the future — Sequel",
                "description": "Continue forward from the Main Campaign's current situation or another forward anchor.",
            },
        ],
    }


def resolve_simulation_branch(
    main_campaign_manifest: Mapping[str, object], mode: str, anchor: str | None = None
) -> dict[str, str]:
    """Create a branch contract without mutating the Main Campaign.

    Both modes simulate forward in time. A prequel requires an explicit
    historical anchor. A sequel may use the Main Campaign's starting/current
    situation as its default forward anchor.
    """

    normalized_mode = _require_text(mode, "mode").lower()
    if normalized_mode not in SIMULATION_MODES:
        raise ValueError("simulation mode must be prequel or sequel")

    if normalized_mode == PREQUEL_MODE:
        resolved_anchor = _require_text(anchor, "historical anchor")
        relative_position = "before_main_campaign"
        boundary_behavior = "freeze_at_main_convergence_gate"
    else:
        candidate = anchor if isinstance(anchor, str) and anchor.strip() else main_campaign_manifest.get(
            "starting_situation"
        )
        resolved_anchor = _require_text(candidate, "sequel anchor")
        relative_position = "after_main_campaign"
        boundary_behavior = "continue_forward"

    return {
        "mode": normalized_mode,
        "anchor": resolved_anchor,
        "relative_position": relative_position,
        "time_direction": "forward",
        "main_campaign_access": "read_only",
        "boundary_behavior": boundary_behavior,
    }


def _write_json_atomically(destination: Path, payload: Mapping[str, object]) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        dir=destination.parent,
        prefix=f".{destination.name}.",
        suffix=".tmp",
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, destination)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


def persist_simulation_branch(destination: Path, branch: Mapping[str, object]) -> dict[str, str]:
    """Validate and persist the selected branch in the local simulation runtime."""

    validated = resolve_simulation_branch(
        {"starting_situation": branch.get("anchor", "")},
        _require_text(branch.get("mode"), "mode"),
        _require_text(branch.get("anchor"), "anchor"),
    )
    for field in ("relative_position", "time_direction", "main_campaign_access", "boundary_behavior"):
        if branch.get(field) != validated[field]:
            raise ValueError(f"simulation branch {field} is invalid")
    _write_json_atomically(destination, validated)
    return validated
