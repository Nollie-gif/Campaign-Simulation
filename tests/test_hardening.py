import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

from campaign_simulation.admission import MainCampaignAdmissionError, admit_main_campaign
from campaign_simulation.bootstrap import REPOSITORY_MODE, SUPABASE_MODE, probe_supabase, resolve_storage_mode
from campaign_simulation.branches import PREQUEL_MODE, SEQUEL_MODE, resolve_simulation_branch
from campaign_simulation.cli import main as cli_main
from campaign_simulation.convergence import (
    CONTINUE_ALTERNATE_TIMELINE,
    ENTER_MAIN_UNCHANGED,
    PROPOSE_CANON_CHANGES,
    begin_prequel_main_convergence,
    resolve_prequel_main_convergence,
)
from campaign_simulation.lifecycles import allocate_persistent_identifier
from campaign_simulation.runtime import complete_sequel_onboarding
from campaign_simulation.saves import commit_checkpoint, commit_manifest, load_checkpoint, validate_prepared_manifest


def _write_minimum_campaign(root: Path, reference: str = "characters/player.json") -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / "main-campaign-manifest.json").write_text(
        json.dumps(
            {
                "campaign_history": "A short history.",
                "starting_situation": "A current situation.",
                "character_profile_references": [reference],
            }
        ),
        encoding="utf-8",
    )
    profile = root / "characters" / "player.json"
    profile.parent.mkdir(parents=True, exist_ok=True)
    profile.write_text(
        json.dumps({"character_name": "A character", "character_summary": "A playable participant."}),
        encoding="utf-8",
    )


def _validated_manifest() -> dict[str, object]:
    return {
        "id": "save-000001",
        "kind": "final",
        "status": "validated",
        "created_at": "2026-08-10T12:00:00Z",
        "record_revisions": [{"record_id": "record-000001", "revision": "rev-000001"}],
    }


class AdmissionBoundaryTests(unittest.TestCase):
    def test_reference_cannot_escape_main_campaign_root(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            campaign = root / "main-campaign"
            _write_minimum_campaign(campaign, "../outside.json")
            (root / "outside.json").write_text(
                json.dumps({"character_name": "Outside", "character_summary": "Must stay outside."}),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(MainCampaignAdmissionError, "escapes the main campaign"):
                admit_main_campaign(campaign)

    def test_absolute_reference_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            campaign = Path(temporary_directory) / "main-campaign"
            _write_minimum_campaign(campaign, str((campaign / "characters" / "player.json").resolve()))
            with self.assertRaisesRegex(MainCampaignAdmissionError, "must be relative"):
                admit_main_campaign(campaign)

    def test_runtime_path_inside_main_campaign_is_refused_without_writing(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            campaign = root / "main-campaign"
            _write_minimum_campaign(campaign)
            config = campaign / "runtime" / "storage-configuration.json"
            with self.assertRaisesRegex(ValueError, "overlaps the read-only main campaign"):
                complete_sequel_onboarding(campaign, config, ["continue_without_adding_material"])
            self.assertFalse(config.exists())

    def test_runtime_path_above_main_campaign_is_refused_without_writing(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            campaign = root / "main-campaign"
            _write_minimum_campaign(campaign)
            config = root / "storage-configuration.json"
            with self.assertRaisesRegex(ValueError, "ancestor of the read-only main campaign"):
                complete_sequel_onboarding(campaign, config, ["continue_without_adding_material"])
            self.assertFalse(config.exists())


class BranchTests(unittest.TestCase):
    def test_prequel_requires_historical_anchor_and_still_moves_forward(self) -> None:
        manifest = {"starting_situation": "Current situation."}
        with self.assertRaisesRegex(ValueError, "historical anchor"):
            resolve_simulation_branch(manifest, PREQUEL_MODE)
        branch = resolve_simulation_branch(manifest, PREQUEL_MODE, "A point in the past.")
        self.assertEqual(branch["relative_position"], "before_main_campaign")
        self.assertEqual(branch["time_direction"], "forward")
        self.assertEqual(branch["boundary_behavior"], "freeze_at_main_convergence_gate")

    def test_sequel_defaults_to_main_campaign_current_situation(self) -> None:
        branch = resolve_simulation_branch({"starting_situation": "Current situation."}, SEQUEL_MODE)
        self.assertEqual(branch["anchor"], "Current situation.")
        self.assertEqual(branch["relative_position"], "after_main_campaign")
        self.assertEqual(branch["time_direction"], "forward")


class IdentifierPersistenceTests(unittest.TestCase):
    def test_hook_and_scenario_ids_persist_in_session_state(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            state_path = Path(temporary_directory) / "runtime" / "session-state.json"
            self.assertEqual(allocate_persistent_identifier(state_path, "hook"), "hook-000001")
            self.assertEqual(allocate_persistent_identifier(state_path, "hook"), "hook-000002")
            self.assertEqual(allocate_persistent_identifier(state_path, "scenario"), "scenario-000001")
            self.assertEqual(
                json.loads(state_path.read_text(encoding="utf-8"))["identifier_counters"],
                {"hook": 3, "scenario": 2},
            )


class CheckpointTests(unittest.TestCase):
    def test_full_checkpoint_commits_manifest_and_all_records_together(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            destination = Path(temporary_directory) / "runtime" / "checkpoints" / "save.json"
            checkpoint = commit_checkpoint(
                destination,
                _validated_manifest(),
                {"record-000001": {"revision": "rev-000001", "data": {"state": "current"}}},
            )
            self.assertEqual(checkpoint["manifest"]["status"], "committed")
            loaded = load_checkpoint(destination)
            self.assertEqual(loaded["records"]["record-000001"]["data"]["state"], "current")

    def test_prepared_manifest_cannot_commit_without_validation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            manifest = _validated_manifest()
            manifest["status"] = "prepared"
            with self.assertRaisesRegex(ValueError, "only a validated"):
                commit_checkpoint(
                    Path(temporary_directory) / "save.json",
                    manifest,
                    {"record-000001": {"revision": "rev-000001", "data": {}}},
                )
            validated = validate_prepared_manifest(manifest)
            self.assertEqual(validated["status"], "validated")

    def test_manifest_only_save_path_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            with self.assertRaisesRegex(ValueError, "manifest-only"):
                commit_manifest(Path(temporary_directory) / "save.json", _validated_manifest())

    def test_blank_id_and_invalid_timestamp_are_refused(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            manifest = _validated_manifest()
            manifest["id"] = ""
            with self.assertRaisesRegex(ValueError, "id"):
                commit_checkpoint(
                    Path(temporary_directory) / "save.json",
                    manifest,
                    {"record-000001": {"revision": "rev-000001", "data": {}}},
                )
            manifest = _validated_manifest()
            manifest["created_at"] = "not-a-timestamp"
            with self.assertRaisesRegex(ValueError, "ISO-8601"):
                commit_checkpoint(
                    Path(temporary_directory) / "save.json",
                    manifest,
                    {"record-000001": {"revision": "rev-000001", "data": {}}},
                )

    def test_mismatched_record_revision_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            with self.assertRaisesRegex(ValueError, "do not match"):
                commit_checkpoint(
                    Path(temporary_directory) / "save.json",
                    _validated_manifest(),
                    {"record-000001": {"revision": "wrong", "data": {}}},
                )


class StorageHardeningTests(unittest.TestCase):
    def test_supabase_uses_environment_variable_without_persisting_secret(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            config_path = Path(temporary_directory) / "runtime" / "storage.json"
            answers = iter(["supabase", "https://project.supabase.co", "TEST_SUPABASE_KEY"])
            with patch.dict(os.environ, {"TEST_SUPABASE_KEY": "secret-value"}, clear=False):
                result = resolve_storage_mode(
                    config_path,
                    lambda _: next(answers),
                    lambda url, key: url == "https://project.supabase.co" and key == "secret-value",
                )
            self.assertEqual(result["storage_mode"], SUPABASE_MODE)
            persisted = config_path.read_text(encoding="utf-8")
            self.assertNotIn("secret-value", persisted)
            self.assertIn("TEST_SUPABASE_KEY", persisted)

    def test_missing_supabase_credential_falls_back_without_prompting_again(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            config_path = Path(temporary_directory) / "runtime" / "storage.json"
            config_path.parent.mkdir(parents=True)
            config_path.write_text(
                json.dumps(
                    {
                        "storage_mode": "supabase",
                        "supabase_url": "https://project.supabase.co",
                        "supabase_key_env_var": "MISSING_KEY",
                        "supabase_schema": "",
                        "fallback_reason": "",
                    }
                ),
                encoding="utf-8",
            )
            result = resolve_storage_mode(
                config_path,
                lambda _: self.fail("a stored configuration must not prompt again"),
                lambda *_: self.fail("a missing credential must not call the probe"),
                environment={},
            )
            self.assertEqual(result["storage_mode"], REPOSITORY_MODE)
            self.assertIn("credential", result["fallback_reason"])

    def test_real_probe_builds_authenticated_settings_request(self) -> None:
        class Response:
            status = 200

            def __enter__(self):
                return self

            def __exit__(self, *_):
                return False

        with patch("campaign_simulation.bootstrap.urlopen", return_value=Response()) as mocked_open:
            self.assertTrue(probe_supabase("https://project.supabase.co", "test-key"))
        request = mocked_open.call_args.args[0]
        self.assertEqual(request.full_url, "https://project.supabase.co/auth/v1/settings")
        self.assertEqual(request.headers["Apikey"], "test-key")


class CliTests(unittest.TestCase):
    def test_non_interactive_requires_explicit_mode(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            campaign = root / "main-campaign"
            _write_minimum_campaign(campaign)
            stderr = io.StringIO()
            with redirect_stderr(stderr):
                result = cli_main(
                    [
                        "start",
                        "--main-campaign",
                        str(campaign),
                        "--runtime",
                        str(root / "runtime"),
                        "--non-interactive",
                    ]
                )
            self.assertEqual(result, 2)
            self.assertIn("requires --mode", stderr.getvalue())

    def test_non_interactive_sequel_creates_branch_and_repository_runtime(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            campaign = root / "main-campaign"
            _write_minimum_campaign(campaign)
            stdout = io.StringIO()
            stderr = io.StringIO()
            with redirect_stdout(stdout), redirect_stderr(stderr):
                result = cli_main(
                    [
                        "start",
                        "--main-campaign",
                        str(campaign),
                        "--runtime",
                        str(root / "runtime"),
                        "--mode",
                        "sequel",
                        "--non-interactive",
                    ]
                )
            self.assertEqual(result, 0, stderr.getvalue())
            self.assertIn('"simulation_mode": "sequel"', stdout.getvalue())
            self.assertTrue((root / "runtime" / "storage-configuration.json").is_file())
            branch = json.loads((root / "runtime" / "simulation-branch.json").read_text(encoding="utf-8"))
            self.assertEqual(branch["anchor"], "A current situation.")

    def test_non_interactive_prequel_requires_anchor(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            campaign = root / "main-campaign"
            _write_minimum_campaign(campaign)
            stderr = io.StringIO()
            with redirect_stderr(stderr):
                result = cli_main(
                    [
                        "start",
                        "--main-campaign",
                        str(campaign),
                        "--runtime",
                        str(root / "runtime"),
                        "--mode",
                        "prequel",
                        "--non-interactive",
                    ]
                )
            self.assertEqual(result, 2)
            self.assertIn("requires --anchor", stderr.getvalue())

    def test_interactive_start_shows_branch_and_optional_capabilities(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            campaign = root / "main-campaign"
            _write_minimum_campaign(campaign)
            responses = iter(["sequel", "", "", "repository"])
            stdout = io.StringIO()
            with patch("builtins.input", side_effect=lambda _: next(responses)), redirect_stdout(stdout):
                result = cli_main(
                    [
                        "start",
                        "--main-campaign",
                        str(campaign),
                        "--runtime",
                        str(root / "runtime"),
                    ]
                )
            self.assertEqual(result, 0)
            self.assertIn("Explore the past", stdout.getvalue())
            self.assertIn("Explore the future", stdout.getvalue())
            self.assertIn("supporting_character", stdout.getvalue())
            self.assertIn("Continue without adding material", stdout.getvalue())


class PrequelConvergenceTests(unittest.TestCase):
    def test_convergence_freezes_prequel_and_never_authorizes_main_writes(self) -> None:
        manifest = _validated_manifest()
        manifest["status"] = "committed"
        checkpoint = {
            "manifest": manifest,
            "records": {"record-000001": {"revision": "rev-000001", "data": {}}},
        }
        gate = begin_prequel_main_convergence(checkpoint, "main-scene-000001")
        self.assertEqual(gate["prequel_status"], "frozen_at_main_boundary")
        self.assertEqual(gate["main_campaign_write_authorization"], "never_automatic")
        self.assertEqual(
            gate["allowed_choices"],
            [ENTER_MAIN_UNCHANGED, PROPOSE_CANON_CHANGES, CONTINUE_ALTERNATE_TIMELINE],
        )

    def test_each_explicit_convergence_choice_preserves_main_write_boundary(self) -> None:
        manifest = _validated_manifest()
        manifest["status"] = "committed"
        checkpoint = {
            "manifest": manifest,
            "records": {"record-000001": {"revision": "rev-000001", "data": {}}},
        }
        gate = begin_prequel_main_convergence(checkpoint, "main-scene-000001")
        unchanged = resolve_prequel_main_convergence(gate, ENTER_MAIN_UNCHANGED)
        proposal = resolve_prequel_main_convergence(
            gate, PROPOSE_CANON_CHANGES, [{"record_id": "candidate-000001"}]
        )
        alternate = resolve_prequel_main_convergence(gate, CONTINUE_ALTERNATE_TIMELINE)
        self.assertEqual(unchanged["status"], "main_entered_unchanged")
        self.assertEqual(proposal["status"], "canon_change_review_required")
        self.assertEqual(alternate["status"], "alternate_timeline_continues")
        for result in (unchanged, proposal, alternate):
            self.assertEqual(result["main_campaign_write_authorization"], "never_automatic")


if __name__ == "__main__":
    unittest.main()
