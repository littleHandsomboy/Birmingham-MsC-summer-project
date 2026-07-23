"""Tests for BFS with grounded generic disassembly actions."""

from __future__ import annotations

import unittest

from helpers import load_actions, load_case, load_goal
from planning_system.planner import plan_disassembly


class GenericPlannerTests(unittest.TestCase):
    def test_motor_case_generates_expected_reusable_sequence(self) -> None:
        state = load_case()
        result = plan_disassembly(state, load_goal(), load_actions(state))

        self.assertTrue(result.success, result.failure_reasons)
        self.assertEqual(len(result.plan), 12)
        self.assertEqual(result.visited_states, 31)
        self.assertEqual(
            result.plan[1].name,
            "remove_fastener[fastener=end_cover_screws,tool=hex_driver_m4]",
        )
        self.assertEqual(
            result.plan[5].name,
            "remove_fastener[fastener=bearing_plate_screws,tool=phillips_driver_m3]",
        )
        self.assertEqual(
            result.final_state["components"]["rotor"]["status"], "collected"
        )

    def test_goal_already_satisfied_returns_empty_plan(self) -> None:
        state = load_case()
        state["components"]["rotor"]["status"] = "collected"
        result = plan_disassembly(state, load_goal(), load_actions(state))
        self.assertTrue(result.success)
        self.assertEqual(result.plan, [])
        self.assertEqual(result.visited_states, 1)

    def test_max_iterations_returns_controlled_failure(self) -> None:
        state = load_case()
        result = plan_disassembly(
            state,
            load_goal(),
            load_actions(state),
            max_iterations=0,
        )
        self.assertFalse(result.success)
        self.assertIn("Maximum iterations reached: 0.", result.failure_reasons)


if __name__ == "__main__":
    unittest.main()
