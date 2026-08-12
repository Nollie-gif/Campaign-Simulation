"""Bridge WDR-001 evaluations to the existing WDR-002 save gate.

This module is deliberately an *initiator*, not a persistence provider.  It
evaluates one scene boundary and, only when a checkpoint is warranted, returns
the three generation-pinned runtime records plus a normal ``autosave`` gate
plan.  The Mission 10 adapter remains solely responsible for staging,
publication, mirror confirmation, and receipt verification.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Iterable, Mapping

from .autosave import AUTOSAVE_RECORD_ID, evaluate_autosave, initial_autosave_state, validate_autosave_state
from .clock import CLOCK_RECORD_ID, apply_time_update, initial_clock_state, validate_clock_state
from .mutation_gates import (
    MutationDomain,
    MutationKind,
    MutationOperation,
    MutationPlan,
    Procedure,
    validate_mutation_plan,
)
from .scheduler import SCHEDULER_RECORD_ID, evaluate_scheduler, initial_scheduler_state, validate_scheduler_state

WDR001_RECORD_IDS = (CLOCK_RECORD_ID, AUTOSAVE_RECORD_ID, SCHEDULER_RECORD_ID)


def initial_wdr001_records(*, day: int, phase: str = "unknown") -> dict[str, dict[str, Any]]:
    """Create the three first-class checkpoint records for a new runtime."""

    clock = initial_clock_state(day=day, phase=phase)
    return {
        CLOCK_RECORD_ID: clock,
        AUTOSAVE_RECORD_ID: initial_autosave_state(clock),
        SCHEDULER_RECORD_ID: initial_scheduler_state(),
    }


def validate_wdr001_records(records: Mapping[str, Any]) -> None:
    """Reject missing, unknown, or invalid WDR-001 checkpoint records."""

    if not isinstance(records, Mapping):
        raise ValueError("WDR-001 records must be an object")
    keys = set(records)
    expected = set(WDR001_RECORD_IDS)
    if keys != expected:
        missing = expected - keys
        extra = keys - expected
        details = []
        if missing:
            details.append("missing: " + ", ".join(sorted(missing)))
        if extra:
            details.append("unknown: " + ", ".join(sorted(extra)))
        raise ValueError("invalid WDR-001 record set (" + "; ".join(details) + ")")
    validate_clock_state(records[CLOCK_RECORD_ID])
    validate_autosave_state(records[AUTOSAVE_RECORD_ID])
    validate_scheduler_state(records[SCHEDULER_RECORD_ID])


def _autosave_plan(*, published_generation: int, staging_generation: int) -> MutationPlan:
    """Declare the exact normal save transaction required for an autosave."""

    plan = MutationPlan(
        procedure=Procedure.AUTOSAVE,
        operations=(
            MutationOperation(MutationDomain.CAMPAIGN_CLOCK, CLOCK_RECORD_ID, MutationKind.WRITE),
            MutationOperation(MutationDomain.AUTOSAVE, AUTOSAVE_RECORD_ID, MutationKind.WRITE),
            MutationOperation(MutationDomain.SCHEDULER, SCHEDULER_RECORD_ID, MutationKind.WRITE),
        ),
        facts=frozenset({"reconciled", "validated", "same_checkpoint"}),
        branch="runtime-save-staging",
        sql_mode="gated",
        persistence_mode="generation_pinned",
        published_generation=published_generation,
        staging_generation=staging_generation,
    )
    validate_mutation_plan(plan, record_ids=WDR001_RECORD_IDS)
    return plan


def evaluate_runtime_boundary(
    records: Mapping[str, Any],
    assessment: Mapping[str, Any],
    *,
    published_generation: int,
    staging_generation: int,
    time_update: Mapping[str, Any] | None = None,
    runtime_state: Mapping[str, Any] | None = None,
    transition_keys: Iterable[str] = (),
) -> dict[str, Any]:
    """Evaluate one scene boundary without writing anything.

    ``checkpoint`` is ``None`` when no save is warranted.  If it is present,
    callers must run *that* plan through the existing gated save pipeline and
    publish all returned records atomically.  Eligible scheduler events are
    informational only: they remain pending and never generate narrative or
    persistence by themselves.
    """

    validate_wdr001_records(records)
    if isinstance(published_generation, bool) or not isinstance(published_generation, int) or published_generation < 0:
        raise ValueError("published_generation must be a non-negative integer")
    if isinstance(staging_generation, bool) or not isinstance(staging_generation, int) or staging_generation <= published_generation:
        raise ValueError("staging_generation must be newer than published_generation")
    if time_update is not None and not isinstance(time_update, Mapping):
        raise ValueError("time_update must be an object when supplied")

    next_clock = apply_time_update(dict(records[CLOCK_RECORD_ID]), **dict(time_update or {}))
    autosave = evaluate_autosave(records[AUTOSAVE_RECORD_ID], next_clock, assessment)
    scheduler = evaluate_scheduler(
        records[SCHEDULER_RECORD_ID],
        next_clock,
        runtime_state={} if runtime_state is None else runtime_state,
        transition_keys=transition_keys,
    )
    next_records = {
        CLOCK_RECORD_ID: next_clock,
        AUTOSAVE_RECORD_ID: autosave["state"],
        SCHEDULER_RECORD_ID: deepcopy(dict(records[SCHEDULER_RECORD_ID])),
    }
    validate_wdr001_records(next_records)

    checkpoint = None
    if autosave["trigger"]:
        checkpoint = {
            "plan": _autosave_plan(
                published_generation=published_generation,
                staging_generation=staging_generation,
            ),
            "records": next_records,
        }

    return {
        "autosave": autosave,
        "eligible_events": scheduler["eligible_events"],
        "blocked_event_ids": scheduler["due_but_guard_blocked_event_ids"],
        "checkpoint": checkpoint,
        "next_records": next_records,
    }
