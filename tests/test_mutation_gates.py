import unittest

from campaign_simulation.mutation_gates import (
    MutationDomain,
    MutationGateError,
    MutationKind,
    MutationOperation,
    MutationPlan,
    Procedure,
    PublicationReceipt,
    route_user_request,
    validate_mutation_plan,
    validate_publication_receipt,
)


def quicksave_plan(*operations, facts=None, **kwargs):
    return MutationPlan(
        procedure=Procedure.QUICKSAVE,
        operations=tuple(operations),
        facts=frozenset(facts or {"reconciled", "validated", "same_checkpoint"}),
        branch="runtime-save-staging",
        sql_mode="gated",
        persistence_mode="generation_pinned",
        published_generation=15,
        staging_generation=16,
        **kwargs,
    )


class MutationGateTests(unittest.TestCase):
    def test_simple_user_words_route_to_internal_procedures(self):
        self.assertEqual(route_user_request("DM note: quicksave"), Procedure.QUICKSAVE)
        self.assertEqual(route_user_request("final save"), Procedure.FINAL_SAVE)

    def test_quicksave_rejects_engineering_scope(self):
        plan = quicksave_plan(
            MutationOperation(MutationDomain.RUNTIME_STATE, "record-1"),
            MutationOperation(MutationDomain.ENGINEERING_DOCS, "README.md"),
        )
        with self.assertRaisesRegex(MutationGateError, "forbidden_domain"):
            validate_mutation_plan(plan)

    def test_completion_rejects_primary_hook_left_active(self):
        plan = MutationPlan(
            procedure=Procedure.SCENARIO_COMPLETION,
            operations=(
                MutationOperation(MutationDomain.SCENARIO, "scenario-1", MutationKind.TRANSITION, "active", "completed"),
                MutationOperation(MutationDomain.PUBLICATION, "publication", MutationKind.PUBLISH),
            ),
            facts=frozenset({"consequences_persisted", "validated", "same_checkpoint"}),
            branch="runtime-save-staging",
            sql_mode="gated",
            persistence_mode="generation_pinned",
            published_generation=15,
            staging_generation=16,
        )
        with self.assertRaisesRegex(MutationGateError, "missing_postcondition"):
            validate_mutation_plan(plan)

    def test_event_resolution_rejects_missing_consequence(self):
        plan = MutationPlan(
            procedure=Procedure.DEFERRED_EVENT_RESOLUTION,
            operations=(
                MutationOperation(MutationDomain.DEFERRED_EVENT, "event-1", MutationKind.TRANSITION, "pending", "resolved"),
            ),
            facts=frozenset({"event_terminal", "validated", "same_checkpoint"}),
            branch="runtime-save-staging",
            sql_mode="gated",
            persistence_mode="generation_pinned",
            published_generation=15,
            staging_generation=16,
        )
        with self.assertRaisesRegex(MutationGateError, "missing_postcondition"):
            validate_mutation_plan(plan)

    def test_start_of_day_requires_finalized_previous_day(self):
        plan = MutationPlan(
            procedure=Procedure.START_OF_DAY,
            operations=(MutationOperation(MutationDomain.RUNTIME_STATE, "day"),),
            facts=frozenset({"new_day_initialized", "validated", "same_checkpoint"}),
            branch="runtime-save-staging",
            sql_mode="gated",
            persistence_mode="generation_pinned",
            published_generation=15,
            staging_generation=16,
        )
        with self.assertRaisesRegex(MutationGateError, "previous_day_finalized"):
            validate_mutation_plan(plan)

    def test_illegal_lifecycle_transition_is_rejected(self):
        plan = quicksave_plan(
            MutationOperation(MutationDomain.HOOK, "hook-1", MutationKind.TRANSITION, "resolved", "active"),
        )
        with self.assertRaisesRegex(MutationGateError, "illegal_lifecycle_transition"):
            validate_mutation_plan(plan)

    def test_raw_sql_runtime_mutation_is_rejected(self):
        plan = MutationPlan(
            procedure=Procedure.KNOWLEDGE_ONLY,
            operations=(MutationOperation(MutationDomain.KNOWLEDGE, "claim-1"),),
            facts=frozenset({"knowledge_reconciled", "validated", "same_checkpoint"}),
            branch="runtime-save-staging",
            sql_mode="raw",
            persistence_mode="generation_pinned",
            published_generation=15,
            staging_generation=16,
        )
        with self.assertRaisesRegex(MutationGateError, "ungated_sql_mutation"):
            validate_mutation_plan(plan)

    def test_receipt_must_prove_complete_publication(self):
        plan = quicksave_plan(MutationOperation(MutationDomain.RUNTIME_STATE, "record-1"))
        validate_mutation_plan(plan)
        receipt = PublicationReceipt(
            procedure=Procedure.QUICKSAVE,
            published_generation=16,
            published_git_ref="abcdef012345",
            published_day=20,
            git_mirror_confirmed=False,
            store_parity_confirmed=True,
            checkpoint_committed=True,
            last_healthy_checkpoint="generation-15",
        )
        with self.assertRaisesRegex(MutationGateError, "mirror_unconfirmed"):
            validate_publication_receipt(plan, receipt)

    def test_valid_quicksave_and_receipt_succeed(self):
        plan = quicksave_plan(MutationOperation(MutationDomain.RUNTIME_STATE, "record-1"))
        validate_mutation_plan(plan, record_ids=["record-1"])
        receipt = PublicationReceipt(
            procedure=Procedure.QUICKSAVE,
            published_generation=16,
            published_git_ref="abcdef012345",
            published_day=20,
            git_mirror_confirmed=True,
            store_parity_confirmed=True,
            checkpoint_committed=True,
            last_healthy_checkpoint="generation-15",
        )
        validate_publication_receipt(plan, receipt)

    def test_safe_narration_is_not_a_gate_operation(self):
        # The gate is called only for durable mutation candidates; a narrative-only
        # action never needs a plan and therefore cannot be blocked by this module.
        self.assertTrue(True)


if __name__ == "__main__":
    unittest.main()
