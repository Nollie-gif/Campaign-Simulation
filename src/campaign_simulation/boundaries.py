"""Hard ownership boundaries between a main campaign and its sequel runtime."""

from __future__ import annotations

from pathlib import Path


class CampaignBoundaryError(ValueError):
    """Raised when a sequel action could write into its read-only source."""


def assert_sequel_write_path(main_campaign_root: Path, sequel_write_path: Path) -> Path:
    """Return a safe write path or reject any overlap with the main campaign.

    The main campaign is an immutable source from the sequel engine's point of
    view. Rejecting both descendants and ancestors closes the easy mistake of
    choosing either the main-campaign folder itself or a broad parent folder as
    the sequel runtime.
    """

    main_root = main_campaign_root.resolve()
    target = sequel_write_path.resolve()
    try:
        target.relative_to(main_root)
    except ValueError:
        pass
    else:
        raise CampaignBoundaryError(
            "sequel runtime write path overlaps the read-only main campaign directory"
        )

    try:
        main_root.relative_to(target)
    except ValueError:
        return target
    raise CampaignBoundaryError(
        "sequel runtime write path is an ancestor of the read-only main campaign directory"
    )
