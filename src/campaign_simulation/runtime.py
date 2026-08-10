"""Safe simulation startup orchestration."""

from __future__ import annotations

from pathlib import Path

from .admission import admit_main_campaign
from .bootstrap import resolve_storage_mode


def initialize_sequel_runtime(
    main_campaign_root: Path,
    storage_config_path: Path,
    input_fn=input,
    external_probe=None,
) -> dict[str, object]:
    """Admit the source campaign before creating any sequel runtime state.

    Storage selection is intentionally second: a blocked sequel must not create
    a configuration file, prompt for Supabase, or write any simulation data.
    """
    manifest = admit_main_campaign(main_campaign_root)
    storage = resolve_storage_mode(storage_config_path, input_fn, external_probe)
    return {"main_campaign": manifest, "storage": storage}
