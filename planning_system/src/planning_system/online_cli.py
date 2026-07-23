"""Command-line entry point for observation-driven replanning scenarios."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .online_planner import run_online_scenario
from .report import generate_online_markdown_report, online_result_to_json_payload


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run an observation-driven symbolic replanning scenario."
    )
    parser.add_argument(
        "--scenario", required=True, help="Path to a single observation-stream JSON."
    )
    parser.add_argument("--output", help="Optional Markdown report output path.")
    parser.add_argument("--json-output", help="Optional JSON result output path.")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        result = run_online_scenario(args.scenario)
    except (OSError, json.JSONDecodeError, ValueError) as error:
        print(f"Input error: {error}")
        return 2

    print(f"Scenario: {result.scenario_name}")
    print(f"Success: {result.success}")
    print(f"Cycles: {len(result.cycles)}")
    print(f"Replanning count: {result.replanning_count}")
    print(f"Observation mismatches: {result.mismatch_count}")
    print(f"Setup time: {result.setup_ms:.6f} ms")
    print(f"Total planning time: {result.total_planning_ms:.6f} ms")
    print(f"Sum of cycle times: {result.total_cycle_ms:.6f} ms")
    print(f"Experiment total time: {result.experiment_total_ms:.6f} ms")
    for cycle in result.cycles:
        print(
            f"Cycle {cycle.cycle}: {cycle.observation_id} -> "
            f"{cycle.selected_action or 'no action'} "
            f"({cycle.timing.planning_ms:.6f} ms planning)"
        )
    if result.failure_reason:
        print(f"Failure: {result.failure_reason}")

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(generate_online_markdown_report(result), encoding="utf-8")
        print(f"Report written to: {output_path}")

    if args.json_output:
        json_path = Path(args.json_output)
        json_path.parent.mkdir(parents=True, exist_ok=True)
        json_path.write_text(
            json.dumps(online_result_to_json_payload(result), indent=2),
            encoding="utf-8",
        )
        print(f"JSON result written to: {json_path}")

    return 0 if result.success else 1


if __name__ == "__main__":
    raise SystemExit(main())
