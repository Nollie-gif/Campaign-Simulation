import json
import unittest
from pathlib import Path

from campaign_simulation.onboarding import (
    CONTINUE_WITHOUT_OPTIONAL_MATERIAL,
    build_first_boot_state,
    build_optional_material_menu,
    continue_from_optional_material,
)


ROOT = Path(__file__).resolve().parents[1]


class OnboardingTests(unittest.TestCase):
    def test_missing_minimum_input_blocks_before_menu_or_storage(self):
        state = build_first_boot_state({}, [])
        self.assertEqual(state["status"], "blocked")
        self.assertEqual(state["optional_material_menu"], None)
        self.assertEqual(state["storage_prompt"], None)

    def test_minimum_input_admits_without_optional_material(self):
        state = build_first_boot_state(
            {"campaign_history": "A short history.", "starting_situation": "A present situation."},
            [{"character_name": "A character", "character_summary": "A playable participant."}],
        )
        self.assertEqual(state["status"], "admitted")
        self.assertTrue(state["optional_material_menu"]["all_options_optional"])
        self.assertEqual(state["storage_prompt"], None)

    def test_menu_always_offers_continue_without_material(self):
        menu = build_optional_material_menu()
        option_ids = {option["id"] for option in menu["options"]}
        self.assertIn(CONTINUE_WITHOUT_OPTIONAL_MATERIAL, option_ids)

    def test_continue_without_material_reaches_storage_choice(self):
        state = continue_from_optional_material([CONTINUE_WITHOUT_OPTIONAL_MATERIAL])
        self.assertEqual(state["selected_optional_material"], [CONTINUE_WITHOUT_OPTIONAL_MATERIAL])
        self.assertEqual(state["storage_prompt"]["default"], "repository")
        self.assertEqual(state["storage_prompt"]["fallback"], "repository")

    def test_all_templates_have_only_blank_values(self):
        for template_path in (ROOT / "templates").rglob("*.json"):
            data = json.loads(template_path.read_text())
            self._assert_blank(data, template_path)

    def _assert_blank(self, value, template_path):
        if isinstance(value, dict):
            for nested_value in value.values():
                self._assert_blank(nested_value, template_path)
        elif isinstance(value, list):
            self.assertEqual(value, [], template_path)
        else:
            self.assertEqual(value, "", template_path)


if __name__ == "__main__":
    unittest.main()
