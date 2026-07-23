"""Tests for observation-driven one-action-per-cycle replanning."""

from __future__ import annotations

import unittest
import json
import tempfile
from pathlib import Path

from planning_system.online_planner import load_online_scenario, run_online_scenario


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCENARIO_DIR = PROJECT_ROOT / "data" / "stream_scenarios"


class OnlinePlannerTests(unittest.TestCase):
    def test_incremental_scenario_confirms_goal_after_twelve_actions(self) -> None:
        result = run_online_scenario(
            SCENARIO_DIR / "motor_stream_01_multilayer_m3_m4.json"
        )

        self.assertTrue(result.success, result.failure_reason)
        self.assertTrue(result.goal_reached)
        self.assertEqual(len(result.cycles), 13)
        self.assertEqual(result.replanning_count, 11)
        self.assertEqual(result.mismatch_count, 0)
        self.assertEqual(
            [
                cycle.selected_action_template
                for cycle in result.cycles
                if cycle.selected_action_template is not None
            ],
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
        self.assertTrue(
            all(cycle.verification_valid is True for cycle in result.cycles)
        )
        self.assertEqual(
            result.final_state["components"]["rotor"]["status"], "collected"
        )
        self.assertEqual(result.cycles[-1].goal_type, "final_observed")
        self.assertIsNone(result.cycles[-1].selected_action)
        self.assertGreater(result.total_planning_ms, 0.0)
        self.assertGreater(result.setup_ms, 0.0)
        self.assertGreater(result.total_cycle_ms, result.total_planning_ms)
        self.assertGreaterEqual(result.experiment_total_ms, result.total_planning_ms)
        self.assertGreaterEqual(
            result.experiment_total_ms,
            result.setup_ms + result.total_cycle_ms,
        )
        for cycle in result.cycles:
            self.assertTrue(
                all(value >= 0.0 for value in cycle.timing.to_dict().values())
            )
            self.assertGreaterEqual(
                cycle.timing.cycle_total_ms,
                cycle.timing.planning_ms,
            )

    def test_conflicting_observation_overrides_prediction_and_replans(self) -> None:
        result = run_online_scenario(
            SCENARIO_DIR / "motor_stream_03_prediction_conflict.json"
        )

        self.assertFalse(result.success)
        self.assertEqual(result.mismatch_count, 1)
        conflict_cycle = result.cycles[2]
        self.assertEqual(
            conflict_cycle.state_after_observation["connections"][
                "end_cover_screws"
            ]["status"],
            "installed",
        )
        self.assertEqual(
            conflict_cycle.expected_state_after_action["connections"][
                "end_cover_screws"
            ]["status"],
            "removed",
        )
        self.assertEqual(conflict_cycle.selected_action_template, "remove_fastener")

    def test_no_visible_frontier_stops_with_explanation(self) -> None:
        result = run_online_scenario(
            SCENARIO_DIR / "motor_stream_05_no_visible_frontier.json"
        )
        self.assertFalse(result.success)
        self.assertEqual(len(result.cycles), 1)
        self.assertIsNone(result.cycles[0].selected_action)
        self.assertGreaterEqual(result.cycles[0].planning_attempts, 1)
        self.assertGreaterEqual(result.cycles[0].total_visited_states, 1)
        self.assertIn("No reachable final goal or frontier goal", result.failure_reason or "")

    def test_clip_retainer_uses_reusable_release_action(self) -> None:
        result = run_online_scenario(
            SCENARIO_DIR / "motor_stream_02_clip_retainer.json"
        )
        self.assertTrue(result.success, result.failure_reason)
        self.assertEqual(
            [
                cycle.selected_action_template
                for cycle in result.cycles
                if cycle.selected_action_template is not None
            ],
            ["change_tool", "release_retainer", "change_tool", "remove_component"],
        )
        self.assertEqual(result.cycles[-1].goal_type, "final_observed")

    def test_unavailable_compatible_tool_stops_with_explanation(self) -> None:
        result = run_online_scenario(
            SCENARIO_DIR / "motor_stream_04_missing_m4_driver.json"
        )
        self.assertFalse(result.success)
        self.assertIsNone(result.cycles[0].selected_action)
        self.assertIn("No reachable final goal", result.failure_reason or "")

    def test_adhesive_stream_uses_debonding_before_removal(self) -> None:
        result = run_online_scenario(
            SCENARIO_DIR / "motor_stream_06_adhesive_cover.json"
        )
        self.assertTrue(result.success, result.failure_reason)
        self.assertEqual(
            [
                cycle.selected_action_template
                for cycle in result.cycles
                if cycle.selected_action_template is not None
            ],
            [
                "change_tool",
                "debond_joint",
                "change_tool",
                "remove_component",
                "change_tool",
                "pull_component",
                "change_tool",
                "collect_component",
            ],
        )
        self.assertEqual(result.cycles[-1].goal_type, "final_observed")

    def test_stream_loader_rejects_non_consecutive_sequence(self) -> None:
        source = json.loads(
            (SCENARIO_DIR / "motor_stream_05_no_visible_frontier.json").read_text(
                encoding="utf-8"
            )
        )
        source["observation_stream"][0]["sequence"] = 2
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "invalid_stream.json"
            path.write_text(json.dumps(source), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "consecutive"):
                load_online_scenario(path)


if __name__ == "__main__":
    unittest.main()
