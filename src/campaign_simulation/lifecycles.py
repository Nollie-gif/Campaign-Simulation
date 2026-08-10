"""Generic state transitions for scenario and hook records."""

from __future__ import annotations

import json
import os
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator, Mapping


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

PERSISTED_IDENTIFIER_KINDS = {"hook": "hook", "scenario": "scenario"}


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


@contextmanager
def _session_state_lock(session_state_path: Path, timeout_seconds: float = 2.0) -> Iterator[None]:
    """Serialize cross-process identifier allocation for one session-state file."""

    session_state_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = session_state_path.with_name(f"{session_state_path.name}.lock")
    deadline = time.monotonic() + timeout_seconds
    descriptor: int | None = None
    while descriptor is None:
        try:
            descriptor = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            if time.monotonic() >= deadline:
                raise RuntimeError(f"session identifier allocator is locked: {session_state_path}")
            time.sleep(0.01)
    try:
        yield
    finally:
        os.close(descriptor)
        lock_path.unlink(missing_ok=True)


def _write_json_atomically(destination: Path, value: Mapping[str, Any]) -> None:
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, destination)


def allocate_persistent_identifier(session_state_path: Path, kind: str) -> str:
    """Allocate and durably persist a unique hook or scenario identifier.

    The counter is owned by the simulation session state, rather than by a caller's
    in-memory variable. This prevents an ordinary restart from recycling IDs.
    """

    if kind not in PERSISTED_IDENTIFIER_KINDS:
        raise ValueError(f"unsupported persisted identifier kind: {kind}")

    with _session_state_lock(session_state_path):
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
        _write_json_atomically(session_state_path, state)
        return identifier
