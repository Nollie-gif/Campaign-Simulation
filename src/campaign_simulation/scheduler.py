"""Deterministic deferred-event scheduler for campaign simulations.

The scheduler owns *when a pending obligation becomes eligible*. It never owns
narrative consequences and never mutates campaign state during evaluation.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Iterable, Mapping

from .clock import campaign_time_reached, validate_clock_state
from .lifecycles import EVENT_TRANSITIONS, transition

SCHEDULER_SCHEMA_VERSION = 1
SCHEDULER_RECORD_ID = "scheduler_state"

EVENT_STATUSES = ("pending", "resolved", "cancelled")
TRIGGER_TYPES = (
    "campaign_time",
    "elapsed_time",
    "long_rest",
    "state_condition",
    "transition",
)
CONDITION_OPERATORS = (
    "equals",
    "not_equals",
    "exists",
    "not_exists",
    "greater_or_equal",
    "less_or_equal",
    "contains",
)

_MISSING = object()


def _require_text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be a non-empty string")
    return value


def _require_int(value: Any, label: str, minimum: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise ValueError(f"{label} must be an integer >= {minimum}")
    return value


def initial_scheduler_state() -> dict[str, Any]:
    state = {"schema_version": SCHEDULER_SCHEMA_VERSION, "events": []}
    validate_scheduler_state(state)
    return state


def campaign_time_trigger(*, day: int, phase: str) -> dict[str, Any]:
    trigger = {"type": "campaign_time", "day": day, "phase": phase}
    validate_trigger(trigger)
    return trigger


def after_elapsed_trigger(clock_state: Mapping[str, Any], minutes: int) -> dict[str, Any]:
    validate_clock_state(clock_state)
    delay = _require_int(minutes, "minutes", 1)
    trigger = {
        "type": "elapsed_time",
        "due_elapsed_campaign_minutes": clock_state["elapsed_campaign_minutes"] + delay,
    }
    validate_trigger(trigger)
    return trigger


def next_long_rest_trigger(clock_state: Mapping[str, Any]) -> dict[str, Any]:
    validate_clock_state(clock_state)
    trigger = {
        "type": "long_rest",
        "due_long_rest_count": clock_state["long_rests_completed"] + 1,
    }
    validate_trigger(trigger)
    return trigger


def state_condition_trigger(condition: Mapping[str, Any]) -> dict[str, Any]:
    validate_condition(condition)
    trigger = {"type": "state_condition", "condition": deepcopy(dict(condition))}
    validate_trigger(trigger)
    return trigger


def transition_trigger(transition_key: str) -> dict[str, Any]:
    trigger = {
        "type": "transition",
        "transition_key": _require_text(transition_key, "transition_key"),
    }
    validate_trigger(trigger)
    return trigger


def validate_condition(condition: Mapping[str, Any]) -> None:
    if not isinstance(condition, Mapping):
        raise ValueError("condition must be an object")

    path = condition.get("path")
    if not isinstance(path, list) or not path:
        raise ValueError("condition.path must be a non-empty list")
    for part in path:
        _require_text(part, "condition.path entry")

    operator = condition.get("operator")
    if operator not in CONDITION_OPERATORS:
        raise ValueError(
            "condition.operator must be one of: " + ", ".join(CONDITION_OPERATORS)
        )

    if operator not in {"exists", "not_exists"} and "value" not in condition:
        raise ValueError(f"condition operator {operator!r} requires value")


def validate_trigger(trigger: Mapping[str, Any]) -> None:
    if not isinstance(trigger, Mapping):
        raise ValueError("event trigger must be an object")

    trigger_type = trigger.get("type")
    if trigger_type not in TRIGGER_TYPES:
        raise ValueError("event trigger type must be one of: " + ", ".join(TRIGGER_TYPES))

    if trigger_type == "campaign_time":
        day = _require_int(trigger.get("day"), "trigger.day", 1)
        phase = _require_text(trigger.get("phase"), "trigger.phase")
        try:
            campaign_time_reached(
                {
                    "schema_version": 1,
                    "day": day,
                    "phase": phase,
                    "elapsed_campaign_minutes": 0,
                    "long_rests_completed": 0,
                },
                target_day=day,
                target_phase=phase,
            )
        except ValueError as error:
            raise ValueError(f"invalid campaign_time trigger: {error}") from error
    elif trigger_type == "elapsed_time":
        _require_int(
            trigger.get("due_elapsed_campaign_minutes"),
            "trigger.due_elapsed_campaign_minutes",
            0,
        )
    elif trigger_type == "long_rest":
        _require_int(trigger.get("due_long_rest_count"), "trigger.due_long_rest_count", 1)
    elif trigger_type == "state_condition":
        condition = trigger.get("condition")
        if not isinstance(condition, Mapping):
            raise ValueError("state_condition trigger requires condition")
        validate_condition(condition)
    elif trigger_type == "transition":
        _require_text(trigger.get("transition_key"), "trigger.transition_key")


def _validate_clock_snapshot(snapshot: Mapping[str, Any], label: str) -> None:
    if not isinstance(snapshot, Mapping):
        raise ValueError(f"{label} must be a clock snapshot")
    validate_clock_state(
        {
            "schema_version": 1,
            "day": snapshot.get("day"),
            "phase": snapshot.get("phase"),
            "elapsed_campaign_minutes": snapshot.get("elapsed_campaign_minutes"),
            "long_rests_completed": snapshot.get("long_rests_completed"),
        }
    )


def validate_event(event: Mapping[str, Any]) -> None:
    if not isinstance(event, Mapping):
        raise ValueError("scheduled event must be an object")

    _require_text(event.get("id"), "event.id")
    if event.get("status") not in EVENT_STATUSES:
        raise ValueError("event.status must be pending, resolved, or cancelled")
    _require_text(event.get("dedupe_key"), "event.dedupe_key")

    trigger = event.get("trigger")
    if not isinstance(trigger, Mapping):
        raise ValueError("event.trigger must be an object")
    validate_trigger(trigger)

    references = event.get("references", {})
    if not isinstance(references, Mapping):
        raise ValueError("event.references must be an object")
    for key, value in references.items():
        _require_text(key, "event.references key")
        _require_text(value, f"event.references[{key!r}]")

    guard = event.get("guard")
    if guard is not None:
        if not isinstance(guard, Mapping):
            raise ValueError("event.guard must be an object or null")
        validate_condition(guard)

    created_at = event.get("created_at")
    if not isinstance(created_at, Mapping):
        raise ValueError("event.created_at must be a clock snapshot")
    _validate_clock_snapshot(created_at, "event.created_at")


def validate_scheduler_state(state: Mapping[str, Any]) -> None:
    if not isinstance(state, Mapping):
        raise ValueError("scheduler state must be an object")
    if state.get("schema_version") != SCHEDULER_SCHEMA_VERSION:
        raise ValueError(f"scheduler schema_version must be {SCHEDULER_SCHEMA_VERSION}")

    events = state.get("events")
    if not isinstance(events, list):
        raise ValueError("scheduler events must be a list")

    seen_ids: set[str] = set()
    seen_dedupe_keys: set[str] = set()
    for event in events:
        if not isinstance(event, Mapping):
            raise ValueError("scheduler events must contain objects")
        validate_event(event)
        event_id = str(event["id"])
        dedupe_key = str(event["dedupe_key"])
        if event_id in seen_ids:
            raise ValueError(f"duplicate scheduled event id: {event_id}")
        if dedupe_key in seen_dedupe_keys:
            raise ValueError(f"duplicate scheduled event dedupe_key: {dedupe_key}")
        seen_ids.add(event_id)
        seen_dedupe_keys.add(dedupe_key)


def create_event(
    state: Mapping[str, Any],
    *,
    event_id: str,
    dedupe_key: str,
    trigger: Mapping[str, Any],
    clock_state: Mapping[str, Any],
    references: Mapping[str, str] | None = None,
    guard: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Create one pending event, idempotently by dedupe key.

    A retry with the same ``dedupe_key`` and same immutable event definition
    returns the existing event and leaves the registry unchanged. Reusing a
    dedupe key for a different event definition is refused.
    """

    validate_scheduler_state(state)
    validate_clock_state(clock_state)
    normalized_id = _require_text(event_id, "event_id")
    normalized_dedupe = _require_text(dedupe_key, "dedupe_key")
    validate_trigger(trigger)
    if guard is not None:
        validate_condition(guard)

    normalized_references = dict(references or {})
    for key, value in normalized_references.items():
        _require_text(key, "references key")
        _require_text(value, f"references[{key!r}]")

    current = deepcopy(dict(state))
    current["events"] = [deepcopy(dict(item)) for item in state["events"]]

    for existing in current["events"]:
        if existing["dedupe_key"] != normalized_dedupe:
            continue

        same_definition = (
            existing["trigger"] == dict(trigger)
            and existing.get("references", {}) == normalized_references
            and existing.get("guard") == (None if guard is None else dict(guard))
        )
        if not same_definition:
            raise ValueError(
                f"dedupe_key already belongs to a different event definition: {normalized_dedupe}"
            )
        return {
            "state": current,
            "event": deepcopy(existing),
            "created": False,
        }

    if any(item["id"] == normalized_id for item in current["events"]):
        raise ValueError(f"scheduled event id already exists: {normalized_id}")

    event: dict[str, Any] = {
        "id": normalized_id,
        "status": "pending",
        "dedupe_key": normalized_dedupe,
        "trigger": deepcopy(dict(trigger)),
        "references": normalized_references,
        "guard": None if guard is None else deepcopy(dict(guard)),
        "created_at": {
            "day": clock_state["day"],
            "phase": clock_state["phase"],
            "elapsed_campaign_minutes": clock_state["elapsed_campaign_minutes"],
            "long_rests_completed": clock_state["long_rests_completed"],
        },
    }
    validate_event(event)
    current["events"].append(event)
    validate_scheduler_state(current)
    return {"state": current, "event": deepcopy(event), "created": True}


def transition_event(
    state: Mapping[str, Any],
    event_id: str,
    target_status: str,
) -> dict[str, Any]:
    """Resolve or cancel one pending event and return the next registry state."""

    validate_scheduler_state(state)
    normalized_id = _require_text(event_id, "event_id")
    current = deepcopy(dict(state))
    current["events"] = [deepcopy(dict(item)) for item in state["events"]]

    for event in current["events"]:
        if event["id"] == normalized_id:
            event["status"] = transition(
                str(event["status"]),
                target_status,
                EVENT_TRANSITIONS,
            )
            validate_scheduler_state(current)
            return current

    raise ValueError(f"scheduled event does not exist: {normalized_id}")


def _resolve_path(root: Mapping[str, Any], path: list[str]) -> Any:
    current: Any = root
    for part in path:
        if not isinstance(current, Mapping) or part not in current:
            return _MISSING
        current = current[part]
    return current


def evaluate_condition(runtime_state: Mapping[str, Any], condition: Mapping[str, Any]) -> bool:
    if not isinstance(runtime_state, Mapping):
        raise ValueError("runtime_state must be an object")
    validate_condition(condition)

    value = _resolve_path(runtime_state, list(condition["path"]))
    operator = condition["operator"]

    if operator == "exists":
        return value is not _MISSING
    if operator == "not_exists":
        return value is _MISSING
    if value is _MISSING:
        return False

    expected = condition.get("value")
    if operator == "equals":
        return value == expected
    if operator == "not_equals":
        return value != expected
    if operator == "greater_or_equal":
        try:
            return value >= expected
        except TypeError:
            return False
    if operator == "less_or_equal":
        try:
            return value <= expected
        except TypeError:
            return False
    if operator == "contains":
        try:
            return expected in value
        except TypeError:
            return False

    raise AssertionError("validated condition operator unexpectedly unsupported")


def _trigger_is_eligible(
    trigger: Mapping[str, Any],
    clock_state: Mapping[str, Any],
    runtime_state: Mapping[str, Any],
    transition_keys: set[str],
) -> bool:
    trigger_type = trigger["type"]

    if trigger_type == "campaign_time":
        return campaign_time_reached(
            clock_state,
            target_day=trigger["day"],
            target_phase=trigger["phase"],
        )
    if trigger_type == "elapsed_time":
        return (
            clock_state["elapsed_campaign_minutes"]
            >= trigger["due_elapsed_campaign_minutes"]
        )
    if trigger_type == "long_rest":
        return clock_state["long_rests_completed"] >= trigger["due_long_rest_count"]
    if trigger_type == "state_condition":
        return evaluate_condition(runtime_state, trigger["condition"])
    if trigger_type == "transition":
        return trigger["transition_key"] in transition_keys

    raise AssertionError("validated trigger type unexpectedly unsupported")


def evaluate_scheduler(
    state: Mapping[str, Any],
    clock_state: Mapping[str, Any],
    *,
    runtime_state: Mapping[str, Any] | None = None,
    transition_keys: Iterable[str] = (),
) -> dict[str, Any]:
    """Surface all eligible pending events without mutating the registry.

    Pending events remain pending until the DM/runtime resolves or cancels them and
    persists that status together with any resulting campaign-state mutation.
    Consequently, a crash before that commit safely causes the event to surface
    again after reload (at-least-once delivery).
    """

    validate_scheduler_state(state)
    validate_clock_state(clock_state)
    runtime = {} if runtime_state is None else runtime_state
    if not isinstance(runtime, Mapping):
        raise ValueError("runtime_state must be an object")

    normalized_transitions: set[str] = set()
    for key in transition_keys:
        normalized_transitions.add(_require_text(key, "transition key"))

    eligible: list[dict[str, Any]] = []
    blocked: list[str] = []

    for raw_event in state["events"]:
        event = dict(raw_event)
        if event["status"] != "pending":
            continue
        if not _trigger_is_eligible(
            event["trigger"],
            clock_state,
            runtime,
            normalized_transitions,
        ):
            continue

        guard = event.get("guard")
        if guard is not None and not evaluate_condition(runtime, guard):
            blocked.append(str(event["id"]))
            continue

        eligible.append(deepcopy(event))

    eligible.sort(key=lambda item: str(item["id"]))
    blocked.sort()

    return {
        "eligible_event_ids": [item["id"] for item in eligible],
        "eligible_events": eligible,
        "due_but_guard_blocked_event_ids": blocked,
    }

