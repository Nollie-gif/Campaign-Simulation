"""Safe simulation startup orchestration."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .admission import admit_main_campaign
from .boundaries import assert_sequel_write_path
from .bootstrap import resolve_storage_mode
from .onboarding import build_optional_material_menu, continue_from_optional_material


def begin_sequel_onboarding(main_campaign_root: Path) -> dict[str, Any]:
    """Admit the campaign, then show capabilities before storage setup."""
    manifest = admit_main_campaign(main_campaign_root)
    return {
        "main_campaign": manifest,
        "status": "choose_optional_material",
        "optional_material_menu": build_optional_material_menu(),
        "storage": None,
    }


def complete_sequel_onboarding(
    main_campaign_root: Path,
    storage_config_path: Path,
    selected_optional_material: list[str],
    input_fn=input,
    external_probe=None,
) -> dict[str, object]:
    """Complete storage setup after the optional-material choice.

    A blocked campaign therefore cannot create a configuration file or prompt
    for Supabase. An admitted campaign may continue with an empty selection.
    """
    manifest = admit_main_campaign(main_campaign_root)
    # ``storage_config_path`` is a file *inside* the selected runtime. Guard
    # the runtime directory itself so `--runtime /a-parent-of-main` is refused.
    assert_sequel_write_path(main_campaign_root, storage_config_path.parent)
    optional_material = continue_from_optional_material(selected_optional_material)
    storage = resolve_storage_mode(storage_config_path, input_fn, external_probe)
    return {"main_campaign": manifest, "optional_material": optional_material, "storage": storage}
