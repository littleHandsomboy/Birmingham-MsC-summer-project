"""Tests for reports produced from grounded generic actions."""

from __future__ import annotations

import unittest

from helpers import load_actions, load_case, load_goal
from planning_system.planner import plan_disassembly
from planning_system.report import generate_markdown_report, planning_result_to_json_payload
from planning_system.verifier import verify_plan


class GenericReportTests(unittest.TestCase):
    def test_report_and_payload_contain_nested_trace(self) -> None:
        state = load_case()
        goal = load_goal()
        result = plan_disassembly(state, goal, load_actions(state))
        verification = verify_plan(state, goal, result.plan)
        report = generate_markdown_report(
            "case_07_generic_motor_m3_m4", state, goal, result, verification
        )
        payload = planning_result_to_json_payload(
            "case_07_generic_motor_m3_m4", state, goal, result, verification
        )

        self.assertIn("remove_fastener[fastener=end_cover_screws", report)
        self.assertIn("Valid: `True`", report)
        self.assertEqual(
            payload["trace"][1]["changed_fields"][
                "connections.end_cover_screws.status"
            ],
            {"before": "installed", "after": "removed"},
        )
        self.assertEqual(
            payload["final_state"]["components"]["rotor"]["status"],
            "collected",
        )


if __name__ == "__main__":
    unittest.main()
