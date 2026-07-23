"""Tests for the current generic planning CLI."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from helpers import CASE_PATH, GOAL_PATH
from planning_system.cli import main


class GenericCliTests(unittest.TestCase):
    def test_cli_uses_generic_library_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            result_path = Path(directory) / "result.json"
            with patch(
                "sys.argv",
                [
                    "planning-system",
                    "--case",
                    str(CASE_PATH),
                    "--goal",
                    str(GOAL_PATH),
                    "--json-output",
                    str(result_path),
                ],
            ):
                exit_code = main()

            payload = json.loads(result_path.read_text(encoding="utf-8"))
            self.assertEqual(exit_code, 0)
            self.assertTrue(payload["verification"]["valid"])
            self.assertEqual(payload["visited_states"], 31)

    def test_cli_rejects_missing_input(self) -> None:
        with patch(
            "sys.argv",
            [
                "planning-system",
                "--case",
                "missing.json",
                "--goal",
                str(GOAL_PATH),
            ],
        ):
            self.assertEqual(main(), 2)


if __name__ == "__main__":
    unittest.main()
