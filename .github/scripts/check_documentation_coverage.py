from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

IMPLEMENTATION_PREFIXES = (
    "src/",
    "schemas/",
    "scripts/",
    "templates/",
    ".github/workflows/",
)
IMPLEMENTATION_FILES = {"pyproject.toml"}
DOCUMENTATION_PREFIXES = ("docs/",)
DOCUMENTATION_FILES = {
    "README.md",
    "HUMAN_README.md",
    "INSTALLATION_GUIDE.md",
    "CHANGELOG.md",
    "CAMPAIGN_CLOCK_README.md",
    ".github/copilot-instructions.md",
}
PLACEHOLDER_REASONS = {"replace this text", "n/a", "na", "none"}


def changed_files(base: str, head: str) -> list[str]:
    result = subprocess.run(
        ["git", "diff", "--name-only", f"{base}...{head}"],
        check=True,
        text=True,
        capture_output=True,
    )
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def is_implementation(path: str) -> bool:
    return path in IMPLEMENTATION_FILES or path.startswith(IMPLEMENTATION_PREFIXES)


def is_documentation(path: str) -> bool:
    return path in DOCUMENTATION_FILES or path.startswith(DOCUMENTATION_PREFIXES)


def pull_request_body() -> str:
    event_path = os.environ.get("GITHUB_EVENT_PATH")
    if not event_path:
        return ""
    payload = json.loads(Path(event_path).read_text(encoding="utf-8"))
    return str((payload.get("pull_request") or {}).get("body") or "")


def explicit_no_impact_exemption(body: str) -> tuple[bool, str]:
    impact = re.search(r"^Documentation impact:\s*none\s*$", body, re.MULTILINE | re.IGNORECASE)
    reason = re.search(r"^Documentation reason:\s*(.+?)\s*$", body, re.MULTILINE | re.IGNORECASE)
    if not impact or not reason:
        return False, ""
    text = reason.group(1).strip()
    if not text or text.lower() in PLACEHOLDER_REASONS:
        return False, text
    return True, text


def main() -> int:
    if len(sys.argv) != 3:
        print("usage: check_documentation_coverage.py <base-sha> <head-sha>")
        return 2

    files = changed_files(sys.argv[1], sys.argv[2])
    implementation = [path for path in files if is_implementation(path)]
    documentation = [path for path in files if is_documentation(path)]

    print("Changed files:")
    for path in files:
        print(f"  - {path}")

    if not implementation:
        print("Documentation Coverage Gate: PASS (no implementation-sensitive files changed).")
        return 0

    if documentation:
        print("Documentation Coverage Gate: PASS")
        print("Implementation-sensitive changes are accompanied by repository documentation:")
        for path in documentation:
            print(f"  - {path}")
        return 0

    exempt, reason = explicit_no_impact_exemption(pull_request_body())
    if exempt:
        print("Documentation Coverage Gate: PASS (explicit no-impact exemption).")
        print(f"Reason: {reason}")
        return 0

    print("Documentation Coverage Gate: FAIL", file=sys.stderr)
    print("Implementation-sensitive files changed without a repository documentation update.", file=sys.stderr)
    print("Update the relevant repository docs in this PR, or use the explicit PR-body no-impact exemption with a real reason for behavior-neutral work.", file=sys.stderr)
    print("Implementation-sensitive files:", file=sys.stderr)
    for path in implementation:
        print(f"  - {path}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
