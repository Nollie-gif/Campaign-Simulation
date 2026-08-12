"""Atomic quick-save and final-save checkpoint persistence."""

from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping

from .autosave import AUTOSAVE_RECORD_ID, validate_autosave_state
from .clock import CLOCK_RECORD_ID, validate_clock_state
from .mutation_gates import MutationPlan, plan_to_mapping, validate_mutation_plan
from .scheduler import SCHEDULER_RECORD_ID, validate_scheduler_state


REQUIRED_MANIFEST_FIELDS = {"id", "kind", "status", "created_at", "record_revisions"}


def _require_text(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"save manifest {field} must be a non-empty string")
    return value


def _validate_timestamp(value: object) -> None:
    timestamp = _require_text(value, "created_at")
    if "T" not in timestamp:
        raise ValueError("save manifest created_at must be an ISO-8601 date-time")
    try:
        parsed = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    except ValueError as error:
        raise ValueError("save manifest created_at must be an ISO-8601 date-time") from error
    if parsed.tzinfo is None:
        raise ValueError("save manifest created_at must include a timezone")


def _validate_record_revisions(value: object) -> list[Mapping[str, object]]:
    if not isinstance(value, list) or not value:
        raise ValueError("record revisions must be a non-empty list")
    revisions: list[Mapping[str, object]] = []
    seen_ids: set[str] = set()
    for revision in value:
        if not isinstance(revision, Mapping):
            raise ValueError("each record revision must be an object")
        record_id = _require_text(revision.get("record_id"), "record_revisions.record_id")
        _require_text(revision.get("revision"), "record_revisions.revision")
        if record_id in seen_ids:
            raise ValueError("record revisions must not repeat a record_id")
        seen_ids.add(record_id)
        revisions.append(revision)
    return revisions


def validate_manifest(manifest: Mapping[str, object]) -> None:
    """Validate a complete generic save manifest in any lifecycle state."""

    missing = REQUIRED_MANIFEST_FIELDS - set(manifest)
    if missing:
        raise ValueError(f"save manifest is missing fields: {', '.join(sorted(missing))}")
    _require_text(manifest["id"], "id")
    if manifest["kind"] not in {"quick", "final"}:
        raise ValueError("save manifest kind must be quick or final")
    if manifest["status"] not in {"prepared", "validated", "committed"}:
        raise ValueError("save manifest status is invalid")
    _validate_timestamp(manifest["created_at"])
    _validate_record_revisions(manifest["record_revisions"])


def validate_prepared_manifest(manifest: Mapping[str, object]) -> dict[str, object]:
    """Validate the only state that may advance to `validated`."""

    validate_manifest(manifest)
    if manifest["status"] != "prepared":
        raise ValueError("only a prepared save manifest may be validated")
    validated = dict(manifest)
    validated["status"] = "validated"
    return validated


def _require_commit_ready_manifest(manifest: Mapping[str, object]) -> dict[str, object]:
    validate_manifest(manifest)
    if manifest["status"] != "validated":
        raise ValueError("only a validated save manifest may be committed")
    committed = dict(manifest)
    committed["status"] = "committed"
    return committed


def _write_json_atomically(destination: Path, payload: Mapping[str, Any]) -> None:
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


def commit_manifest(destination: Path, manifest: Mapping[str, object]) -> None:
    """Refuse the former manifest-only save path.

    A manifest cannot restore a simulation by itself, so all durable saves must
    use :func:`commit_checkpoint` with the record snapshots it declares.
    """

    del destination, manifest
    raise ValueError("manifest-only save commits are not supported; use commit_checkpoint")


def _validate_known_runtime_record(record_id: str, data: Mapping[str, object]) -> None:
    """Apply stronger schema checks to engine-owned runtime records."""

    if record_id == CLOCK_RECORD_ID:
        validate_clock_state(data)
    elif record_id == AUTOSAVE_RECORD_ID:
        validate_autosave_state(data)
    elif record_id == SCHEDULER_RECORD_ID:
        validate_scheduler_state(data)


def validate_checkpoint(
    manifest: Mapping[str, object], records: Mapping[str, Mapping[str, object]]
) -> None:
    """Ensure every declared revision has exactly one supplied record snapshot.

    Engine-owned runtime records (Campaign Clock, Autosave and Scheduler) receive
    their subsystem validation before any checkpoint is allowed to commit.
    """

    validate_manifest(manifest)
    if not isinstance(records, Mapping) or not records:
        raise ValueError("checkpoint records must be a non-empty object")

    declared = {
        (
            _require_text(item.get("record_id"), "record_revisions.record_id"),
            _require_text(item.get("revision"), "record_revisions.revision"),
        )
        for item in _validate_record_revisions(manifest["record_revisions"])
    }
    supplied: set[tuple[str, str]] = set()
    for record_id, snapshot in records.items():
        normalized_record_id = _require_text(record_id, "records.record_id")
        if not isinstance(snapshot, Mapping):
            raise ValueError("each checkpoint record must be an object")
        revision = _require_text(snapshot.get("revision"), "records.revision")
        data = snapshot.get("data")
        if not isinstance(data, Mapping):
            raise ValueError("each checkpoint record requires an object data snapshot")
        _validate_known_runtime_record(normalized_record_id, data)
        supplied.add((normalized_record_id, revision))

    if declared != supplied:
        raise ValueError("checkpoint records do not match the declared record revisions")


def validate_gated_checkpoint(
    manifest: Mapping[str, object],
    records: Mapping[str, Mapping[str, object]],
    gate_plan: MutationPlan,
) -> None:
    """Validate the checkpoint plus its declared procedure-level mutation plan."""

    validate_checkpoint(manifest, records)
    validate_mutation_plan(gate_plan, record_ids=records)


def commit_checkpoint(
    destination: Path,
    manifest: Mapping[str, object],
    records: Mapping[str, Mapping[str, object]],
    *,
    gate_plan: MutationPlan | None = None,
) -> dict[str, object]:
    """Atomically persist a durable, multi-record, procedure-gated checkpoint."""

    if gate_plan is None:
        raise ValueError("procedure gate plan is required before a checkpoint may commit")
    validate_gated_checkpoint(manifest, records, gate_plan)
    checkpoint: dict[str, object] = {
        "manifest": _require_commit_ready_manifest(manifest),
        "records": dict(records),
        "mutation_gate": plan_to_mapping(gate_plan),
    }
    _write_json_atomically(destination, checkpoint)
    return checkpoint


def load_checkpoint(source: Path) -> dict[str, object]:
    """Load and validate a previously committed complete checkpoint."""

    try:
        checkpoint = json.loads(source.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ValueError("checkpoint is not valid JSON") from error
    if not isinstance(checkpoint, dict):
        raise ValueError("checkpoint must be a JSON object")
    manifest = checkpoint.get("manifest")
    records = checkpoint.get("records")
    if not isinstance(manifest, Mapping) or not isinstance(records, Mapping):
        raise ValueError("checkpoint requires manifest and records objects")
    mutation_gate = checkpoint.get("mutation_gate")
    if mutation_gate is not None and not isinstance(mutation_gate, Mapping):
        raise ValueError("checkpoint mutation_gate must be an object when present")
    validate_checkpoint(manifest, records)
    if manifest["status"] != "committed":
        raise ValueError("checkpoint manifest must be committed")
    return checkpoint
