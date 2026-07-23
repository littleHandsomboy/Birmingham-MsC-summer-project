"""Tests for repeated online-planning timing measurements."""

from __future__ import annotations

import unittest
from pathlib import Path

from planning_system.benchmark import (
    benchmark_online_scenario,
    generate_benchmark_markdown,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCENARIO = (
    PROJECT_ROOT
    / "data"
    / "stream_scenarios"
    / "motor_stream_01_multilayer_m3_m4.json"
)


class BenchmarkTests(unittest.TestCase):
    def test_repeated_benchmark_reports_aggregate_and_cycle_timing(self) -> None:
        result = benchmark_online_scenario(SCENARIO, measured_runs=3, warmup_runs=1)

        self.assertTrue(result.all_runs_successful)
        self.assertEqual(result.measured_runs, 3)
        self.assertEqual(len(result.runs), 3)
        self.assertEqual(len(result.cycle_statistics), 13)
        self.assertGreater(result.total_planning_ms.mean_ms, 0.0)
        self.assertGreaterEqual(
            result.total_planning_ms.p95_ms,
            result.total_planning_ms.median_ms,
        )
        self.assertIn("Per-Cycle Timing", generate_benchmark_markdown(result))

    def test_benchmark_rejects_invalid_run_counts(self) -> None:
        with self.assertRaises(ValueError):
            benchmark_online_scenario(SCENARIO, measured_runs=0)
        with self.assertRaises(ValueError):
            benchmark_online_scenario(SCENARIO, measured_runs=1, warmup_runs=-1)


if __name__ == "__main__":
    unittest.main()
