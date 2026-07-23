"""Tests for reusable action templates and grounded motor actions."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from planning_system.action_grounder import ground_action_templates
from planning_system.action_library import load_action_templates
from planning_system.planner import plan_disassembly
from planning_system.state import load_state_from_json, validate_structured_state
from planning_system.verifier import verify_plan


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
LIBRARY_PATH = DATA_DIR / "generic_disassembly_action_library.json"
CASE_PATH = DATA_DIR / "case_07_generic_motor_m3_m4.json"
GOAL_PATH = DATA_DIR / "goal_collect_generic_rotor.json"


class GenericActionLibraryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.state = load_state_from_json(CASE_PATH)
        self.templates = load_action_templates(LIBRARY_PATH)
        self.actions = ground_action_templates(self.state, self.templates)

    def test_library_loads_unique_reusable_templates(self) -> None:
        self.assertEqual(
            [template.name for template in self.templates],
            [
                "change_tool",
                "inspect_component",
                "remove_fastener",
                "release_retainer",
                "disconnect_connection",
                "debond_joint",
                "cut_connection",
                "remove_component",
                "pull_component",
                "collect_component",
            ],
        )

    def test_structured_motor_state_is_valid(self) -> None:
        validate_structured_state(self.state)

    def test_structured_state_rejects_unknown_component_reference(self) -> None:
        invalid_state = json.loads(json.dumps(self.state))
        invalid_state["connections"]["end_cover_screws"]["connects"] = [
            "end_cover",
            "missing_component",
        ]
        with self.assertRaisesRegex(ValueError, "missing_component"):
            validate_structured_state(invalid_state)

    def test_grounder_matches_fastener_size_drive_and_tool(self) -> None:
        fastener_actions = {
            action.name: action
            for action in self.actions
            if action.template.name == "remove_fastener"
        }

        m4_name = (
            "remove_fastener[fastener=end_cover_screws,tool=hex_driver_m4]"
        )
        m3_name = (
            "remove_fastener[fastener=bearing_plate_screws,"
            "tool=phillips_driver_m3]"
        )
        self.assertIn(m4_name, fastener_actions)
        self.assertIn(m3_name, fastener_actions)
        self.assertNotIn(
            "remove_fastener[fastener=end_cover_screws,tool=phillips_driver_m3]",
            fastener_actions,
        )
        self.assertAlmostEqual(fastener_actions[m4_name].expected_time or 0.0, 4.2)
        self.assertAlmostEqual(fastener_actions[m3_name].expected_time or 0.0, 3.4)

    def test_component_removal_is_blocked_by_installed_connection(self) -> None:
        action = next(
            action
            for action in self.actions
            if action.name
            == "remove_component[component=end_cover,tool=parallel_gripper]"
        )
        reasons = action.failed_reasons(self.state)
        self.assertIn("end_cover_screws", " ".join(reasons))
        self.assertIn("mounted_tool", " ".join(reasons))

    def test_other_connection_templates_are_reusable(self) -> None:
        state = json.loads(json.dumps(self.state))
        state["connections"] = {
            "cover_clip": {
                "type": "clip",
                "connects": ["end_cover", "housing"],
                "retaining": True,
                "status": "installed",
                "accessible": True,
            },
            "terminal_connector": {
                "type": "electrical_connector",
                "connects": ["end_cover", "housing"],
                "retaining": True,
                "status": "installed",
                "accessible": True,
            },
            "cover_adhesive": {
                "type": "adhesive_joint",
                "connects": ["end_cover", "housing"],
                "retaining": True,
                "status": "installed",
                "accessible": True,
            },
        }
        state["tools"].update(
            {
                "clip_tool": {
                    "type": "hand_tool",
                    "capabilities": ["release_retainer"],
                    "connection_types": ["clip"],
                    "available": True,
                },
                "connector_tool": {
                    "type": "hand_tool",
                    "capabilities": ["disconnect"],
                    "connection_types": ["electrical_connector"],
                    "available": True,
                },
                "heat_tool": {
                    "type": "thermal_tool",
                    "capabilities": ["debond"],
                    "available": True,
                },
            }
        )
        actions = ground_action_templates(state, self.templates)
        names = {action.name for action in actions}
        self.assertIn(
            "release_retainer[connection=cover_clip,tool=clip_tool]", names
        )
        self.assertIn(
            "disconnect_connection[connection=terminal_connector,tool=connector_tool]",
            names,
        )
        self.assertIn(
            "debond_joint[connection=cover_adhesive,tool=heat_tool]", names
        )

    def test_generic_motor_plan_reuses_templates_and_verifies(self) -> None:
        goal = load_state_from_json(GOAL_PATH)
        result = plan_disassembly(self.state, goal, self.actions)

        self.assertTrue(result.success, result.failure_reasons)
        self.assertEqual(
            [action.template.name for action in result.plan],
            [
                "change_tool",
                "remove_fastener",
                "change_tool",
                "remove_component",
                "change_tool",
                "remove_fastener",
                "change_tool",
                "remove_component",
                "change_tool",
                "pull_component",
                "change_tool",
                "collect_component",
            ],
        )
        self.assertEqual(
            result.final_state["components"]["rotor"]["status"],
            "collected",
        )

        verification = verify_plan(self.state, goal, result.plan)
        self.assertTrue(verification.valid, verification.reason)

    def test_loader_rejects_missing_actions_list(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "invalid_library.json"
            path.write_text(json.dumps({"name": "invalid"}), encoding="utf-8")
            with self.assertRaises(ValueError):
                load_action_templates(path)


if __name__ == "__main__":
    unittest.main()
