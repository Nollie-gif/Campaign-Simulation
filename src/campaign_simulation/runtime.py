"""Safe branch-neutral simulation startup orchestration."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from .admission import admit_main_campaign
from .boundaries import assert_simulation_write_path
from .bootstrap import resolve_storage_mode
from .branches import SEQUEL_MODE, build_exploration_menu, persist_simulation_branch, resolve_simulation_branch
from .onboarding import build_optional_material_menu, continue_from_optional_material


def begin_simulation_onboarding(main_campaign_root: Path) -> dict[str, Any]:
    """Admit the Main Campaign before asking which branch the user wants."""

    manifest = admit_main_campaign(main_campaign_root)
    return {
        "main_campaign": manifest,
        "status": "choose_simulation_mode",
        "exploration_menu": build_exploration_menu(),
        "optional_material_menu": build_optional_material_menu(),
        "storage": None,
    }


def complete_simulation_onboarding(
    main_campaign_root: Path,
    runtime_root: Path,
    branch: Mapping[str, object],
    selected_optional_material: list[str],
    input_fn=input,
    external_probe=None,
) -> dict[str, object]:
    """Persist the chosen branch and complete storage setup in a safe runtime."""

    manifest = admit_main_campaign(main_campaign_root)
    safe_runtime = assert_simulation_write_path(main_campaign_root, runtime_root)
    resolved_branch = resolve_simulation_branch(
        manifest,
        str(branch.get("mode", "")),
        str(branch.get("anchor", "")),
    )
    for field in ("relative_position", "time_direction", "main_campaign_access", "boundary_behavior"):
        if branch.get(field) != resolved_branch[field]:
            raise ValueError(f"simulation branch {field} is invalid")

    optional_material = continue_from_optional_material(selected_optional_material)
    stored_branch = persist_simulation_branch(safe_runtime / "simulation-branch.json", resolved_branch)
    storage = resolve_storage_mode(
        safe_runtime / "storage-configuration.json",
        input_fn,
        external_probe,
    )
    return {
        "main_campaign": manifest,
        "branch": stored_branch,
        "optional_material": optional_material,
        "storage": storage,
    }


def begin_sequel_onboarding(main_campaign_root: Path) -> dict[str, Any]:
    """Backward-compatible entry point; new callers should use branch-neutral onboarding."""

    state = begin_simulation_onboarding(main_campaign_root)
    state["status"] = "choose_optional_material"
    return state


def complete_sequel_onboarding(
    main_campaign_root: Path,
    storage_config_path: Path,
    selected_optional_material: list[str],
    input_fn=input,
    external_probe=None,
) -> dict[str, object]:
    """Backward-compatible sequel wrapper around branch-neutral onboarding."""

    manifest = admit_main_campaign(main_campaign_root)
    branch = resolve_simulation_branch(manifest, SEQUEL_MODE)
    return complete_simulation_onboarding(
        main_campaign_root,
        storage_config_path.parent,
        branch,
        selected_optional_material,
        input_fn,
        external_probe,
    )
