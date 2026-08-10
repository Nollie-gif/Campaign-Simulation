import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from campaign_simulation.lifecycles import allocate_persistent_identifier


class LifecyclesAtomicTests(unittest.TestCase):
    def test_allocate_persistent_identifier_cleans_temp_on_write_failure(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            state_path = root / "runtime" / "session-state.json"
            state_path.parent.mkdir(parents=True)
            initial = {"identifier_counters": {"hook": 1}}
            state_path.write_text(json.dumps(initial), encoding="utf-8")

            # Patch the json.dump used by the atomic writer to raise during the write.
            target = "campaign_simulation._atomic.json.dump"
            with patch(target, side_effect=OSError("simulated write failure")):
                with self.assertRaises(OSError):
                    allocate_persistent_identifier(state_path, "hook")

            # Previous state must remain unchanged.
            self.assertTrue(state_path.exists())
            self.assertEqual(json.loads(state_path.read_text(encoding="utf-8")), initial)

            # No temporary files matching the pattern should be left behind.
            temps = list(state_path.parent.glob(f".{state_path.name}.*"))
            self.assertEqual(len(temps), 0, f"temporary files left behind: {temps}")

            # Retry without patch should succeed and advance the counter.
            identifier = allocate_persistent_identifier(state_path, "hook")
            self.assertEqual(identifier, "hook-000001")
            persisted = json.loads(state_path.read_text(encoding="utf-8"))
            self.assertEqual(persisted.get("identifier_counters", {}).get("hook"), 2)

    def test_allocate_persistent_identifier_cleans_temp_on_replace_failure(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            state_path = root / "runtime" / "session-state.json"
            state_path.parent.mkdir(parents=True)
            initial = {"identifier_counters": {"hook": 1}}
            state_path.write_text(json.dumps(initial), encoding="utf-8")

            # Patch os.replace inside the atomic helper to raise.
            target = "campaign_simulation._atomic.os.replace"
            with patch(target, side_effect=OSError("simulated replace failure")):
                with self.assertRaises(OSError):
                    allocate_persistent_identifier(state_path, "hook")

            # Previous state must remain unchanged.
            self.assertTrue(state_path.exists())
            self.assertEqual(json.loads(state_path.read_text(encoding="utf-8")), initial)

            # No temp files should remain after handled replace failure.
            temps = list(state_path.parent.glob(f".{state_path.name}.*"))
            self.assertEqual(len(temps), 0, f"temporary files left behind: {temps}")

            # Retry without patch should succeed.
            identifier = allocate_persistent_identifier(state_path, "hook")
            self.assertEqual(identifier, "hook-000001")
            persisted = json.loads(state_path.read_text(encoding="utf-8"))
            self.assertEqual(persisted.get("identifier_counters", {}).get("hook"), 2)

    def test_parent_dir_fsync_best_effort_does_not_fail_when_unsupported(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            state_path = root / "runtime" / "session-state.json"
            state_path.parent.mkdir(parents=True)
            initial = {"identifier_counters": {"hook": 1}}
            state_path.write_text(json.dumps(initial), encoding="utf-8")

            # Simulate platform where parent-directory fsync helper raises.
            target = "campaign_simulation._atomic._fsync_parent_directory"
            with patch(target, side_effect=OSError("simulated fsync unsupported")):
                # This should NOT raise — parent-dir fsync is best-effort only.
                identifier = allocate_persistent_identifier(state_path, "hook")
                self.assertEqual(identifier, "hook-000001")

    def test_temp_files_removed_on_handled_failures_and_retry_safe(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            state_path = root / "runtime" / "session-state.json"
            state_path.parent.mkdir(parents=True)
            initial = {"identifier_counters": {"hook": 1}}
            state_path.write_text(json.dumps(initial), encoding="utf-8")

            target_dump = "campaign_simulation._atomic.json.dump"
            target_replace = "campaign_simulation._atomic.os.replace"

            # Simulate write failure
            with patch(target_dump, side_effect=OSError("simulated write failure")):
                with self.assertRaises(OSError):
                    allocate_persistent_identifier(state_path, "hook")
            temps = list(state_path.parent.glob(f".{state_path.name}.*"))
            self.assertEqual(len(temps), 0)

            # Simulate replace failure
            with patch(target_replace, side_effect=OSError("simulated replace failure")):
                with self.assertRaises(OSError):
                    allocate_persistent_identifier(state_path, "hook")
            temps = list(state_path.parent.glob(f".{state_path.name}.*"))
            self.assertEqual(len(temps), 0)

            # Final attempt succeeds
            identifier = allocate_persistent_identifier(state_path, "hook")
            self.assertEqual(identifier, "hook-000001")
            persisted = json.loads(state_path.read_text(encoding="utf-8"))
            self.assertEqual(persisted.get("identifier_counters", {}).get("hook"), 2)


if __name__ == "__main__":
    unittest.main()
