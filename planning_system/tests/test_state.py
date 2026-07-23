"""Tests for nested state loading, goals, and validation."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from helpers import load_case, load_goal
from planning_system.state import (
    get_nested_value,
    load_state_from_json,
    make_hashable_state,
    set_nested_value,
    state_satisfies_goal,
    validate_structured_state,
)


class StructuredStateTests(unittest.TestCase):
    def test_primary_case_is_valid(self) -> None:
        validate_structured_state(load_case())

    def test_nested_goal_and_nested_update(self) -> None:
        state = load_case()
        self.assertFalse(state_satisfies_goal(state, load_goal()))
        updated = set_nested_value(state, "components.rotor.status", "collected")
        self.assertTrue(state_satisfies_goal(updated, load_goal()))
        self.assertEqual(get_nested_value(updated, "components.rotor.status"), "collected")
        self.assertEqual(get_nested_value(state, "components.rotor.status"), "installed")

    def test_hashable_state_normalizes_nested_lists(self) -> None:
        left = make_hashable_state({"tools": {"driver": {"sizes": ["M4", "M3"]}}})
        right = make_hashable_state({"tools": {"driver": {"sizes": ["M3", "M4"]}}})
        self.assertEqual(left, right)

    def test_loader_requires_top_level_object(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "invalid.json"
            path.write_text(json.dumps(["invalid"]), encoding="utf-8")
            with self.assertRaises(ValueError):
                load_state_from_json(path)


if __name__ == "__main__":
    unittest.main()
