"""Regression tests for tools/public_safety_scan.py.

Each test reproduces one of the defects found by adversarial PR review of
the original implementation (PR #17): a fixture that should fail the scan
but did not under the original coverage-suffix allowlist / metadata-regex
approach. Run against an isolated throwaway git repo so the fixtures never
touch this repository's own tracked history.
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SCAN_PATH = ROOT / "tools" / "public_safety_scan.py"

# Every secret- and address-shaped fixture is assembled at runtime, so this
# file contains no contiguous match for the scanner's own patterns and can
# therefore be scanned in full by the tool it tests. A blanket
# path exemption was the earlier approach and was strictly worse: it would
# have skipped a real credential accidentally committed here.
_AWS_KEY = "AKIA" + "ABCDEFGHIJKLMNOP"
_GH_PAT = "github_pat_" + "1234567890ABCDEFGHIJ"
_OPENAI_KEY = "sk-proj-" + "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
_GENERIC_VALUE = "abcdefghijklmnopqrstuvwxyz" + "123456"
_COMPANY = "real-" + "company.com"
_NON_NOREPLY = "real.human" + "@" + "example-not-noreply.com"


def _addr(user: str) -> str:
    return user + "@" + _COMPANY


def _load_scan_module():
    spec = importlib.util.spec_from_file_location("public_safety_scan_under_test", SCAN_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _run_scan(repo_root: Path, module) -> list[str]:
    module.ROOT = repo_root
    module.ARTIFACT_DIRECTORY = repo_root / "artifacts"
    failures: list[str] = []
    for path in module.tracked_files():
        if not path.is_file():
            continue
        is_artifact = module.ARTIFACT_DIRECTORY in path.parents
        suffix = path.suffix.lower()
        if suffix == ".docx" and is_artifact:
            module.scan_docx_metadata(path, failures)
        elif suffix == ".pdf" and is_artifact:
            module.scan_pdf_metadata(path, failures)
        else:
            module.scan_text_file(path, failures)
    return failures


def _make_docx(path: Path, *, creator: str = "", modified_by: str = "",
               core_attrs: str = "", document_xml: str | None = None,
               extra_parts: dict[str, str] | None = None) -> None:
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("[Content_Types].xml", "<Types/>")
        archive.writestr(
            "docProps/core.xml",
            '<?xml version="1.0"?><cp:coreProperties '
            'xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" '
            'xmlns:dc="http://purl.org/dc/elements/1.1/">'
            f'<dc:creator{core_attrs}>{creator}</dc:creator>'
            f'<cp:lastModifiedBy>{modified_by}</cp:lastModifiedBy>'
            '</cp:coreProperties>',
        )
        archive.writestr(
            "word/document.xml",
            document_xml
            or '<?xml version="1.0"?><w:document xmlns:w="ns"><w:body><w:p/></w:body></w:document>',
        )
        for name, content in (extra_parts or {}).items():
            archive.writestr(name, content)


class PublicSafetyScanRegressionTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="psafety_test_")
        self.addCleanup(self._tmp.cleanup)
        self.repo_root = Path(self._tmp.name) / "root"
        self.repo_root.mkdir()
        subprocess.run(["git", "init", "-q"], cwd=self.repo_root, check=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=self.repo_root, check=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=self.repo_root, check=True)
        (self.repo_root / "artifacts").mkdir()
        self.module = _load_scan_module()

    def _commit(self) -> None:
        subprocess.run(["git", "add", "-A"], cwd=self.repo_root, check=True)
        subprocess.run(["git", "commit", "-q", "-m", "fixture"], cwd=self.repo_root, check=True)

    def test_clean_tree_has_no_false_positives(self) -> None:
        (self.repo_root / "README.md").write_text("Nothing sensitive here.\n")
        _make_docx(self.repo_root / "artifacts" / "clean.docx", creator="", modified_by="")
        self._commit()
        self.assertEqual(_run_scan(self.repo_root, self.module), [])

    def test_finding1_scans_files_outside_old_suffix_allowlist(self) -> None:
        (self.repo_root / "secrets.env").write_text(f"AWS_KEY={_AWS_KEY}\n")
        (self.repo_root / "run.sh").write_text(f"token={_GH_PAT}\n")
        (self.repo_root / "noext").write_text(f"contact {_addr('bob')}\n")
        self._commit()
        failures = _run_scan(self.repo_root, self.module)
        joined = "\n".join(failures)
        self.assertIn("secrets.env", joined)
        self.assertIn("run.sh", joined)
        self.assertIn("noext", joined)

    def test_finding2_pdf_author_and_email_are_caught(self) -> None:
        pdf_bytes = (
            b"%PDF-1.4\n1 0 obj\n<< /Author (Alice Person) /Title (Doc) >>\nendobj\n"
            b"trailer\n<< /Info 1 0 R >>\n" + _addr("carol").encode() + b"\n%%EOF"
        )
        (self.repo_root / "artifacts" / "doc.pdf").write_bytes(pdf_bytes)
        self._commit()
        failures = _run_scan(self.repo_root, self.module)
        joined = "\n".join(failures)
        self.assertIn("Alice Person", joined)
        self.assertIn(_addr("carol"), joined)

    def test_finding4_docx_body_secret_and_email_are_caught(self) -> None:
        _make_docx(
            self.repo_root / "artifacts" / "body_secret.docx",
            document_xml=(
                '<?xml version="1.0"?><w:document xmlns:w="ns"><w:body>'
                f"<w:p><w:r><w:t>contact {_addr('dave')} or "
                f"{_AWS_KEY}</w:t></w:r></w:p></w:body></w:document>"
            ),
        )
        self._commit()
        failures = _run_scan(self.repo_root, self.module)
        joined = "\n".join(failures)
        self.assertIn(_addr("dave"), joined)
        self.assertIn("AWS access key", joined)

    def test_finding5_attributed_core_property_elements_are_caught(self) -> None:
        _make_docx(
            self.repo_root / "artifacts" / "attr_metadata.docx",
            creator="Alice Person",
            core_attrs=' xml:space="preserve"',
        )
        self._commit()
        failures = _run_scan(self.repo_root, self.module)
        self.assertTrue(any("Alice Person" in f for f in failures))

    def test_finding6_tracked_changes_in_header_are_caught(self) -> None:
        _make_docx(
            self.repo_root / "artifacts" / "header_trackedchanges.docx",
            extra_parts={
                "word/header1.xml": (
                    '<?xml version="1.0"?><w:hdr xmlns:w="ns">'
                    '<w:ins w:author="Alice Person"><w:r><w:t>added</w:t></w:r></w:ins>'
                    "</w:hdr>"
                ),
            },
        )
        self._commit()
        failures = _run_scan(self.repo_root, self.module)
        self.assertTrue(any("header1.xml" in f and "tracked-changes" in f for f in failures))

    def test_finding7_docx_instrtext_field_is_not_a_tracked_change(self) -> None:
        # A plain PAGE field uses <w:instrText>, which contains "w:ins" as a
        # substring — must not be mistaken for a real <w:ins> tracked change.
        _make_docx(
            self.repo_root / "artifacts" / "field_code.docx",
            document_xml=(
                '<?xml version="1.0"?><w:document xmlns:w="ns"><w:body>'
                "<w:p><w:r><w:instrText> PAGE </w:instrText></w:r></w:p>"
                "</w:body></w:document>"
            ),
        )
        self._commit()
        failures = _run_scan(self.repo_root, self.module)
        self.assertFalse(any("tracked-changes" in f for f in failures), failures)

    def test_finding8_docx_email_split_across_adjacent_runs_is_caught(self) -> None:
        _make_docx(
            self.repo_root / "artifacts" / "split_run.docx",
            document_xml=(
                '<?xml version="1.0"?><w:document xmlns:w="ns"><w:body><w:p>'
                f"<w:r><w:t>alice@{_COMPANY[:5]}</w:t></w:r><w:r><w:t>{_COMPANY[5:]}</w:t></w:r>"
                "</w:p></w:body></w:document>"
            ),
        )
        self._commit()
        failures = _run_scan(self.repo_root, self.module)
        self.assertTrue(any(_addr("alice") in f for f in failures), failures)

    def test_finding9_pdf_hex_encoded_author_is_caught(self) -> None:
        name = "Alice Person"
        hexstr = ("FEFF" + name.encode("utf-16-be").hex()).upper().encode("ascii")
        pdf_bytes = (
            b"%PDF-1.4\n1 0 obj\n<< /Author <" + hexstr + b"> /Title (Doc) >>\nendobj\n"
            b"trailer\n<< /Info 1 0 R >>\n%%EOF"
        )
        (self.repo_root / "artifacts" / "hex_author.pdf").write_bytes(pdf_bytes)
        self._commit()
        failures = _run_scan(self.repo_root, self.module)
        self.assertTrue(any("Alice Person" in f for f in failures), failures)

    def test_finding10_push_range_override_catches_direct_main_push(self) -> None:
        # Simulates actions/checkout on a `push` to main: origin/main and
        # HEAD point at the identical commit (the push already landed
        # before CI ran), so merge-base-based diffing sees an empty range
        # and would miss the pushed commit's own identity without the
        # PUBLIC_SAFETY_COMMIT_RANGE_BASE override CI supplies.
        subprocess.run(["git", "checkout", "-qb", "main"], cwd=self.repo_root, check=True)
        (self.repo_root / "base.txt").write_text("base\n")
        self._commit()
        before_sha = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=self.repo_root, capture_output=True, text=True, check=True
        ).stdout.strip()

        (self.repo_root / "feature.txt").write_text("feature\n")
        subprocess.run(["git", "add", "-A"], cwd=self.repo_root, check=True)
        subprocess.run(
            [
                "git", "-c", f"user.email={_NON_NOREPLY}", "-c", "user.name=Real Human",
                "commit", "-q", "-m", "direct push to main",
            ],
            cwd=self.repo_root, check=True,
        )
        pushed_sha = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=self.repo_root, capture_output=True, text=True, check=True
        ).stdout.strip()

        subprocess.run(["git", "remote", "add", "origin", str(self.repo_root)], cwd=self.repo_root, check=True)
        subprocess.run(["git", "fetch", "-q", "origin", "main"], cwd=self.repo_root, check=True)
        # origin/main == HEAD, matching what a real push-triggered checkout sees.
        subprocess.run(["git", "update-ref", "refs/remotes/origin/main", pushed_sha], cwd=self.repo_root, check=True)

        self.module.ROOT = self.repo_root

        without_override: list[str] = []
        with mock.patch.dict("os.environ", {}, clear=False):
            import os as _os
            _os.environ.pop("PUBLIC_SAFETY_COMMIT_RANGE_BASE", None)
            self.module.check_commit_identities(without_override)
        self.assertEqual(without_override, [], "expected the pre-fix gap: empty range without override")

        with_override: list[str] = []
        with mock.patch.dict("os.environ", {"PUBLIC_SAFETY_COMMIT_RANGE_BASE": before_sha}):
            self.module.check_commit_identities(with_override)
        self.assertTrue(
            any(_NON_NOREPLY in f for f in with_override), with_override
        )

    def test_finding11_unquoted_env_secret_is_caught(self) -> None:
        (self.repo_root / "unquoted.env").write_text(
            f"OPENAI_API_KEY={_OPENAI_KEY}\n"
            f"secret={_GENERIC_VALUE}\n"
        )
        self._commit()
        failures = _run_scan(self.repo_root, self.module)
        self.assertTrue(any("Generic API key assignment" in f for f in failures), failures)

    def test_finding12_docx_relationship_target_is_scanned(self) -> None:
        _make_docx(
            self.repo_root / "artifacts" / "hyperlink.docx",
            extra_parts={
                "word/_rels/document.xml.rels": (
                    '<?xml version="1.0"?><Relationships '
                    'xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                    '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/'
                    'officeDocument/2006/relationships/hyperlink" '
                    f'Target="mailto:{_addr("alice")}" TargetMode="External"/>'
                    "</Relationships>"
                ),
            },
        )
        self._commit()
        failures = _run_scan(self.repo_root, self.module)
        self.assertTrue(any(_addr("alice") in f for f in failures), failures)

    def test_finding13_pdf_xmp_creator_is_caught(self) -> None:
        pdf_bytes = (
            b"%PDF-1.4\n1 0 obj\n<< /Type /Metadata /Subtype /XML >>\nstream\n"
            b'<x:xmpmeta xmlns:x="adobe:ns:meta/"><rdf:RDF '
            b'xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">'
            b'<rdf:Description xmlns:dc="http://purl.org/dc/elements/1.1/">'
            b"<dc:creator><rdf:Seq><rdf:li>Alice Person</rdf:li></rdf:Seq></dc:creator>"
            b"</rdf:Description></rdf:RDF></x:xmpmeta>\nendstream\nendobj\n%%EOF"
        )
        (self.repo_root / "artifacts" / "xmp_author.pdf").write_bytes(pdf_bytes)
        self._commit()
        failures = _run_scan(self.repo_root, self.module)
        self.assertTrue(any("Alice Person" in f for f in failures), failures)

    def test_finding14_non_ascii_tracked_filename_is_scanned(self) -> None:
        # Plain `git ls-files` C-escapes this name under core.quotePath, which
        # would build a nonexistent Path and silently skip the file entirely.
        (self.repo_root / "résumé.env").write_text(
            f"AWS_KEY={_AWS_KEY}\n", encoding="utf-8"
        )
        self._commit()
        self.module.ROOT = self.repo_root
        tracked = [p.name for p in self.module.tracked_files()]
        self.assertIn("résumé.env", tracked)
        failures = _run_scan(self.repo_root, self.module)
        self.assertTrue(any("AWS access key" in f for f in failures), failures)

    def test_finding15_legacy_github_noreply_identity_is_accepted(self) -> None:
        pattern = self.module.ALLOWED_EMAIL_PATTERN
        self.assertTrue(pattern.match("username@users.noreply.github.com"))
        self.assertTrue(pattern.match("12345+username@users.noreply.github.com"))
        self.assertTrue(pattern.match("noreply@github.com"))
        self.assertFalse(pattern.match(_NON_NOREPLY))

    def test_finding16_bot_noreply_identity_is_accepted(self) -> None:
        pattern = self.module.ALLOWED_EMAIL_PATTERN
        self.assertTrue(pattern.match("49699333+dependabot[bot]@users.noreply.github.com"))
        self.assertTrue(pattern.match("41898282+github-actions[bot]@users.noreply.github.com"))

    def test_finding17_text_is_not_joined_across_structural_boundaries(self) -> None:
        # Two separate paragraphs are not displayed as one continuous string,
        # so joining them would invent an address the document never shows.
        _make_docx(
            self.repo_root / "artifacts" / "two_paragraphs.docx",
            document_xml=(
                '<?xml version="1.0"?><w:document xmlns:w="ns"><w:body>'
                f"<w:p><w:r><w:t>alice@{_COMPANY[:5]}</w:t></w:r></w:p>"
                f"<w:p><w:r><w:t>{_COMPANY[5:]}</w:t></w:r></w:p>"
                "</w:body></w:document>"
            ),
        )
        self._commit()
        failures = _run_scan(self.repo_root, self.module)
        self.assertEqual(failures, [], "must not join text across paragraph boundaries")

    def test_finding18_scanner_own_test_file_is_not_exempt(self) -> None:
        # The scanner must not categorically skip any path: a real credential
        # committed into its own test file has to be caught like anywhere else.
        self.assertFalse(hasattr(self.module, "SELF_TEST_FIXTURE_PATH"))
        tests_dir = self.repo_root / "tests"
        tests_dir.mkdir()
        (tests_dir / "test_public_safety_scan.py").write_text(
            f"leaked = '{_AWS_KEY}'\n"
        )
        self._commit()
        failures = _run_scan(self.repo_root, self.module)
        self.assertTrue(any("AWS access key" in f for f in failures), failures)

    def test_commit_identities_accept_github_noreply_committer(self) -> None:
        # Empirically confirmed against PR #17's real refs/pull/17/merge:
        # GitHub's synthetic merge commit uses committer "GitHub
        # <noreply@github.com>", which must not be flagged.
        subprocess.run(["git", "checkout", "-qb", "main"], cwd=self.repo_root, check=True)
        (self.repo_root / "base.txt").write_text("base\n")
        self._commit()
        subprocess.run(["git", "checkout", "-qb", "feature"], cwd=self.repo_root, check=True)
        (self.repo_root / "feature.txt").write_text("feature\n")
        subprocess.run(["git", "add", "-A"], cwd=self.repo_root, check=True)
        subprocess.run(
            [
                "git", "-c", "user.email=noreply@github.com", "-c", "user.name=GitHub",
                "commit", "-q", "-m", "feature commit",
            ],
            cwd=self.repo_root, check=True,
        )
        subprocess.run(["git", "remote", "add", "origin", str(self.repo_root)], cwd=self.repo_root, check=True)
        subprocess.run(["git", "fetch", "-q", "origin", "main"], cwd=self.repo_root, check=True)
        subprocess.run(["git", "update-ref", "refs/remotes/origin/main", "main"], cwd=self.repo_root, check=True)

        self.module.ROOT = self.repo_root
        failures: list[str] = []
        self.module.check_commit_identities(failures)
        self.assertEqual(failures, [])

    def test_commit_identities_reject_non_noreply_committer(self) -> None:
        subprocess.run(["git", "checkout", "-qb", "main"], cwd=self.repo_root, check=True)
        (self.repo_root / "base.txt").write_text("base\n")
        self._commit()
        subprocess.run(["git", "checkout", "-qb", "feature"], cwd=self.repo_root, check=True)
        (self.repo_root / "feature.txt").write_text("feature\n")
        subprocess.run(["git", "add", "-A"], cwd=self.repo_root, check=True)
        subprocess.run(
            [
                "git", "-c", f"user.email={_NON_NOREPLY}", "-c", "user.name=Real Human",
                "commit", "-q", "-m", "feature commit",
            ],
            cwd=self.repo_root, check=True,
        )
        subprocess.run(["git", "remote", "add", "origin", str(self.repo_root)], cwd=self.repo_root, check=True)
        subprocess.run(["git", "fetch", "-q", "origin", "main"], cwd=self.repo_root, check=True)
        subprocess.run(["git", "update-ref", "refs/remotes/origin/main", "main"], cwd=self.repo_root, check=True)

        self.module.ROOT = self.repo_root
        failures: list[str] = []
        self.module.check_commit_identities(failures)
        self.assertTrue(any(_NON_NOREPLY in f for f in failures))


if __name__ == "__main__":
    sys.exit(unittest.main())
