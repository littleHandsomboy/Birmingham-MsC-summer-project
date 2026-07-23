"""Tests for the observation-driven replanning CLI."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from planning_system.online_cli import main


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCENARIO = (
    PROJECT_ROOT
    / "data"
    / "stream_scenarios"
    / "motor_stream_01_multilayer_m3_m4.json"
)


class OnlineCliTests(unittest.TestCase):
    def test_online_cli_writes_timed_result(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            json_path = Path(directory) / "result.json"
            report_path = Path(directory) / "report.md"
            with patch(
                "sys.argv",
                [
                    "online-planner",
                    "--scenario",
                    str(SCENARIO),
                    "--output",
                    str(report_path),
                    "--json-output",
                    str(json_path),
                ],
            ):
                exit_code = main()

            payload = json.loads(json_path.read_text(encoding="utf-8"))
            self.assertEqual(exit_code, 0)
            self.assertEqual(payload["summary"]["cycles"], 13)
            self.assertGreater(payload["summary"]["setup_ms"], 0.0)
            self.assertGreater(payload["summary"]["total_planning_ms"], 0.0)
            self.assertIn("state_update_ms", payload["cycles"][0]["timing"])
            self.assertIn("Cycle Timing", report_path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
