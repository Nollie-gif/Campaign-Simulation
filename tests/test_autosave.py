import unittest

from campaign_simulation.autosave import evaluate_autosave, initial_autosave_state
from campaign_simulation.clock import initial_clock_state, observe_presentation_time


class AutosaveTests(unittest.TestCase):
    def setUp(self) -> None:
        self.clock = initial_clock_state(day=4, phase="morning")
        self.state = initial_autosave_state(self.clock)

    def test_minor_dialogue_does_not_trigger(self) -> None:
        result = evaluate_autosave(
            self.state,
            self.clock,
            {"scene_resolved": True, "change_level": "minor"},
        )
        self.assertFalse(result["trigger"])
        self.assertEqual(result["reason"], "no_trigger")

    def test_meaningful_phase_transition_triggers(self) -> None:
        later = observe_presentation_time(self.clock, phase="midday")
        result = evaluate_autosave(
            self.state,
            later,
            {"scene_resolved": True, "change_level": "meaningful"},
        )
        self.assertTrue(result["trigger"])
        self.assertEqual(result["reason"], "day_phase_transition")

    def test_major_event_triggers_immediately(self) -> None:
        result = evaluate_autosave(
            self.state,
            self.clock,
            {"scene_resolved": True, "change_level": "major"},
        )
        self.assertTrue(result["trigger"])
        self.assertEqual(result["reason"], "major_persistent_event")

    def test_duplicate_state_suppresses_automatic_save(self) -> None:
        state = dict(self.state)
        state["last_saved_state_fingerprint"] = "same"
        result = evaluate_autosave(
            state,
            self.clock,
            {
                "scene_resolved": True,
                "change_level": "major",
                "state_fingerprint": "same",
            },
        )
        self.assertFalse(result["trigger"])
        self.assertEqual(result["reason"], "duplicate_state")

    def test_manual_save_overrides_duplicate_suppression(self) -> None:
        state = dict(self.state)
        state["last_saved_state_fingerprint"] = "same"
        result = evaluate_autosave(
            state,
            self.clock,
            {
                "scene_resolved": False,
                "change_level": "none",
                "manual_save_requested": True,
                "state_fingerprint": "same",
            },
        )
        self.assertTrue(result["trigger"])
        self.assertFalse(result["automatic"])
        self.assertEqual(result["reason"], "manual_request")

    def test_soft_cap_suppresses_ordinary_autosave(self) -> None:
        state = dict(self.state)
        state["automatic_saves_today"] = 5
        result = evaluate_autosave(
            state,
            self.clock,
            {"scene_resolved": True, "change_level": "major"},
        )
        self.assertFalse(result["trigger"])
        self.assertEqual(result["reason"], "ordinary_autosave_soft_cap_reached")

    def test_critical_boundary_can_exceed_soft_cap(self) -> None:
        state = dict(self.state)
        state["automatic_saves_today"] = 5
        result = evaluate_autosave(
            state,
            self.clock,
            {"scene_resolved": True, "change_level": "critical"},
        )
        self.assertTrue(result["trigger"])
        self.assertEqual(result["reason"], "critical_persistence_boundary")
        self.assertEqual(result["state"]["automatic_saves_today"], 6)

    def test_accumulated_three_scenes_with_meaningful_progress_triggers(self) -> None:
        state = self.state
        for level in ("meaningful", "minor"):
            result = evaluate_autosave(
                state,
                self.clock,
                {"scene_resolved": True, "change_level": level},
            )
            self.assertFalse(result["trigger"])
            state = result["state"]

        result = evaluate_autosave(
            state,
            self.clock,
            {"scene_resolved": True, "change_level": "minor"},
        )
        self.assertTrue(result["trigger"])
        self.assertEqual(result["reason"], "accumulated_meaningful_progress")

    def test_day_transition_resets_daily_count(self) -> None:
        state = dict(self.state)
        state["automatic_saves_today"] = 5
        next_day = observe_presentation_time(self.clock, day=5, phase="dawn")
        result = evaluate_autosave(
            state,
            next_day,
            {"scene_resolved": True, "change_level": "meaningful"},
        )
        self.assertTrue(result["trigger"])
        self.assertEqual(result["reason"], "day_transition")
        self.assertEqual(result["state"]["automatic_saves_today"], 1)


if __name__ == "__main__":
    unittest.main()

