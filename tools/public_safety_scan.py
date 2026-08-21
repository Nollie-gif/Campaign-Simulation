"""Mechanically enforce the repository's written public-safety policy.

Scans every tracked file for secret-shaped strings, non-noreply email
addresses, and (for historical DOCX/PDF artifacts) leftover author metadata
or comment/tracked-changes parts. This does not replace human judgement or
the artifact library's own fidelity review; it exists so an obvious mistake
fails CI instead of waiting for the next manual audit.
"""

from __future__ import annotations

import re
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

ALLOWED_EMAIL_PATTERN = re.compile(r"^[0-9]+\+[\w-]+@users\.noreply\.github\.com$")
ALLOWED_EMAIL_DOMAINS = {"example.com", "example.org", "example.net"}

# Text files only; binary artifacts (docx/pdf) get their own metadata check below.
TEXT_SUFFIXES = {
    ".py", ".md", ".txt", ".json", ".yml", ".yaml", ".toml", ".cfg", ".ini",
}

SECRET_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("AWS access key", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("GitHub token", re.compile(r"gh[pousr]_[A-Za-z0-9]{30,}")),
    ("GitHub fine-grained token", re.compile(r"github_pat_[A-Za-z0-9_]{20,}")),
    ("Private key header", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("Postgres/Supabase connection string with credentials",
     re.compile(r"postgres(?:ql)?://[^\s'\"]+:[^\s'\"]+@")),
    ("Slack token", re.compile(r"xox[baprs]-[A-Za-z0-9-]{10,}")),
    ("Generic API key assignment", re.compile(r"(?i)(api[_-]?key|secret|service_role)\s*[:=]\s*['\"][A-Za-z0-9_\-]{20,}['\"]")),
]

EMAIL_PATTERN = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")

ARTIFACT_DIRECTORY = ROOT / "artifacts"

# Reviewed, accepted non-personal values already present in the published
# artifact library. Anything outside this set is treated as a possible
# personal name/identity and fails the scan.
ALLOWED_DOCX_METADATA_VALUES = {"", "python-docx", "Mission 10"}


def tracked_files() -> list[Path]:
    output = subprocess.run(
        ["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True
    ).stdout
    return [ROOT / line for line in output.splitlines() if line]


def scan_text_file(path: Path, failures: list[str]) -> None:
    try:
        text = path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return
    relative = path.relative_to(ROOT).as_posix()
    for label, pattern in SECRET_PATTERNS:
        if pattern.search(text):
            failures.append(f"{relative}: possible {label}")
    for match in EMAIL_PATTERN.finditer(text):
        email = match.group(0)
        domain = email.rsplit("@", 1)[-1].lower()
        if ALLOWED_EMAIL_PATTERN.match(email) or domain in ALLOWED_EMAIL_DOMAINS:
            continue
        failures.append(f"{relative}: non-noreply email address found ({email})")


def scan_docx_metadata(path: Path, failures: list[str]) -> None:
    relative = path.relative_to(ROOT).as_posix()
    try:
        with zipfile.ZipFile(path) as archive:
            names = set(archive.namelist())
            if "word/comments.xml" in names:
                failures.append(f"{relative}: contains word/comments.xml (reviewer comments)")
            if "word/people.xml" in names:
                failures.append(f"{relative}: contains word/people.xml (tracked-change identities)")
            if any(name.startswith("word/media/") for name in names):
                failures.append(f"{relative}: contains embedded media under word/media/")
            if "docProps/core.xml" in names:
                core = archive.read("docProps/core.xml").decode("utf-8", errors="replace")
                creator = re.search(r"<dc:creator>(.*?)</dc:creator>", core)
                modifier = re.search(r"<cp:lastModifiedBy>(.*?)</cp:lastModifiedBy>", core)
                for field_name, field_match in (("dc:creator", creator), ("cp:lastModifiedBy", modifier)):
                    value = field_match.group(1).strip() if field_match else ""
                    if value not in ALLOWED_DOCX_METADATA_VALUES:
                        failures.append(
                            f"{relative}: {field_name} is set to an unreviewed value "
                            f"({value!r}) — add it to ALLOWED_DOCX_METADATA_VALUES only after "
                            "confirming it is not a personal name"
                        )
            if "word/document.xml" in names:
                doc = archive.read("word/document.xml").decode("utf-8", errors="replace")
                if "w:ins" in doc or "w:del" in doc:
                    failures.append(f"{relative}: contains tracked-changes markup (w:ins/w:del)")
    except zipfile.BadZipFile:
        failures.append(f"{relative}: not a valid zip/docx container")


def check_commit_identities(failures: list[str]) -> None:
    base = subprocess.run(
        ["git", "merge-base", "HEAD", "origin/main"],
        cwd=ROOT, capture_output=True, text=True,
    )
    if base.returncode != 0:
        return
    merge_base = base.stdout.strip()
    log = subprocess.run(
        ["git", "log", f"{merge_base}..HEAD", "--format=%H %ae %ce"],
        cwd=ROOT, capture_output=True, text=True, check=True,
    ).stdout
    for line in log.splitlines():
        parts = line.split(" ")
        if len(parts) < 3:
            continue
        sha, author_email, committer_email = parts[0], parts[1], parts[2]
        for role, email in (("author", author_email), ("committer", committer_email)):
            if not ALLOWED_EMAIL_PATTERN.match(email):
                failures.append(f"commit {sha[:8]}: {role} email is not a GitHub noreply address ({email})")


def main() -> int:
    failures: list[str] = []

    for path in tracked_files():
        if not path.is_file():
            continue
        if path.suffix.lower() in TEXT_SUFFIXES:
            scan_text_file(path, failures)
        elif path.suffix.lower() == ".docx" and ARTIFACT_DIRECTORY in path.parents:
            scan_docx_metadata(path, failures)

    check_commit_identities(failures)

    if failures:
        print("Public-safety scan found issues:\n")
        print("\n".join(f"  - {f}" for f in failures))
        return 1
    print("Public-safety scan passed: no secrets, non-noreply emails, or artifact metadata leaks found.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
