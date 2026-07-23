"""Tests for project utility scripts."""

from __future__ import annotations

import json
import subprocess
import sys
import unittest

from helpers import PROJECT_ROOT


class ScriptTests(unittest.TestCase):
    def test_run_all_cases_writes_summary_markdown(self) -> None:
        output_path = PROJECT_ROOT / "outputs" / "case_summary.md"
        completed = subprocess.run(
            [sys.executable, "scripts/run_all_cases.py"],
            cwd=PROJECT_ROOT,
            check=False,
            capture_output=True,
            text=True,
        )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertTrue(output_path.exists())
        content = output_path.read_text(encoding="utf-8")
        self.assertIn("case_07_generic_motor_m3_m4", content)
        self.assertNotIn("case_06_pmsm_motor_permanent_magnet", content)
        self.assertIn("goal_collect_generic_rotor.json", content)
        self.assertIn("collect_component", content)
        self.assertIn("success", content)
        self.assertIn("validation", content)

    def test_run_online_scenarios_writes_expected_summary(self) -> None:
        output_path = (
            PROJECT_ROOT / "outputs" / "online" / "online_scenario_summary.md"
        )
        completed = subprocess.run(
            [sys.executable, "scripts/run_online_scenarios.py"],
            cwd=PROJECT_ROOT,
            check=False,
            capture_output=True,
            text=True,
        )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        content = output_path.read_text(encoding="utf-8")
        self.assertIn("motor_stream_01_multilayer_m3_m4", content)
        self.assertIn("motor_stream_03_prediction_conflict", content)
        self.assertIn("motor_stream_05_no_visible_frontier", content)
        scenario_rows = [
            line for line in content.splitlines() if line.startswith("| motor_stream_")
        ]
        self.assertEqual(len(scenario_rows), 6)
        for row in scenario_rows:
            fields = [field.strip() for field in row.strip("|").split("|")]
            self.assertEqual(fields[3], "True")

    def test_documented_motor_suite_runs_ten_expected_cases(self) -> None:
        generation = subprocess.run(
            [sys.executable, "scripts/generate_motor_test_cases.py"],
            cwd=PROJECT_ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        execution = subprocess.run(
            [sys.executable, "scripts/run_motor_test_cases.py"],
            cwd=PROJECT_ROOT,
            check=False,
            capture_output=True,
            text=True,
        )

        self.assertEqual(generation.returncode, 0, generation.stderr)
        self.assertEqual(execution.returncode, 0, execution.stderr)
        case_paths = sorted((PROJECT_ROOT / "data" / "test_cases").glob("*.json"))
        self.assertEqual(len(case_paths), 10)
        for case_path in case_paths:
            payload = json.loads(case_path.read_text(encoding="utf-8"))
            self.assertEqual(next(iter(payload)), "test_case")

        summary = (
            PROJECT_ROOT
            / "outputs"
            / "motor_test_cases"
            / "motor_test_case_summary.md"
        ).read_text(encoding="utf-8")
        rows = [line for line in summary.splitlines() if line.startswith("| motor_case_")]
        self.assertEqual(len(rows), 10)
        self.assertTrue(all("| True |" in row for row in rows))

        first_report = (
            PROJECT_ROOT
            / "outputs"
            / "motor_test_cases"
            / "motor_case_01_m4_hex_fasteners_report.md"
        ).read_text(encoding="utf-8")
        self.assertIn("## Test Case Description", first_report)


if __name__ == "__main__":
    unittest.main()
