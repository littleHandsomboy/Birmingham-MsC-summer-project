"""Tests for the repeated timing benchmark command line interface."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from planning_system.benchmark_cli import main


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCENARIO = (
    PROJECT_ROOT
    / "data"
    / "stream_scenarios"
    / "motor_stream_01_multilayer_m3_m4.json"
)


class BenchmarkCliTests(unittest.TestCase):
    def test_cli_writes_repeated_timing_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            json_path = Path(directory) / "benchmark.json"
            report_path = Path(directory) / "benchmark.md"
            with patch(
                "sys.argv",
                [
                    "planning-benchmark",
                    "--scenario",
                    str(SCENARIO),
                    "--runs",
                    "2",
                    "--warmups",
                    "1",
                    "--output",
                    str(report_path),
                    "--json-output",
                    str(json_path),
                ],
            ):
                exit_code = main()

            payload = json.loads(json_path.read_text(encoding="utf-8"))
            self.assertEqual(exit_code, 0)
            self.assertEqual(payload["measured_runs"], 2)
            self.assertTrue(payload["all_runs_successful"])
            self.assertIn("Overall Timing", report_path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
