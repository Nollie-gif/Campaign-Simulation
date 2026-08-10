"""Deterministic in-world campaign clock primitives.

The clock deliberately separates:
- presentation time (campaign day + broad phase), which may be only partially known; and
- monotonic elapsed duration, which advances only when a duration is actually established.

This prevents the engine from inventing minute-level precision merely because the
fiction establishes a broad time of day.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping

CLOCK_SCHEMA_VERSION = 1
CLOCK_RECORD_ID = "campaign_clock"

PHASES = (
    "unknown",
    "dawn",
    "morning",
    "midday",
    "afternoon",
    "evening",
    "night",
    "late_night",
)

_PHASE_ORDER = {phase: index for index, phase in enumerate(PHASES) if phase != "unknown"}


def _require_int(value: Any, label: str, minimum: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise ValueError(f"{label} must be an integer >= {minimum}")
    return value


def _require_phase(value: Any, label: str = "clock.phase") -> str:
    if value not in PHASES:
        raise ValueError(f"{label} must be one of: {', '.join(PHASES)}")
    return str(value)


def initial_clock_state(
    *,
    day: int = 1,
    phase: str = "unknown",
    elapsed_campaign_minutes: int = 0,
    long_rests_completed: int = 0,
) -> dict[str, Any]:
    """Create a validated clock state.

    ``elapsed_campaign_minutes`` is a monotonic duration cursor measured from the
    runtime's chosen zero point. It is not a wall-clock minute-of-day value.
    """

    state = {
        "schema_version": CLOCK_SCHEMA_VERSION,
        "day": day,
        "phase": phase,
        "elapsed_campaign_minutes": elapsed_campaign_minutes,
        "long_rests_completed": long_rests_completed,
    }
    validate_clock_state(state)
    return state


def validate_clock_state(state: Mapping[str, Any]) -> None:
    if not isinstance(state, Mapping):
        raise ValueError("clock state must be an object")
    if state.get("schema_version") != CLOCK_SCHEMA_VERSION:
        raise ValueError(f"clock schema_version must be {CLOCK_SCHEMA_VERSION}")
    _require_int(state.get("day"), "clock.day", 1)
    _require_phase(state.get("phase"))
    _require_int(
        state.get("elapsed_campaign_minutes"),
        "clock.elapsed_campaign_minutes",
        0,
    )
    _require_int(state.get("long_rests_completed"), "clock.long_rests_completed", 0)


def observe_presentation_time(
    state: Mapping[str, Any],
    *,
    day: int | None = None,
    phase: str | None = None,
) -> dict[str, Any]:
    """Update only the established presentation-time facts.

    This function never changes the monotonic elapsed-duration cursor. Use it when
    the fiction establishes only a day/phase anchor without a trustworthy exact
    duration.
    """

    validate_clock_state(state)
    current = deepcopy(dict(state))
    current_day = int(current["day"])
    current_phase = str(current["phase"])

    observed_day = current_day if day is None else _require_int(day, "day", 1)
    if observed_day < current_day:
        raise ValueError("campaign day cannot move backwards")

    observed_phase = current_phase if phase is None else _require_phase(phase, "phase")

    if (
        observed_day == current_day
        and current_phase != "unknown"
        and observed_phase != "unknown"
        and _PHASE_ORDER[observed_phase] < _PHASE_ORDER[current_phase]
    ):
        raise ValueError("campaign phase cannot move backwards within the same day")

    current["day"] = observed_day
    current["phase"] = observed_phase
    validate_clock_state(current)
    return current


def advance_duration(
    state: Mapping[str, Any],
    minutes: int,
    *,
    long_rest_completed: bool = False,
) -> dict[str, Any]:
    """Advance only confirmed in-world duration.

    The day/phase are intentionally left untouched. A known duration does not grant
    permission to invent the exact presentation-time anchor when the starting
    minute-of-day is unknown.
    """

    validate_clock_state(state)
    duration = _require_int(minutes, "minutes", 0)
    if not isinstance(long_rest_completed, bool):
        raise ValueError("long_rest_completed must be boolean")

    current = deepcopy(dict(state))
    current["elapsed_campaign_minutes"] += duration
    if long_rest_completed:
        current["long_rests_completed"] += 1

    validate_clock_state(current)
    return current


def apply_time_update(
    state: Mapping[str, Any],
    *,
    elapsed_minutes: int | None = None,
    day: int | None = None,
    phase: str | None = None,
    long_rest_completed: bool = False,
) -> dict[str, Any]:
    """Apply one conservative semantic time update.

    Callers may supply:
    - only presentation facts (day/phase),
    - only a confirmed duration,
    - or both when both are established.

    If only a broad phase is known, omit ``elapsed_minutes`` so the monotonic cursor
    does not gain invented time.
    """

    validate_clock_state(state)
    current = deepcopy(dict(state))

    if elapsed_minutes is not None or long_rest_completed:
        duration = 0 if elapsed_minutes is None else elapsed_minutes
        current = advance_duration(
            current,
            duration,
            long_rest_completed=long_rest_completed,
        )

    if day is not None or phase is not None:
        current = observe_presentation_time(current, day=day, phase=phase)

    return current


def campaign_time_reached(
    state: Mapping[str, Any],
    *,
    target_day: int,
    target_phase: str,
) -> bool:
    """Return whether a broad campaign day/phase target is definitely reached."""

    validate_clock_state(state)
    day = _require_int(target_day, "target_day", 1)
    phase = _require_phase(target_phase, "target_phase")
    if phase == "unknown":
        raise ValueError("target_phase cannot be unknown")

    current_day = int(state["day"])
    if current_day > day:
        return True
    if current_day < day:
        return False

    current_phase = str(state["phase"])
    if current_phase == "unknown":
        return False
    return _PHASE_ORDER[current_phase] >= _PHASE_ORDER[phase]
