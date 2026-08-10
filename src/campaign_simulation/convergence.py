"""Prequel-to-main convergence gate with no implicit canon mutation."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping

from .saves import validate_checkpoint


ENTER_MAIN_UNCHANGED = "enter_main_unchanged"
PROPOSE_CANON_CHANGES = "propose_canon_changes"
CONTINUE_ALTERNATE_TIMELINE = "continue_as_alternate_timeline"
CONVERGENCE_CHOICES = (
    ENTER_MAIN_UNCHANGED,
    PROPOSE_CANON_CHANGES,
    CONTINUE_ALTERNATE_TIMELINE,
)


def _require_text(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"prequel convergence requires a non-empty {field}")
    return value


def begin_prequel_main_convergence(
    prequel_checkpoint: Mapping[str, object], main_campaign_target: str
) -> dict[str, Any]:
    """Freeze a completed prequel at the scene where it meets the main campaign.

    This creates a review state only. It never opens, writes, or mutates the
    main campaign, so reaching the same scene cannot silently retcon canon.
    """

    if not isinstance(prequel_checkpoint, Mapping):
        raise ValueError("prequel checkpoint must be an object")
    manifest = prequel_checkpoint.get("manifest")
    records = prequel_checkpoint.get("records")
    if not isinstance(manifest, Mapping) or not isinstance(records, Mapping):
        raise ValueError("prequel checkpoint requires manifest and records objects")
    validate_checkpoint(manifest, records)
    if manifest.get("status") != "committed":
        raise ValueError("prequel convergence requires a committed checkpoint")

    return {
        "status": "awaiting_main_convergence_choice",
        "prequel_status": "frozen_at_main_boundary",
        "prequel_checkpoint_id": _require_text(manifest.get("id"), "prequel_checkpoint_id"),
        "main_campaign_target": _require_text(main_campaign_target, "main_campaign_target"),
        "allowed_choices": list(CONVERGENCE_CHOICES),
        "main_campaign_write_authorization": "never_automatic",
        "selected_choice": "",
        "canon_change_proposal": [],
    }


def resolve_prequel_main_convergence(
    convergence: Mapping[str, object], choice: str, canon_change_proposal: list[Mapping[str, object]] | None = None
) -> dict[str, Any]:
    """Record an explicit player decision while preserving Main Campaign ownership."""

    if convergence.get("status") != "awaiting_main_convergence_choice":
        raise ValueError("prequel convergence is not awaiting a choice")
    if choice not in CONVERGENCE_CHOICES:
        raise ValueError("prequel convergence choice is invalid")
    if canon_change_proposal is not None and not all(
        isinstance(item, Mapping) for item in canon_change_proposal
    ):
        raise ValueError("canon change proposal must contain only objects")

    result = deepcopy(dict(convergence))
    result["selected_choice"] = choice
    result["main_campaign_write_authorization"] = "never_automatic"
    if choice == ENTER_MAIN_UNCHANGED:
        result["status"] = "main_entered_unchanged"
        result["canon_change_proposal"] = []
    elif choice == PROPOSE_CANON_CHANGES:
        result["status"] = "canon_change_review_required"
        result["canon_change_proposal"] = list(canon_change_proposal or [])
    else:
        result["status"] = "alternate_timeline_continues"
        result["canon_change_proposal"] = []
    return result
