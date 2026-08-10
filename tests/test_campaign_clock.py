import unittest

from campaign_simulation.clock import (
    advance_duration,
    apply_time_update,
    campaign_time_reached,
    initial_clock_state,
    observe_presentation_time,
)


class CampaignClockTests(unittest.TestCase):
    def test_broad_phase_observation_does_not_invent_elapsed_duration(self) -> None:
        state = initial_clock_state(day=7, phase="morning", elapsed_campaign_minutes=90)
        updated = observe_presentation_time(state, phase="midday")
        self.assertEqual(updated["phase"], "midday")
        self.assertEqual(updated["elapsed_campaign_minutes"], 90)

    def test_confirmed_duration_advances_only_monotonic_cursor(self) -> None:
        state = initial_clock_state(day=7, phase="morning", elapsed_campaign_minutes=90)
        updated = advance_duration(state, 75)
        self.assertEqual(updated["elapsed_campaign_minutes"], 165)
        self.assertEqual(updated["day"], 7)
        self.assertEqual(updated["phase"], "morning")

    def test_combined_update_accepts_duration_and_established_presentation_time(self) -> None:
        state = initial_clock_state(day=7, phase="morning")
        updated = apply_time_update(
            state,
            elapsed_minutes=120,
            day=7,
            phase="afternoon",
        )
        self.assertEqual(updated["elapsed_campaign_minutes"], 120)
        self.assertEqual(updated["phase"], "afternoon")

    def test_day_cannot_move_backwards(self) -> None:
        state = initial_clock_state(day=7, phase="morning")
        with self.assertRaisesRegex(ValueError, "day cannot move backwards"):
            observe_presentation_time(state, day=6)

    def test_phase_cannot_move_backwards_within_same_day(self) -> None:
        state = initial_clock_state(day=7, phase="afternoon")
        with self.assertRaisesRegex(ValueError, "phase cannot move backwards"):
            observe_presentation_time(state, phase="morning")

    def test_new_day_allows_earlier_phase(self) -> None:
        state = initial_clock_state(day=7, phase="late_night")
        updated = observe_presentation_time(state, day=8, phase="dawn")
        self.assertEqual((updated["day"], updated["phase"]), (8, "dawn"))

    def test_unknown_phase_is_conservative_for_campaign_time_target(self) -> None:
        state = initial_clock_state(day=7, phase="unknown")
        self.assertFalse(campaign_time_reached(state, target_day=7, target_phase="morning"))
        next_day = observe_presentation_time(state, day=8, phase="unknown")
        self.assertTrue(campaign_time_reached(next_day, target_day=7, target_phase="morning"))

    def test_long_rest_counter_advances_without_forcing_duration(self) -> None:
        state = initial_clock_state(day=7, phase="night")
        updated = apply_time_update(state, long_rest_completed=True)
        self.assertEqual(updated["long_rests_completed"], 1)
        self.assertEqual(updated["elapsed_campaign_minutes"], 0)


if __name__ == "__main__":
    unittest.main()
