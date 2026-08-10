"""Admission control for starting a sequel simulation from a main campaign."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Mapping


MAIN_CAMPAIGN_MANIFEST = "main-campaign-manifest.json"
REQUIRED_COVERAGE_AREAS = (
    "campaign_context",
    "world_state",
    "participants",
    "timeline",
    "knowledge_boundaries",
    "open_threads",
)
VALID_COVERAGE_STATUSES = {"complete", "not_applicable"}


class MainCampaignAdmissionError(ValueError):
    """Raised when a sequel would start without an adequate campaign foundation."""


def _require_non_empty_string(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise MainCampaignAdmissionError(f"main campaign manifest requires a non-empty {field}")
    return value


def validate_main_campaign_manifest(manifest: Mapping[str, object]) -> None:
    """Validate the evidence required before a sequel runtime may be initialized."""
    if manifest.get("repository_role") != "main-campaign":
        raise MainCampaignAdmissionError("manifest repository_role must be main-campaign")
    _require_non_empty_string(manifest.get("campaign_id"), "campaign_id")
    _require_non_empty_string(manifest.get("source_revision"), "source_revision")

    readiness = manifest.get("readiness")
    if not isinstance(readiness, Mapping) or readiness.get("status") != "ready":
        raise MainCampaignAdmissionError("main campaign readiness.status must be ready")

    coverage = manifest.get("information_coverage")
    if not isinstance(coverage, Mapping):
        raise MainCampaignAdmissionError("main campaign manifest requires information_coverage")

    for area in REQUIRED_COVERAGE_AREAS:
        evidence = coverage.get(area)
        if not isinstance(evidence, Mapping):
            raise MainCampaignAdmissionError(f"missing information coverage for {area}")
        if evidence.get("status") not in VALID_COVERAGE_STATUSES:
            raise MainCampaignAdmissionError(
                f"information coverage for {area} must be complete or not_applicable"
            )
        record_ids = evidence.get("evidence_record_ids")
        if not isinstance(record_ids, list) or not record_ids or not all(
            isinstance(record_id, str) and record_id.strip() for record_id in record_ids
        ):
            raise MainCampaignAdmissionError(
                f"information coverage for {area} requires at least one evidence record id"
            )


def admit_main_campaign(main_campaign_root: Path) -> dict[str, object]:
    """Load and validate a main-campaign manifest before any sequel action occurs."""
    manifest_path = main_campaign_root / MAIN_CAMPAIGN_MANIFEST
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
    validate_main_campaign_manifest(manifest)
    return manifest
