"""Executable admission and optional-material onboarding rules."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


OPTIONAL_MATERIAL = (
    {
        "id": "supporting_character",
        "label": "Supporting-character profiles",
        "template": "supporting-character-profile.template.json",
    },
    {
        "id": "location",
        "label": "Location profiles",
        "template": "location-profile.template.json",
    },
    {
        "id": "organization",
        "label": "Organization profiles",
        "template": "organization-profile.template.json",
    },
    {
        "id": "item",
        "label": "Item profiles",
        "template": "item-profile.template.json",
    },
    {
        "id": "relationship",
        "label": "Relationship records",
        "template": "relationship-record.template.json",
    },
    {
        "id": "timeline",
        "label": "Timeline entries",
        "template": "timeline-entry.template.json",
    },
    {
        "id": "knowledge_boundary",
        "label": "Knowledge-boundary records",
        "template": "knowledge-boundary-record.template.json",
    },
)

CONTINUE_WITHOUT_OPTIONAL_MATERIAL = "continue_without_adding_material"


@dataclass(frozen=True)
class AdmissionResult:
    admitted: bool
    missing: tuple[str, ...]


def _has_text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _is_usable_character_profile(profile: Any) -> bool:
    return isinstance(profile, dict) and _has_text(profile.get("character_name")) and _has_text(
        profile.get("character_summary")
    )


def evaluate_minimum_playable_campaign(
    manifest: dict[str, Any], character_profiles: list[dict[str, Any]]
) -> AdmissionResult:
    """Return all missing minimum inputs without writing runtime state."""

    missing: list[str] = []
    if not _has_text(manifest.get("campaign_history")):
        missing.append("campaign_history")
    if not any(_is_usable_character_profile(profile) for profile in character_profiles):
        missing.append("usable_character_profile")
    if not _has_text(manifest.get("starting_situation")):
        missing.append("starting_situation")
    return AdmissionResult(admitted=not missing, missing=tuple(missing))


def build_optional_material_menu() -> dict[str, Any]:
    """Expose every optional extension without making any of them required."""

    return {
        "title": "Optional campaign material",
        "message": "Your campaign is ready. Add material now, later, or continue directly.",
        "options": [*OPTIONAL_MATERIAL, {"id": CONTINUE_WITHOUT_OPTIONAL_MATERIAL, "label": "Continue without adding material"}],
        "all_options_optional": True,
    }


def build_first_boot_state(
    manifest: dict[str, Any], character_profiles: list[dict[str, Any]]
) -> dict[str, Any]:
    """Enforce the gate before either optional onboarding or storage setup."""

    result = evaluate_minimum_playable_campaign(manifest, character_profiles)
    if not result.admitted:
        return {
            "status": "blocked",
            "missing": list(result.missing),
            "optional_material_menu": None,
            "storage_prompt": None,
        }
    return {
        "status": "admitted",
        "missing": [],
        "optional_material_menu": build_optional_material_menu(),
        "storage_prompt": None,
    }


def continue_from_optional_material(selected_ids: list[str]) -> dict[str, Any]:
    """Validate an optional selection, then expose storage setup."""

    known_ids = {option["id"] for option in OPTIONAL_MATERIAL}
    selected = set(selected_ids)
    if CONTINUE_WITHOUT_OPTIONAL_MATERIAL in selected:
        selected = {CONTINUE_WITHOUT_OPTIONAL_MATERIAL}
    unknown = selected - known_ids - {CONTINUE_WITHOUT_OPTIONAL_MATERIAL}
    if unknown:
        raise ValueError("Unknown optional-material selection")
    return {
        "selected_optional_material": sorted(selected),
        "storage_prompt": {
            "choices": ("repository", "supabase"),
            "default": "repository",
            "fallback": "repository",
        },
    }

