"""First-boot storage selection with a safe repository fallback."""

from __future__ import annotations

import json
from pathlib import Path


REPOSITORY_MODE = "repository"
SUPABASE_MODE = "supabase"


def resolve_storage_mode(config_path: Path, input_fn=input, external_probe=None) -> dict[str, str]:
    """Return persisted configuration, asking only when no local configuration exists."""
    if config_path.exists():
        return json.loads(config_path.read_text(encoding="utf-8"))

    answer = input_fn("Storage mode [repository/supabase] (repository): ").strip().lower()
    mode = SUPABASE_MODE if answer == SUPABASE_MODE else REPOSITORY_MODE
    configuration = {"storage_mode": mode, "fallback_reason": ""}

    if mode == SUPABASE_MODE:
        url = input_fn("Supabase URL: ").strip()
        probe = external_probe or (lambda candidate: bool(candidate))
        if not url or not probe(url):
            configuration = {
                "storage_mode": REPOSITORY_MODE,
                "fallback_reason": "external connection was unavailable",
            }
        else:
            configuration["supabase_url"] = url

    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(json.dumps(configuration, indent=2) + "\n", encoding="utf-8")
    return configuration
