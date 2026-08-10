"""Admission control for starting a sequel simulation from a main campaign."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping


MAIN_CAMPAIGN_MANIFEST = "main-campaign-manifest.json"


class MainCampaignAdmissionError(ValueError):
    """Raised when a sequel would start without an adequate campaign foundation."""


def _require_non_empty_string(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise MainCampaignAdmissionError(f"main campaign manifest requires a non-empty {field}")
    return value


def validate_main_campaign_manifest(manifest: Mapping[str, object]) -> list[str]:
    """Validate only the minimum information required to begin play.

    Supporting characters, locations, organizations, items, relationships,
    timeline records, and knowledge boundaries are deliberately optional.
    """
    _require_non_empty_string(manifest.get("campaign_history"), "campaign_history")
    _require_non_empty_string(manifest.get("starting_situation"), "starting_situation")

    references = manifest.get("character_profile_references")
    if not isinstance(references, list) or not references:
        raise MainCampaignAdmissionError(
            "main campaign manifest requires at least one character profile reference"
        )
    if not all(isinstance(reference, str) and reference.strip() for reference in references):
        raise MainCampaignAdmissionError("character profile references must be non-empty strings")
    return references


def _load_usable_character_profile(main_campaign_root: Path, reference: str) -> dict[str, Any]:
    declared_path = Path(reference)
    if declared_path.is_absolute():
        raise MainCampaignAdmissionError(
            f"character profile reference must be relative to the main campaign: {reference}"
        )

    resolved_root = main_campaign_root.resolve()
    profile_path = (resolved_root / declared_path).resolve()
    try:
        profile_path.relative_to(resolved_root)
    except ValueError as error:
        raise MainCampaignAdmissionError(
            f"character profile reference escapes the main campaign: {reference}"
        ) from error

    if not profile_path.is_file():
        raise MainCampaignAdmissionError(f"character profile is missing: {reference}")
    try:
        profile = json.loads(profile_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise MainCampaignAdmissionError(f"character profile is not valid JSON: {reference}") from error
    if not isinstance(profile, dict):
        raise MainCampaignAdmissionError(f"character profile must be an object: {reference}")
    _require_non_empty_string(profile.get("character_name"), "character_name")
    _require_non_empty_string(profile.get("character_summary"), "character_summary")
    return profile


def admit_main_campaign(main_campaign_root: Path) -> dict[str, object]:
    """Load and validate a main-campaign manifest before any sequel action occurs."""
    resolved_root = main_campaign_root.resolve()
    if not resolved_root.is_dir():
        raise MainCampaignAdmissionError("sequel simulation is blocked: main campaign directory is missing")

    manifest_path = resolved_root / MAIN_CAMPAIGN_MANIFEST
    if not manifest_path.is_file():
        raise MainCampaignAdmissionError(
            "sequel simulation is blocked: main-campaign-manifest.json is missing"
        )
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise MainCampaignAdmissionError("main campaign manifest is not valid JSON") from error
    if not isinstance(manifest, dict):
        raise MainCampaignAdmissionError("main campaign manifest must be an object")
    references = validate_main_campaign_manifest(manifest)
    for reference in references:
        _load_usable_character_profile(resolved_root, reference)
    return manifest
