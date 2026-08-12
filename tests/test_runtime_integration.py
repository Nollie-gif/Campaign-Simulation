import unittest

from campaign_simulation.mutation_gates import (
    MutationDomain,
    MutationGateError,
    MutationKind,
    MutationOperation,
    MutationPlan,
    Procedure,
    validate_mutation_plan,
)
from campaign_simulation.runtime_integration import (
    WDR001_RECORD_IDS,
    evaluate_runtime_boundary,
    initial_wdr001_records,
)
from campaign_simulation.scheduler import campaign_time_trigger, create_event


def assessment(*, level="meaningful", fingerprint=None):
    return {
        "scene_resolved": True,
        "change_level": level,
        "manual_save_requested": False,
        "state_fingerprint": fingerprint,
    }


class RuntimeIntegrationTests(unittest.TestCase):
    def test_three_meaningful_scenes_request_one_normal_autosave(self):
        records = initial_wdr001_records(day=19, phase="morning")
        for scene in range(1, 4):
            decision = evaluate_runtime_boundary(
                records,
                assessment(fingerprint=f"scene-{scene}"),
                published_generation=17,
                staging_generation=18,
                time_update={"elapsed_minutes": 10},
            )
            records = decision["next_records"]
            if scene < 3:
                self.assertIsNone(decision["checkpoint"])

        self.assertTrue(decision["autosave"]["trigger"])
        self.assertTrue(decision["autosave"]["automatic"])
        self.assertEqual("accumulated_meaningful_progress", decision["autosave"]["reason"])
        self.assertEqual(set(WDR001_RECORD_IDS), {op.target for op in decision["checkpoint"]["plan"].operations})
        self.assertEqual("autosave", decision["checkpoint"]["plan"].procedure.value)

    def test_non_trigger_never_returns_a_save_plan(self):
        records = initial_wdr001_records(day=19, phase="morning")
        decision = evaluate_runtime_boundary(
            records,
            assessment(level="minor", fingerprint="unchanged"),
            published_generation=17,
            staging_generation=18,
        )
        self.assertFalse(decision["autosave"]["trigger"])
        self.assertIsNone(decision["checkpoint"])

    def test_eligible_event_is_surfaced_without_auto_resolution_or_write(self):
        records = initial_wdr001_records(day=19, phase="morning")
        created = create_event(
            records["scheduler_state"],
            event_id="event-000001",
            dedupe_key="lab:nix-observation",
            trigger=campaign_time_trigger(day=19, phase="afternoon"),
            clock_state=records["campaign_clock"],
        )
        records["scheduler_state"] = created["state"]
        decision = evaluate_runtime_boundary(
            records,
            assessment(level="minor", fingerprint="same"),
            published_generation=17,
            staging_generation=18,
            time_update={"phase": "afternoon"},
        )
        self.assertEqual(["event-000001"], [event["id"] for event in decision["eligible_events"]])
        self.assertEqual("pending", decision["next_records"]["scheduler_state"]["events"][0]["status"])
        self.assertIsNone(decision["checkpoint"])

    def test_raw_sql_is_still_refused_for_autosave_records(self):
        plan = MutationPlan(
            procedure=Procedure.AUTOSAVE,
            operations=(
                MutationOperation(MutationDomain.CAMPAIGN_CLOCK, "campaign_clock", MutationKind.WRITE),
                MutationOperation(MutationDomain.AUTOSAVE, "autosave_state", MutationKind.WRITE),
                MutationOperation(MutationDomain.SCHEDULER, "scheduler_state", MutationKind.WRITE),
            ),
            facts=frozenset({"reconciled", "validated", "same_checkpoint"}),
            branch="runtime-save-staging",
            sql_mode="raw",
            persistence_mode="generation_pinned",
            published_generation=17,
            staging_generation=18,
        )
        with self.assertRaisesRegex(MutationGateError, "ungated_sql_mutation"):
            validate_mutation_plan(plan, record_ids=WDR001_RECORD_IDS)


if __name__ == "__main__":
    unittest.main()
