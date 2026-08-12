"""Side-effect-free automatic autosave policy for campaign simulations."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping

from .clock import PHASES, validate_clock_state

AUTOSAVE_SCHEMA_VERSION = 1
AUTOSAVE_RECORD_ID = "autosave_state"

CHANGE_LEVELS = ("none", "minor", "meaningful", "major", "critical")
ORDINARY_AUTOSAVE_SOFT_CAP = 5
ACCUMULATED_SCENE_THRESHOLD = 3


def _require_int(value: Any, label: str, minimum: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise ValueError(f"{label} must be an integer >= {minimum}")
    return value


def _require_bool(value: Any, label: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{label} must be boolean")
    return value


def _require_phase(value: Any, label: str) -> str:
    if value not in PHASES:
        raise ValueError(f"{label} must be one of: {', '.join(PHASES)}")
    return str(value)


def initial_autosave_state(clock_state: Mapping[str, Any]) -> dict[str, Any]:
    validate_clock_state(clock_state)
    state = {
        "schema_version": AUTOSAVE_SCHEMA_VERSION,
        "last_observed_day": clock_state["day"],
        "last_observed_phase": clock_state["phase"],
        "automatic_saves_today": 0,
        "last_autosave_day": None,
        "last_autosave_phase": None,
        "resolved_scenes_since_autosave": 0,
        "meaningful_changes_since_autosave": False,
        "last_saved_state_fingerprint": None,
    }
    validate_autosave_state(state)
    return state


def validate_autosave_state(state: Mapping[str, Any]) -> None:
    if not isinstance(state, Mapping):
        raise ValueError("autosave state must be an object")
    if state.get("schema_version") != AUTOSAVE_SCHEMA_VERSION:
        raise ValueError(f"autosave schema_version must be {AUTOSAVE_SCHEMA_VERSION}")
    _require_int(state.get("last_observed_day"), "autosave.last_observed_day", 1)
    _require_phase(state.get("last_observed_phase"), "autosave.last_observed_phase")
    _require_int(state.get("automatic_saves_today"), "autosave.automatic_saves_today")
    _require_int(
        state.get("resolved_scenes_since_autosave"),
        "autosave.resolved_scenes_since_autosave",
    )
    _require_bool(
        state.get("meaningful_changes_since_autosave"),
        "autosave.meaningful_changes_since_autosave",
    )

    last_day = state.get("last_autosave_day")
    if last_day is not None:
        _require_int(last_day, "autosave.last_autosave_day", 1)

    last_phase = state.get("last_autosave_phase")
    if last_phase is not None:
        _require_phase(last_phase, "autosave.last_autosave_phase")

    fingerprint = state.get("last_saved_state_fingerprint")
    if fingerprint is not None and not isinstance(fingerprint, str):
        raise ValueError("autosave.last_saved_state_fingerprint must be string or null")


def validate_turn_assessment(assessment: Mapping[str, Any]) -> None:
    if not isinstance(assessment, Mapping):
        raise ValueError("turn assessment must be an object")
    _require_bool(assessment.get("scene_resolved", False), "assessment.scene_resolved")
    if assessment.get("change_level") not in CHANGE_LEVELS:
        raise ValueError(
            "assessment.change_level must be one of: " + ", ".join(CHANGE_LEVELS)
        )
    _require_bool(
        assessment.get("manual_save_requested", False),
        "assessment.manual_save_requested",
    )
    fingerprint = assessment.get("state_fingerprint")
    if fingerprint is not None and not isinstance(fingerprint, str):
        raise ValueError("assessment.state_fingerprint must be string or null")


def evaluate_autosave(
    state: Mapping[str, Any],
    clock_state: Mapping[str, Any],
    assessment: Mapping[str, Any],
) -> dict[str, Any]:
    """Evaluate one gameplay boundary and return a decision plus next state.

    The function never persists anything. ``trigger=True`` means the active
    persistence adapter should enter its normal validated save flow.
    """

    validate_autosave_state(state)
    validate_clock_state(clock_state)
    validate_turn_assessment(assessment)

    current = deepcopy(dict(state))
    previous_day = current["last_observed_day"]
    previous_phase = current["last_observed_phase"]
    new_day = clock_state["day"]
    new_phase = clock_state["phase"]

    if new_day < previous_day:
        raise ValueError("autosave clock observation cannot move backwards")

    day_changed = new_day != previous_day
    phase_changed = (
        not day_changed
        and new_phase != "unknown"
        and previous_phase != "unknown"
        and new_phase != previous_phase
    )

    if day_changed:
        current["automatic_saves_today"] = 0

    current["last_observed_day"] = new_day
    current["last_observed_phase"] = new_phase

    if assessment.get("scene_resolved", False):
        current["resolved_scenes_since_autosave"] += 1

    change_level = assessment["change_level"]
    meaningful_now = change_level in {"meaningful", "major", "critical"}
    current["meaningful_changes_since_autosave"] = (
        current["meaningful_changes_since_autosave"] or meaningful_now
    )

    fingerprint = assessment.get("state_fingerprint")
    duplicate_state = (
        fingerprint is not None
        and fingerprint == current.get("last_saved_state_fingerprint")
    )
    manual = assessment.get("manual_save_requested", False)
    critical = change_level == "critical"
    major = change_level == "major"
    has_meaningful_progress = current["meaningful_changes_since_autosave"]
    scenes = current["resolved_scenes_since_autosave"]
    cap_reached = current["automatic_saves_today"] >= ORDINARY_AUTOSAVE_SOFT_CAP

    trigger = False
    reason = "no_trigger"
    automatic = False

    if manual:
        trigger = True
        reason = "manual_request"
    elif duplicate_state:
        reason = "duplicate_state"
    elif critical:
        trigger = True
        automatic = True
        reason = "critical_persistence_boundary"
    elif cap_reached:
        reason = "ordinary_autosave_soft_cap_reached"
    elif major:
        trigger = True
        automatic = True
        reason = "major_persistent_event"
    elif day_changed and has_meaningful_progress:
        trigger = True
        automatic = True
        reason = "day_transition"
    elif phase_changed and has_meaningful_progress:
        trigger = True
        automatic = True
        reason = "day_phase_transition"
    elif scenes >= ACCUMULATED_SCENE_THRESHOLD and has_meaningful_progress:
        trigger = True
        automatic = True
        reason = "accumulated_meaningful_progress"

    if trigger:
        if automatic:
            current["automatic_saves_today"] += 1
        current["last_autosave_day"] = new_day
        current["last_autosave_phase"] = new_phase
        current["resolved_scenes_since_autosave"] = 0
        current["meaningful_changes_since_autosave"] = False
        if fingerprint is not None:
            current["last_saved_state_fingerprint"] = fingerprint

    validate_autosave_state(current)
    return {
        "trigger": trigger,
        "automatic": automatic,
        "reason": reason,
        "target_autosaves_per_day": "3-5",
        "ordinary_soft_cap": ORDINARY_AUTOSAVE_SOFT_CAP,
        "state": current,
    }

