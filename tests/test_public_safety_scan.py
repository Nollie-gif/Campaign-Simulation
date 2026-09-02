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
        relative = path.relative_to(repo_root).as_posix()
        if relative == module.SELF_TEST_FIXTURE_PATH:
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
        (self.repo_root / "secrets.env").write_text("AWS_KEY=AKIAABCDEFGHIJKLMNOP\n")
        (self.repo_root / "run.sh").write_text("token=github_pat_1234567890ABCDEFGHIJ\n")
        (self.repo_root / "noext").write_text("contact bob@real-company.com\n")
        self._commit()
        failures = _run_scan(self.repo_root, self.module)
        joined = "\n".join(failures)
        self.assertIn("secrets.env", joined)
        self.assertIn("run.sh", joined)
        self.assertIn("noext", joined)

    def test_finding2_pdf_author_and_email_are_caught(self) -> None:
        pdf_bytes = (
            b"%PDF-1.4\n1 0 obj\n<< /Author (Alice Person) /Title (Doc) >>\nendobj\n"
            b"trailer\n<< /Info 1 0 R >>\ncarol@real-company.com\n%%EOF"
        )
        (self.repo_root / "artifacts" / "doc.pdf").write_bytes(pdf_bytes)
        self._commit()
        failures = _run_scan(self.repo_root, self.module)
        joined = "\n".join(failures)
        self.assertIn("Alice Person", joined)
        self.assertIn("carol@real-company.com", joined)

    def test_finding4_docx_body_secret_and_email_are_caught(self) -> None:
        _make_docx(
            self.repo_root / "artifacts" / "body_secret.docx",
            document_xml=(
                '<?xml version="1.0"?><w:document xmlns:w="ns"><w:body>'
                "<w:p><w:r><w:t>contact dave@real-company.com or "
                "AKIAABCDEFGHIJKLMNOP</w:t></w:r></w:p></w:body></w:document>"
            ),
        )
        self._commit()
        failures = _run_scan(self.repo_root, self.module)
        joined = "\n".join(failures)
        self.assertIn("dave@real-company.com", joined)
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
                "<w:r><w:t>alice@real-</w:t></w:r><w:r><w:t>company.com</w:t></w:r>"
                "</w:p></w:body></w:document>"
            ),
        )
        self._commit()
        failures = _run_scan(self.repo_root, self.module)
        self.assertTrue(any("alice@real-company.com" in f for f in failures), failures)

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
                "git", "-c", "user.email=real.human@example-not-noreply.com", "-c", "user.name=Real Human",
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
            any("real.human@example-not-noreply.com" in f for f in with_override), with_override
        )

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
                "git", "-c", "user.email=real.human@example-not-noreply.com", "-c", "user.name=Real Human",
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
        self.assertTrue(any("real.human@example-not-noreply.com" in f for f in failures))


if __name__ == "__main__":
    sys.exit(unittest.main())
