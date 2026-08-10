"""Hard ownership boundaries between a Main Campaign and simulation runtimes."""

from __future__ import annotations

from pathlib import Path


class CampaignBoundaryError(ValueError):
    """Raised when a simulation action could write into its read-only source."""


def assert_simulation_write_path(main_campaign_root: Path, simulation_write_path: Path) -> Path:
    """Return a safe write path or reject any overlap with the Main Campaign."""

    main_root = main_campaign_root.resolve()
    target = simulation_write_path.resolve()
    try:
        target.relative_to(main_root)
    except ValueError:
        pass
    else:
        raise CampaignBoundaryError(
            "simulation runtime write path overlaps the read-only main campaign directory"
        )

    try:
        main_root.relative_to(target)
    except ValueError:
        return target
    raise CampaignBoundaryError(
        "simulation runtime write path is an ancestor of the read-only main campaign directory"
    )


def assert_sequel_write_path(main_campaign_root: Path, sequel_write_path: Path) -> Path:
    """Backward-compatible alias for the branch-neutral write-boundary guard."""

    return assert_simulation_write_path(main_campaign_root, sequel_write_path)
