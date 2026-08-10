"""Reject populated values in every approved blank template."""

from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_DIRECTORY = ROOT / "templates"


def populated_values(value: object, path: str = "$") -> list[str]:
    if isinstance(value, dict):
        return [issue for key, child in value.items() for issue in populated_values(child, f"{path}.{key}")]
    if isinstance(value, list):
        return [issue for index, child in enumerate(value) for issue in populated_values(child, f"{path}[{index}]")]
    if value not in ("", None):
        return [path]
    return []


def main() -> int:
    failures: list[str] = []
    for template_path in sorted(TEMPLATE_DIRECTORY.rglob("*.json")):
        data = json.loads(template_path.read_text(encoding="utf-8"))
        for location in populated_values(data):
            failures.append(f"{template_path.relative_to(ROOT)}: populated value at {location}")
    if failures:
        print("\n".join(failures))
        return 1
    print("Blank-template validation passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
