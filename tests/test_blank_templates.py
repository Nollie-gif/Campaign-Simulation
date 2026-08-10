from pathlib import Path
import json
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from campaign_simulation.bootstrap import REPOSITORY_MODE, resolve_storage_mode
from campaign_simulation.admission import MainCampaignAdmissionError, admit_main_campaign
from campaign_simulation.lifecycles import HOOK_TRANSITIONS, allocate_identifier, transition
from campaign_simulation.runtime import initialize_sequel_runtime
from campaign_simulation.saves import commit_manifest


ROOT = Path(__file__).resolve().parents[1]


class FoundationTests(unittest.TestCase):
    def test_blank_templates_validate(self) -> None:
        result = subprocess.run(
            [sys.executable, "tools/validate_blank_templates.py"],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_hook_terminal_state_cannot_reopen(self) -> None:
        with self.assertRaises(ValueError):
            transition("resolved", "active", HOOK_TRANSITIONS)

    def test_identifier_counter_never_reuses_current_value(self) -> None:
        identifier, next_value = allocate_identifier("hook", 1)
        self.assertEqual(identifier, "hook-000001")
        self.assertEqual(next_value, 2)

    def test_unavailable_external_store_falls_back(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            config_path = Path(temporary_directory) / "runtime" / "storage.json"
            answers = iter(["supabase", "https://external.invalid"])
            result = resolve_storage_mode(config_path, lambda _: next(answers), lambda _: False)
            self.assertEqual(result["storage_mode"], REPOSITORY_MODE)
            self.assertTrue(json.loads(config_path.read_text(encoding="utf-8"))["fallback_reason"])

    def test_final_save_commits_atomically(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            destination = Path(temporary_directory) / "save.json"
            commit_manifest(destination, {
                "id": "save-000001",
                "kind": "final",
                "status": "validated",
                "created_at": "2000-01-01T00:00:00Z",
                "record_revisions": [],
            })
            self.assertEqual(json.loads(destination.read_text(encoding="utf-8"))["status"], "committed")

    def test_sequel_start_is_blocked_before_storage_setup_when_main_campaign_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            config_path = root / "runtime" / "storage.json"
            input_called = False

            def forbidden_input(_: str) -> str:
                nonlocal input_called
                input_called = True
                return "repository"

            with self.assertRaises(MainCampaignAdmissionError):
                initialize_sequel_runtime(root / "main-campaign", config_path, forbidden_input)
            self.assertFalse(input_called)
            self.assertFalse(config_path.exists())

    def test_valid_main_campaign_is_admitted_before_storage_setup(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            source = root / "main-campaign"
            source.mkdir()
            coverage = {
                area: {"status": "complete", "evidence_record_ids": [f"record-{index:06d}"]}
                for index, area in enumerate(
                    ("campaign_context", "world_state", "participants", "timeline", "knowledge_boundaries", "open_threads"),
                    start=1,
                )
            }
            manifest = {
                "repository_role": "main-campaign",
                "campaign_id": "campaign-000001",
                "source_revision": "revision-000001",
                "readiness": {"status": "ready"},
                "information_coverage": coverage,
            }
            (source / "main-campaign-manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
            result = initialize_sequel_runtime(source, root / "runtime" / "storage.json", lambda _: "repository")
            self.assertEqual(result["main_campaign"]["campaign_id"], "campaign-000001")
            self.assertEqual(result["storage"]["storage_mode"], REPOSITORY_MODE)


if __name__ == "__main__":
    unittest.main()
