import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from campaign_simulation.clock import (
    apply_time_update,
    initial_clock_state,
    observe_presentation_time,
)
from campaign_simulation.lifecycles import allocate_persistent_identifier
from campaign_simulation.mutation_gates import (
    MutationDomain,
    MutationKind,
    MutationOperation,
    MutationPlan,
    Procedure,
)
from campaign_simulation.saves import commit_checkpoint as _commit_checkpoint, load_checkpoint
from campaign_simulation.scheduler import (
    SCHEDULER_RECORD_ID,
    after_elapsed_trigger,
    campaign_time_trigger,
    create_event,
    evaluate_scheduler,
    initial_scheduler_state,
    next_long_rest_trigger,
    state_condition_trigger,
    transition_event,
    transition_trigger,
)


def commit_checkpoint(path, manifest, records):
    plan = MutationPlan(
        procedure=Procedure.AUTOSAVE,
        operations=tuple(
            MutationOperation(
                MutationDomain.SCHEDULER if record_id == "scheduler_state" else MutationDomain.RUNTIME_STATE,
                record_id,
                MutationKind.WRITE,
            )
            for record_id in records
        ),
        facts=frozenset({"reconciled", "validated", "same_checkpoint"}),
        branch="runtime-save-staging",
        sql_mode="gated",
        persistence_mode="generation_pinned",
        published_generation=17,
        staging_generation=18,
    )
    return _commit_checkpoint(path, manifest, records, gate_plan=plan)


def _manifest(record_ids: list[str], revision: str = "rev-1") -> dict[str, object]:
    return {
        "id": "save-000001",
        "kind": "quick",
        "status": "validated",
        "created_at": "2026-08-11T00:00:00Z",
        "record_revisions": [
            {"record_id": record_id, "revision": revision}
            for record_id in record_ids
        ],
    }


def _records(scheduler_state: dict, world_state: dict) -> dict[str, dict]:
    return {
        SCHEDULER_RECORD_ID: {"revision": "rev-1", "data": scheduler_state},
        "world_state": {"revision": "rev-1", "data": world_state},
    }


class SchedulerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.clock = initial_clock_state(day=10, phase="morning", elapsed_campaign_minutes=100)
        self.scheduler = initial_scheduler_state()

    def _schedule(
        self,
        trigger: dict,
        *,
        event_id: str = "event-000001",
        dedupe_key: str = "event:test",
        guard: dict | None = None,
        references: dict[str, str] | None = None,
    ) -> dict:
        result = create_event(
            self.scheduler,
            event_id=event_id,
            dedupe_key=dedupe_key,
            trigger=trigger,
            clock_state=self.clock,
            guard=guard,
            references=references,
        )
        self.scheduler = result["state"]
        return result

    def test_event_identifier_namespace_is_permanent_and_non_recycled(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            state_path = Path(td) / "runtime" / "session-state.json"
            first = allocate_persistent_identifier(state_path, "event")
            second = allocate_persistent_identifier(state_path, "event")
            self.assertEqual(first, "event-000001")
            self.assertEqual(second, "event-000002")
            persisted = json.loads(state_path.read_text(encoding="utf-8"))
            self.assertEqual(persisted["identifier_counters"]["event"], 3)

    def test_relative_elapsed_trigger_fires_at_due_cursor(self) -> None:
        self._schedule(after_elapsed_trigger(self.clock, 60))
        before = apply_time_update(self.clock, elapsed_minutes=59)
        self.assertEqual(evaluate_scheduler(self.scheduler, before)["eligible_event_ids"], [])
        due = apply_time_update(self.clock, elapsed_minutes=60)
        self.assertEqual(
            evaluate_scheduler(self.scheduler, due)["eligible_event_ids"],
            ["event-000001"],
        )

    def test_campaign_day_phase_trigger_is_conservative(self) -> None:
        self._schedule(campaign_time_trigger(day=10, phase="afternoon"))
        midday = observe_presentation_time(self.clock, phase="midday")
        self.assertEqual(evaluate_scheduler(self.scheduler, midday)["eligible_event_ids"], [])
        afternoon = observe_presentation_time(midday, phase="afternoon")
        self.assertEqual(
            evaluate_scheduler(self.scheduler, afternoon)["eligible_event_ids"],
            ["event-000001"],
        )

    def test_next_long_rest_trigger_uses_monotonic_rest_counter(self) -> None:
        self._schedule(next_long_rest_trigger(self.clock))
        before = evaluate_scheduler(self.scheduler, self.clock)
        self.assertEqual(before["eligible_event_ids"], [])
        rested = apply_time_update(self.clock, elapsed_minutes=480, long_rest_completed=True)
        self.assertEqual(
            evaluate_scheduler(self.scheduler, rested)["eligible_event_ids"],
            ["event-000001"],
        )

    def test_state_condition_trigger(self) -> None:
        condition = {"path": ["gate", "open"], "operator": "equals", "value": True}
        self._schedule(state_condition_trigger(condition))
        self.assertEqual(
            evaluate_scheduler(
                self.scheduler,
                self.clock,
                runtime_state={"gate": {"open": False}},
            )["eligible_event_ids"],
            [],
        )
        self.assertEqual(
            evaluate_scheduler(
                self.scheduler,
                self.clock,
                runtime_state={"gate": {"open": True}},
            )["eligible_event_ids"],
            ["event-000001"],
        )

    def test_transition_trigger(self) -> None:
        self._schedule(transition_trigger("location:archive:entered"))
        self.assertEqual(evaluate_scheduler(self.scheduler, self.clock)["eligible_event_ids"], [])
        result = evaluate_scheduler(
            self.scheduler,
            self.clock,
            transition_keys=["location:archive:entered"],
        )
        self.assertEqual(result["eligible_event_ids"], ["event-000001"])

    def test_deadline_guard_blocks_when_world_condition_is_false(self) -> None:
        guard = {
            "path": ["target", "status"],
            "operator": "not_equals",
            "value": "safe",
        }
        self._schedule(after_elapsed_trigger(self.clock, 60), guard=guard)
        due = apply_time_update(self.clock, elapsed_minutes=60)
        result = evaluate_scheduler(
            self.scheduler,
            due,
            runtime_state={"target": {"status": "safe"}},
        )
        self.assertEqual(result["eligible_event_ids"], [])
        self.assertEqual(result["due_but_guard_blocked_event_ids"], ["event-000001"])

    def test_idempotent_creation_retry_returns_existing_event(self) -> None:
        trigger = after_elapsed_trigger(self.clock, 60)
        first = self._schedule(
            trigger,
            references={"origin_hook_id": "hook-000042"},
        )
        retry = create_event(
            self.scheduler,
            event_id="event-999999",
            dedupe_key="event:test",
            trigger=trigger,
            clock_state=self.clock,
            references={"origin_hook_id": "hook-000042"},
        )
        self.assertTrue(first["created"])
        self.assertFalse(retry["created"])
        self.assertEqual(retry["event"]["id"], "event-000001")
        self.assertEqual(len(retry["state"]["events"]), 1)

    def test_dedupe_key_reuse_with_different_definition_is_refused(self) -> None:
        self._schedule(after_elapsed_trigger(self.clock, 60))
        with self.assertRaisesRegex(ValueError, "different event definition"):
            create_event(
                self.scheduler,
                event_id="event-000002",
                dedupe_key="event:test",
                trigger=after_elapsed_trigger(self.clock, 120),
                clock_state=self.clock,
            )

    def test_multiple_eligible_events_are_surfaced_deterministically(self) -> None:
        first = create_event(
            self.scheduler,
            event_id="event-000002",
            dedupe_key="second",
            trigger=after_elapsed_trigger(self.clock, 10),
            clock_state=self.clock,
        )
        second = create_event(
            first["state"],
            event_id="event-000001",
            dedupe_key="first",
            trigger=after_elapsed_trigger(self.clock, 10),
            clock_state=self.clock,
        )
        due = apply_time_update(self.clock, elapsed_minutes=10)
        result = evaluate_scheduler(second["state"], due)
        self.assertEqual(result["eligible_event_ids"], ["event-000001", "event-000002"])

    def test_resolved_event_never_fires_again(self) -> None:
        self._schedule(after_elapsed_trigger(self.clock, 1))
        due = apply_time_update(self.clock, elapsed_minutes=1)
        self.assertEqual(
            evaluate_scheduler(self.scheduler, due)["eligible_event_ids"],
            ["event-000001"],
        )
        resolved = transition_event(self.scheduler, "event-000001", "resolved")
        self.assertEqual(evaluate_scheduler(resolved, due)["eligible_event_ids"], [])
        with self.assertRaisesRegex(ValueError, "transition is not allowed"):
            transition_event(resolved, "event-000001", "pending")

    def test_cancelled_event_never_fires(self) -> None:
        self._schedule(after_elapsed_trigger(self.clock, 1))
        cancelled = transition_event(self.scheduler, "event-000001", "cancelled")
        due = apply_time_update(self.clock, elapsed_minutes=1)
        self.assertEqual(evaluate_scheduler(cancelled, due)["eligible_event_ids"], [])

    def test_checkpoint_rejects_invalid_scheduler_state(self) -> None:
        bad = {"schema_version": 1, "events": [{"id": "broken"}]}
        manifest = _manifest([SCHEDULER_RECORD_ID])
        records = {SCHEDULER_RECORD_ID: {"revision": "rev-1", "data": bad}}
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(ValueError):
                commit_checkpoint(Path(td) / "save.json", manifest, records)

    def test_crash_before_resolution_commit_replays_pending_event(self) -> None:
        self._schedule(after_elapsed_trigger(self.clock, 1))
        due = apply_time_update(self.clock, elapsed_minutes=1)
        world = {"target": {"status": "at_risk"}}
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "save.json"
            commit_checkpoint(
                path,
                _manifest([SCHEDULER_RECORD_ID, "world_state"]),
                _records(self.scheduler, world),
            )
            loaded = load_checkpoint(path)
            reloaded_scheduler = loaded["records"][SCHEDULER_RECORD_ID]["data"]
            self.assertEqual(
                evaluate_scheduler(reloaded_scheduler, due)["eligible_event_ids"],
                ["event-000001"],
            )

    def test_failed_resolution_checkpoint_keeps_old_pending_state_and_world_state(self) -> None:
        self._schedule(after_elapsed_trigger(self.clock, 1))
        world = {"target": {"status": "at_risk"}}
        resolved = transition_event(self.scheduler, "event-000001", "resolved")
        resolved_world = {"target": {"status": "lost"}}

        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "save.json"
            manifest = _manifest([SCHEDULER_RECORD_ID, "world_state"])
            commit_checkpoint(path, manifest, _records(self.scheduler, world))

            with patch(
                "campaign_simulation.saves.os.replace",
                side_effect=OSError("simulated crash window"),
            ):
                with self.assertRaises(OSError):
                    commit_checkpoint(path, manifest, _records(resolved, resolved_world))

            loaded = load_checkpoint(path)
            self.assertEqual(
                loaded["records"][SCHEDULER_RECORD_ID]["data"]["events"][0]["status"],
                "pending",
            )
            self.assertEqual(
                loaded["records"]["world_state"]["data"]["target"]["status"],
                "at_risk",
            )

    def test_resolution_status_and_world_consequence_commit_together(self) -> None:
        self._schedule(after_elapsed_trigger(self.clock, 1))
        resolved = transition_event(self.scheduler, "event-000001", "resolved")
        world = {"target": {"status": "resolved_consequence"}}

        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "save.json"
            commit_checkpoint(
                path,
                _manifest([SCHEDULER_RECORD_ID, "world_state"]),
                _records(resolved, world),
            )
            loaded = load_checkpoint(path)
            self.assertEqual(
                loaded["records"][SCHEDULER_RECORD_ID]["data"]["events"][0]["status"],
                "resolved",
            )
            self.assertEqual(
                loaded["records"]["world_state"]["data"]["target"]["status"],
                "resolved_consequence",
            )


if __name__ == "__main__":
    unittest.main()
