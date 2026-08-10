import unittest

from campaign_simulation.branches import (
    MAIN_CAMPAIGN_ONLY_SOURCE_POLICY,
    MAIN_CAMPAIGN_SOURCE,
    PREQUEL_MODE,
    SEQUEL_MODE,
    resolve_simulation_branch,
)
from campaign_simulation.convergence import (
    PREQUEL_CHECKPOINT_ROLE,
    SEQUEL_SOURCE_POLICY,
    begin_prequel_main_convergence,
)


class PrequelSourceLockTests(unittest.TestCase):
    def test_prequel_checkpoint_cannot_directly_source_a_sequel(self) -> None:
        with self.assertRaisesRegex(ValueError, "only from the accepted Main Campaign"):
            resolve_simulation_branch(
                {"starting_situation": "Current campaign state."},
                SEQUEL_MODE,
                source_type="prequel_checkpoint",
            )

    def test_both_branch_modes_record_main_campaign_only_source_policy(self) -> None:
        prequel = resolve_simulation_branch(
            {"starting_situation": "Current campaign state."},
            PREQUEL_MODE,
            "Earlier historical state.",
        )
        sequel = resolve_simulation_branch(
            {"starting_situation": "Current campaign state."},
            SEQUEL_MODE,
        )
        for branch in (prequel, sequel):
            self.assertEqual(branch["source_type"], MAIN_CAMPAIGN_SOURCE)
            self.assertEqual(branch["source_policy"], MAIN_CAMPAIGN_ONLY_SOURCE_POLICY)

    def test_convergence_marks_prequel_checkpoint_as_review_input_only(self) -> None:
        checkpoint = {
            "manifest": {
                "id": "save-000001",
                "kind": "final",
                "status": "committed",
                "created_at": "2026-08-10T12:00:00Z",
                "record_revisions": [
                    {"record_id": "record-000001", "revision": "rev-000001"}
                ],
            },
            "records": {
                "record-000001": {"revision": "rev-000001", "data": {}}
            },
        }
        convergence = begin_prequel_main_convergence(checkpoint, "main-boundary")
        self.assertEqual(convergence["sequel_source_policy"], SEQUEL_SOURCE_POLICY)
        self.assertEqual(convergence["prequel_checkpoint_role"], PREQUEL_CHECKPOINT_ROLE)
        self.assertEqual(convergence["sequel_source_policy"], "main_campaign_only")
        self.assertEqual(convergence["prequel_checkpoint_role"], "review_input_only")


if __name__ == "__main__":
    unittest.main()
