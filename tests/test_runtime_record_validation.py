import tempfile
import unittest
from pathlib import Path

from campaign_simulation.autosave import AUTOSAVE_RECORD_ID, initial_autosave_state
from campaign_simulation.clock import CLOCK_RECORD_ID, initial_clock_state
from campaign_simulation.saves import commit_checkpoint, load_checkpoint
from campaign_simulation.scheduler import SCHEDULER_RECORD_ID, initial_scheduler_state


def _manifest(record_ids: list[str]) -> dict[str, object]:
    return {
        "id": "save-runtime-000001",
        "kind": "quick",
        "status": "validated",
        "created_at": "2026-08-11T00:00:00Z",
        "record_revisions": [
            {"record_id": record_id, "revision": "rev-1"}
            for record_id in record_ids
        ],
    }


class RuntimeRecordValidationTests(unittest.TestCase):
    def test_clock_autosave_and_scheduler_commit_as_one_checkpoint(self) -> None:
        clock = initial_clock_state(day=3, phase="morning")
        autosave = initial_autosave_state(clock)
        scheduler = initial_scheduler_state()
        records = {
            CLOCK_RECORD_ID: {"revision": "rev-1", "data": clock},
            AUTOSAVE_RECORD_ID: {"revision": "rev-1", "data": autosave},
            SCHEDULER_RECORD_ID: {"revision": "rev-1", "data": scheduler},
        }

        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "save.json"
            commit_checkpoint(path, _manifest(list(records)), records)
            loaded = load_checkpoint(path)
            self.assertEqual(loaded["records"][CLOCK_RECORD_ID]["data"], clock)
            self.assertEqual(loaded["records"][AUTOSAVE_RECORD_ID]["data"], autosave)
            self.assertEqual(loaded["records"][SCHEDULER_RECORD_ID]["data"], scheduler)

    def test_invalid_clock_record_is_rejected_before_commit(self) -> None:
        records = {
            CLOCK_RECORD_ID: {
                "revision": "rev-1",
                "data": {
                    "schema_version": 1,
                    "day": 0,
                    "phase": "morning",
                    "elapsed_campaign_minutes": 0,
                    "long_rests_completed": 0,
                },
            }
        }
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(ValueError):
                commit_checkpoint(Path(td) / "save.json", _manifest([CLOCK_RECORD_ID]), records)

    def test_invalid_autosave_record_is_rejected_before_commit(self) -> None:
        clock = initial_clock_state()
        autosave = initial_autosave_state(clock)
        autosave["automatic_saves_today"] = -1
        records = {
            AUTOSAVE_RECORD_ID: {"revision": "rev-1", "data": autosave},
        }
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(ValueError):
                commit_checkpoint(
                    Path(td) / "save.json",
                    _manifest([AUTOSAVE_RECORD_ID]),
                    records,
                )


if __name__ == "__main__":
    unittest.main()
