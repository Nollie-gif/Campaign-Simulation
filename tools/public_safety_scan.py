"""Mechanically enforce the repository's written public-safety policy.

Scans every tracked file for secret-shaped strings and non-noreply email
addresses, and additionally inspects historical artifact files (DOCX/PDF
under artifacts/) for leftover author/reviewer metadata, comment or
tracked-changes parts, and embedded media. This does not replace human
judgement or the artifact library's own fidelity review; it exists so an
obvious mistake fails CI instead of waiting for the next manual audit.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Both GitHub noreply forms on the users.noreply.github.com domain are
# valid: the modern one prefixed with a numeric account id and a "+", and
# the bare-username form issued to older accounts. GitHub's own synthetic
# committer address on the plain github.com domain is accepted too.
# Bot accounts carry a bracketed suffix in the username component
# (e.g. dependabot and github-actions), which is still a valid noreply
# address and must not fail the identity gate.
ALLOWED_EMAIL_PATTERN = re.compile(
    r"^(([0-9]+\+)?[\w.\[\]-]+@users\.noreply\.github\.com|noreply@github\.com)$"
)
ALLOWED_EMAIL_DOMAINS = {"example.com", "example.org", "example.net"}

SECRET_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("AWS access key", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("GitHub token", re.compile(r"gh[pousr]_[A-Za-z0-9]{30,}")),
    ("GitHub fine-grained token", re.compile(r"github_pat_[A-Za-z0-9_]{20,}")),
    ("Private key header", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("Postgres/Supabase connection string with credentials",
     re.compile(r"postgres(?:ql)?://[^\s'\"]+:[^\s'\"]+@")),
    ("Slack token", re.compile(r"xox[baprs]-[A-Za-z0-9-]{10,}")),
    # Quotes are optional: the common dotenv/shell form is unquoted
    # (OPENAI_API_KEY=sk-proj-..., secret=...), which a quoted-only
    # pattern silently misses.
    ("Generic API key assignment", re.compile(r"(?i)(api[_-]?key|secret|service_role)\s*[:=]\s*['\"]?[A-Za-z0-9_\-]{20,}['\"]?")),
]

EMAIL_PATTERN = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")

ARTIFACT_DIRECTORY = ROOT / "artifacts"

# Reviewed, accepted non-personal values already present in the published
# artifact library. Anything outside this set is treated as a possible
# personal name/identity and fails the scan. Shared by both DOCX core
# properties and PDF Info-dictionary metadata keys.
# "Normal"/"Normal.dotm" are Word's default global template names, present
# in nearly every DOCX; they name no person and reveal no private path. A
# Template value that *is* a private path (…/Users/<name>/…) is not in this
# set and still fails.
ALLOWED_METADATA_VALUES = {"", "python-docx", "Mission 10", "Normal", "Normal.dotm"}

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
# A PDF string can be written as a parenthesized literal OR a hex string
# (PDF 32000-1:2008, 7.9.2.2/7.9.2.4) — Unicode text strings are commonly
# hex-encoded UTF-16BE with a leading FEFF BOM — so both forms are checked.
PDF_METADATA_LITERAL_PATTERN = re.compile(rb"/Author\s*\((.*?)(?<!\\)\)", re.DOTALL)
PDF_METADATA_HEX_PATTERN = re.compile(rb"/Author\s*<([0-9A-Fa-f\s]*)>")

# A PDF may carry authorship only in an XMP metadata packet (dc:creator),
# with no Info-dictionary /Author entry at all.
PDF_XMP_CREATOR_PATTERN = re.compile(rb"<dc:creator>(.*?)</dc:creator>", re.DOTALL)
XMP_RDF_LI_PATTERN = re.compile(rb"<rdf:li[^>]*>(.*?)</rdf:li>", re.DOTALL)


def tracked_files() -> list[Path]:
    # -z: NUL-delimited and never quoted/C-escaped. Plain `git ls-files`
    # renders a non-ASCII path as "r\303\251sum\303\251.env" under the
    # default core.quotePath, which would build a Path that does not exist
    # and be silently skipped — leaving that file unscanned.
    output = subprocess.run(
        ["git", "ls-files", "-z"], cwd=ROOT, capture_output=True, check=True
    ).stdout
    return [
        ROOT / name.decode("utf-8", errors="surrogateescape")
        for name in output.split(b"\x00")
        if name
    ]


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
        raw = path.read_bytes()
    except OSError:
        return
    # Windows tooling commonly writes UTF-16; decoding only as UTF-8 would
    # raise and silently skip the file, leaving its contents unscanned.
    if raw.startswith((b"\xff\xfe", b"\xfe\xff")):
        encodings = ("utf-16", "utf-8")
    else:
        encodings = ("utf-8", "utf-16")
    for encoding in encodings:
        try:
            text = raw.decode(encoding)
            break
        except (UnicodeDecodeError, UnicodeError):
            continue
    else:
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
                content_bytes = archive.read(name)
                content = content_bytes.decode("utf-8", errors="replace")
                try:
                    story_root = ET.fromstring(content_bytes)
                except ET.ParseError:
                    story_root = None
                if story_root is not None:
                    # Element-name match (not a "w:ins"/"w:del" substring
                    # search, which also matches unrelated field codes like
                    # <w:instrText>) for the real tracked-change elements.
                    if any(el.tag.rpartition("}")[2] in ("ins", "del") for el in story_root.iter()):
                        failures.append(f"{relative}: {name} contains tracked-changes markup (w:ins/w:del)")
                    # Word displays adjacent <w:t> runs as one continuous
                    # string with no separator, so a secret/email split
                    # across runs by formatting is joined the same way
                    # before scanning — the raw-XML scan below would miss it.
                    # Structural boundaries (paragraph, table row/cell, tab,
                    # line break) are NOT displayed as continuous text, so
                    # they emit a separator: joining across them would
                    # invent addresses that the document never shows.
                    pieces: list[str] = []
                    for el in story_root.iter():
                        tag = el.tag.rpartition("}")[2]
                        if tag in ("p", "tr", "tc", "tab", "br", "cr"):
                            pieces.append("\n")
                        elif tag == "t" and el.text:
                            pieces.append(el.text)
                    joined_text = "".join(pieces)
                    if joined_text.strip():
                        _scan_text(relative, joined_text, failures, where=f"{name} (joined text):")
                elif "w:ins" in content or "w:del" in content:
                    failures.append(f"{relative}: {name} contains tracked-changes markup (w:ins/w:del)")
                _scan_text(relative, content, failures, where=f"{name}:")
            # Extended/custom property parts carry identity and private-path
            # metadata (Manager, Company, Template, custom properties) that
            # never appears in core.xml. Artifact DOCX files skip the plain
            # text scanner, so these parts would otherwise go uninspected.
            for name in sorted(names):
                if name not in ("docProps/app.xml", "docProps/custom.xml"):
                    continue
                props = archive.read(name).decode("utf-8", errors="replace")
                _scan_text(relative, props, failures, where=f"{name}:")
                try:
                    props_root = ET.fromstring(archive.read(name))
                except ET.ParseError:
                    continue
                for el in props_root.iter():
                    tag = el.tag.rpartition("}")[2]
                    value = (el.text or "").strip()
                    if tag in ("Manager", "Company", "Template") and value:
                        if value not in ALLOWED_METADATA_VALUES:
                            failures.append(
                                f"{relative}: {name} {tag} is set to an unreviewed value "
                                f"({value!r}) — add it to ALLOWED_METADATA_VALUES only after "
                                "confirming it is not a personal name or private path"
                            )

            # Relationship parts hold hyperlink targets — a mailto: address,
            # a credential-bearing URL, or a local path lives here, not in
            # any story part.
            for name in sorted(names):
                if not name.endswith(".rels"):
                    continue
                rels_bytes = archive.read(name)
                _scan_text(relative, rels_bytes.decode("utf-8", errors="replace"),
                           failures, where=f"{name}:")
                # Targets must be scanned as parsed attribute values: an
                # entity-encoded address (mailto:alice&#64;…) carries no
                # literal "@" in the serialized XML, but Word resolves it.
                try:
                    rels_root = ET.fromstring(rels_bytes)
                except ET.ParseError:
                    continue
                for el in rels_root.iter():
                    target = el.get("Target")
                    if target:
                        _scan_text(relative, target, failures, where=f"{name} (Target):")
    except zipfile.BadZipFile:
        failures.append(f"{relative}: not a valid zip/docx container")


def _pdf_unescape(raw: bytes) -> str:
    text = raw.replace(rb"\)", b")").replace(rb"\(", b"(").replace(rb"\\", b"\\")
    return text.decode("latin-1", errors="replace")


def _pdf_decode_hex_string(raw: bytes) -> str:
    try:
        data = bytes.fromhex(re.sub(rb"\s+", b"", raw).decode("ascii"))
    except ValueError:
        return ""
    if data.startswith(b"\xfe\xff"):
        return data[2:].decode("utf-16-be", errors="replace")
    return data.decode("latin-1", errors="replace")


def scan_pdf_metadata(path: Path, failures: list[str]) -> None:
    relative = path.relative_to(ROOT).as_posix()
    try:
        data = path.read_bytes()
    except OSError:
        failures.append(f"{relative}: could not be read")
        return

    author_values = [
        _pdf_unescape(match.group(1)) for match in PDF_METADATA_LITERAL_PATTERN.finditer(data)
    ] + [
        _pdf_decode_hex_string(match.group(1)) for match in PDF_METADATA_HEX_PATTERN.finditer(data)
    ]
    for raw_value in author_values:
        value = raw_value.strip()
        if value and value not in ALLOWED_METADATA_VALUES:
            failures.append(
                f"{relative}: PDF /Author is set to an unreviewed value "
                f"({value!r}) — add it to ALLOWED_METADATA_VALUES only after "
                "confirming it is not a personal name"
            )

    for match in PDF_XMP_CREATOR_PATTERN.finditer(data):
        block = match.group(1)
        entries = [m.group(1) for m in XMP_RDF_LI_PATTERN.finditer(block)] or [block]
        for entry in entries:
            value = entry.decode("utf-8", errors="replace").strip()
            if value and value not in ALLOWED_METADATA_VALUES:
                failures.append(
                    f"{relative}: PDF XMP dc:creator is set to an unreviewed value "
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


_NULL_SHA = "0" * 40


def check_commit_identities(failures: list[str]) -> None:
    # On a direct push to main, actions/checkout leaves origin/main pointing
    # at the same commit as HEAD (the push already landed before CI ran), so
    # `merge-base HEAD origin/main` is HEAD itself and `git log HEAD..HEAD`
    # is empty — the pushed commit's own identity would never be checked.
    # CI passes the pre-push SHA (`github.event.before`) via this env var so
    # a direct push to main is checked against its real prior state; a PR's
    # merge-base-vs-origin/main logic below is unaffected (the env var is
    # only set for push events) and unused/local runs fall back to it too.
    override_base = os.environ.get("PUBLIC_SAFETY_COMMIT_RANGE_BASE", "").strip()
    if override_base and override_base != _NULL_SHA:
        merge_base = override_base
    else:
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
