"""Tests for replay verification of grounded plans."""

from __future__ import annotations

import unittest

from helpers import load_actions, load_case, load_goal
from planning_system.planner import plan_disassembly
from planning_system.verifier import verify_plan


class GenericVerifierTests(unittest.TestCase):
    def test_generated_plan_verifies(self) -> None:
        state = load_case()
        result = plan_disassembly(state, load_goal(), load_actions(state))
        verification = verify_plan(state, load_goal(), result.plan)
        self.assertTrue(verification.valid, verification.reason)
        self.assertTrue(verification.goal_reached)

    def test_fastener_removal_without_tool_change_is_rejected(self) -> None:
        state = load_case()
        action = next(
            action
            for action in load_actions(state)
            if action.name
            == "remove_fastener[fastener=end_cover_screws,tool=hex_driver_m4]"
        )
        verification = verify_plan(state, load_goal(), [action])
        self.assertFalse(verification.valid)
        self.assertEqual(verification.failed_step, 1)
        self.assertIn("robot.mounted_tool", verification.reason or "")


if __name__ == "__main__":
    unittest.main()
