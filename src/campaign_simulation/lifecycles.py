"""Generic state transitions for scenario, hook, and deferred-event records."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from ._atomic import write_json_atomically
from .lock import advisory_lock, LockAcquireTimeout

SCENARIO_TRANSITIONS = {
    "draft": {"available"},
    "available": {"active", "abandoned", "expired"},
    "active": {"completed", "abandoned", "expired"},
    "completed": set(),
    "abandoned": set(),
    "expired": set(),
}

HOOK_TRANSITIONS = {
    "dormant": {"active", "retired"},
    "active": {"resolved", "retired"},
    "resolved": set(),
    "retired": set(),
}

EVENT_TRANSITIONS = {
    "pending": {"resolved", "cancelled"},
    "resolved": set(),
    "cancelled": set(),
}

PERSISTED_IDENTIFIER_KINDS = {
    "hook": "hook",
    "scenario": "scenario",
    "event": "event",
}


def transition(current: str, target: str, transitions: dict[str, set[str]]) -> str:
    """Validate and return a one-way lifecycle transition."""
    if target not in transitions.get(current, set()):
        raise ValueError(f"transition is not allowed: {current!r} -> {target!r}")
    return target


def allocate_identifier(prefix: str, next_value: int) -> tuple[str, int]:
    """Allocate a permanent identifier and the next unrecycled counter value."""
    if not prefix.strip():
        raise ValueError("identifier prefix is required")
    if next_value < 1:
        raise ValueError("next identifier counter must be positive")
    return f"{prefix}-{next_value:06d}", next_value + 1


def allocate_persistent_identifier(session_state_path: Path, kind: str, lock_timeout: float = 2.0) -> str:
    """Allocate and durably persist a unique hook, scenario, or event identifier.

    The counter is owned by the simulation session state, rather than by a caller's
    in-memory variable. This prevents an ordinary restart from recycling IDs.

    This function uses an advisory file lock to serialize cross-process access.
    The lock file is persistent and ownership is represented only by the OS-level
    advisory lock held on an open file descriptor; the lock file is not created
    or removed to represent ownership.
    """

    if kind not in PERSISTED_IDENTIFIER_KINDS:
        raise ValueError(f"unsupported persisted identifier kind: {kind}")

    lock_path = session_state_path.with_name(f"{session_state_path.name}.lock")

    try:
        with advisory_lock(lock_path, timeout_seconds=lock_timeout):
            if session_state_path.exists():
                try:
                    state = json.loads(session_state_path.read_text(encoding="utf-8"))
                except json.JSONDecodeError as error:
                    raise ValueError("session state is not valid JSON") from error
                if not isinstance(state, dict):
                    raise ValueError("session state must be a JSON object")
            else:
                state = {}

            counters = state.get("identifier_counters", {})
            if not isinstance(counters, dict):
                raise ValueError("session identifier_counters must be an object")
            next_value = counters.get(kind, 1)
            if isinstance(next_value, bool) or not isinstance(next_value, int) or next_value < 1:
                raise ValueError(f"session counter for {kind} must be a positive integer")

            identifier, next_value = allocate_identifier(PERSISTED_IDENTIFIER_KINDS[kind], next_value)
            counters[kind] = next_value
            state["identifier_counters"] = counters

            write_json_atomically(session_state_path, state, fsync_parent=True)
            return identifier
    except LockAcquireTimeout as error:
        raise RuntimeError(f"session identifier allocator is locked: {session_state_path}") from error

