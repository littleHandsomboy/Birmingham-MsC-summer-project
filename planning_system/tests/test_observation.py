"""Tests for partial observations and prediction mismatch handling."""

from __future__ import annotations

import unittest

from helpers import load_case
from planning_system.observation import (
    Observation,
    find_observation_mismatches,
    merge_observation,
)


class ObservationTests(unittest.TestCase):
    def test_newly_revealed_fields_merge_without_false_mismatch(self) -> None:
        state = load_case()
        observation = Observation(
            observation_id="new_component",
            source="simulated_camera",
            updates={
                "components": {
                    "new_bearing": {
                        "type": "bearing",
                        "status": "installed",
                        "accessible": True,
                    }
                }
            },
        )
        self.assertEqual(find_observation_mismatches(state, observation), [])
        merged = merge_observation(state, observation)
        self.assertIn("new_bearing", merged["components"])
        self.assertNotIn("new_bearing", state["components"])

    def test_observed_value_overrides_prediction_and_records_mismatch(self) -> None:
        state = load_case()
        state["connections"]["end_cover_screws"]["status"] = "removed"
        observation = Observation(
            observation_id="conflict",
            source="simulated_camera",
            updates={
                "connections": {
                    "end_cover_screws": {"status": "installed"}
                }
            },
        )
        mismatches = find_observation_mismatches(state, observation)
        merged = merge_observation(state, observation)

        self.assertEqual(len(mismatches), 1)
        self.assertEqual(mismatches[0].path, "connections.end_cover_screws.status")
        self.assertEqual(mismatches[0].expected, "removed")
        self.assertEqual(mismatches[0].observed, "installed")
        self.assertEqual(
            merged["connections"]["end_cover_screws"]["status"], "installed"
        )


if __name__ == "__main__":
    unittest.main()
