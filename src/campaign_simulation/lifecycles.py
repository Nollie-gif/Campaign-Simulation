"""Generic state transitions for scenario and hook records."""

from __future__ import annotations


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
