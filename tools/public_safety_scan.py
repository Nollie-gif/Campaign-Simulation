"""Mechanically enforce the repository's written public-safety policy.

Scans every tracked file for secret-shaped strings and non-noreply email
addresses, and additionally inspects historical artifact files (DOCX/PDF
under artifacts/) for leftover author/reviewer metadata, comment or
tracked-changes parts, and embedded media. This does not replace human
judgement or the artifact library's own fidelity review; it exists so an
obvious mistake fails CI instead of waiting for the next manual audit.
"""

from __future__ import annotations

import re
import subprocess
import sys
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

ALLOWED_EMAIL_PATTERN = re.compile(r"^([0-9]+\+[\w-]+@users\.noreply\.github\.com|noreply@github\.com)$")
ALLOWED_EMAIL_DOMAINS = {"example.com", "example.org", "example.net"}

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
# personal name/identity and fails the scan. Shared by both DOCX core
# properties and PDF Info-dictionary metadata keys.
ALLOWED_METADATA_VALUES = {"", "python-docx", "Mission 10"}

CORE_PROPERTY_NS = {
    "dc": "http://purl.org/dc/elements/1.1/",
    "cp": "http://schemas.openxmlformats.org/package/2006/metadata/core-properties",
}

# Any Word "story" part that can carry visible/reviewable text and tracked
# changes, not just the main document body.
WORD_STORY_PART_PATTERN = re.compile(r"^word/(document|header\d*|footer\d*|footnotes|endnotes)\.xml$")

# Only /Author identifies a person, per the PDF spec's Info dictionary;
# /Creator and /Producer name the *application* that made the file (e.g.
# "Notes", "Quartz PDFContext") and are not personal-identity metadata.
PDF_METADATA_PATTERN = re.compile(rb"/Author\s*\((.*?)(?<!\\)\)", re.DOTALL)


def tracked_files() -> list[Path]:
    output = subprocess.run(
        ["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True
    ).stdout
    return [ROOT / line for line in output.splitlines() if line]


def _scan_text(relative: str, text: str, failures: list[str], *, where: str = "") -> None:
    suffix = f" {where}" if where else ""
    for label, pattern in SECRET_PATTERNS:
        if pattern.search(text):
            failures.append(f"{relative}:{suffix} possible {label}")
    for match in EMAIL_PATTERN.finditer(text):
        email = match.group(0)
        domain = email.rsplit("@", 1)[-1].lower()
        if ALLOWED_EMAIL_PATTERN.match(email) or domain in ALLOWED_EMAIL_DOMAINS:
            continue
        failures.append(f"{relative}:{suffix} non-noreply email address found ({email})")


def scan_text_file(path: Path, failures: list[str]) -> None:
    try:
        text = path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return
    relative = path.relative_to(ROOT).as_posix()
    _scan_text(relative, text, failures)


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
                core_bytes = archive.read("docProps/core.xml")
                try:
                    root = ET.fromstring(core_bytes)
                except ET.ParseError:
                    failures.append(f"{relative}: docProps/core.xml is not valid XML")
                else:
                    creator = root.find("dc:creator", CORE_PROPERTY_NS)
                    modifier = root.find("cp:lastModifiedBy", CORE_PROPERTY_NS)
                    for field_name, field_el in (("dc:creator", creator), ("cp:lastModifiedBy", modifier)):
                        value = (field_el.text or "").strip() if field_el is not None else ""
                        if value not in ALLOWED_METADATA_VALUES:
                            failures.append(
                                f"{relative}: {field_name} is set to an unreviewed value "
                                f"({value!r}) — add it to ALLOWED_METADATA_VALUES only after "
                                "confirming it is not a personal name"
                            )
            for name in sorted(names):
                if not WORD_STORY_PART_PATTERN.match(name):
                    continue
                content = archive.read(name).decode("utf-8", errors="replace")
                if "w:ins" in content or "w:del" in content:
                    failures.append(f"{relative}: {name} contains tracked-changes markup (w:ins/w:del)")
                _scan_text(relative, content, failures, where=f"{name}:")
    except zipfile.BadZipFile:
        failures.append(f"{relative}: not a valid zip/docx container")


def _pdf_unescape(raw: bytes) -> str:
    text = raw.replace(rb"\)", b")").replace(rb"\(", b"(").replace(rb"\\", b"\\")
    return text.decode("latin-1", errors="replace")


def scan_pdf_metadata(path: Path, failures: list[str]) -> None:
    relative = path.relative_to(ROOT).as_posix()
    try:
        data = path.read_bytes()
    except OSError:
        failures.append(f"{relative}: could not be read")
        return

    for match in PDF_METADATA_PATTERN.finditer(data):
        value = _pdf_unescape(match.group(1)).strip()
        if value and value not in ALLOWED_METADATA_VALUES:
            failures.append(
                f"{relative}: PDF /Author is set to an unreviewed value "
                f"({value!r}) — add it to ALLOWED_METADATA_VALUES only after "
                "confirming it is not a personal name"
            )

    # Scan the raw (undecoded) bytes only: page-content streams are usually
    # FlateDecode-compressed drawing operators/font data, and decompressing
    # them for generic email/secret pattern matching produces byte-garbage
    # false positives, not real text. A secret or address written as plain
    # PDF text (as in an Info dict, or an uncompressed string object) is
    # still visible here; one hidden only inside a compressed content
    # stream is a known, documented gap of this lightweight scanner.
    text = data.decode("latin-1", errors="replace")
    _scan_text(relative, text, failures)


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
        is_artifact = ARTIFACT_DIRECTORY in path.parents
        suffix = path.suffix.lower()
        if suffix == ".docx" and is_artifact:
            scan_docx_metadata(path, failures)
        elif suffix == ".pdf" and is_artifact:
            scan_pdf_metadata(path, failures)
        else:
            scan_text_file(path, failures)

    check_commit_identities(failures)

    if failures:
        print("Public-safety scan found issues:\n")
        print("\n".join(f"  - {f}" for f in failures))
        return 1
    print("Public-safety scan passed: no secrets, non-noreply emails, or artifact metadata leaks found.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
