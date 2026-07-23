"""Command-line entry point for repeated online-planning timing runs."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .benchmark import benchmark_online_scenario, generate_benchmark_markdown


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Benchmark an observation-driven planning scenario."
    )
    parser.add_argument(
        "--scenario", required=True, help="Path to a single observation-stream JSON."
    )
    parser.add_argument("--runs", type=int, default=20, help="Measured runs.")
    parser.add_argument("--warmups", type=int, default=3, help="Excluded warm-up runs.")
    parser.add_argument("--output", help="Optional Markdown report output path.")
    parser.add_argument("--json-output", help="Optional JSON result output path.")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        result = benchmark_online_scenario(args.scenario, args.runs, args.warmups)
    except (OSError, json.JSONDecodeError, ValueError) as error:
        print(f"Benchmark error: {error}")
        return 2

    print(f"Scenario: {result.scenario_name}")
    print(f"Measured runs: {result.measured_runs}")
    print(f"Successful runs: {result.successful_runs}")
    print(f"Mean planning time: {result.total_planning_ms.mean_ms:.6f} ms")
    print(f"P95 planning time: {result.total_planning_ms.p95_ms:.6f} ms")
    print(f"Mean experiment time: {result.experiment_total_ms.mean_ms:.6f} ms")

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(generate_benchmark_markdown(result), encoding="utf-8")
        print(f"Report written to: {output_path}")

    if args.json_output:
        json_path = Path(args.json_output)
        json_path.parent.mkdir(parents=True, exist_ok=True)
        json_path.write_text(json.dumps(result.to_dict(), indent=2), encoding="utf-8")
        print(f"JSON result written to: {json_path}")

    return 0 if result.all_runs_successful else 1


if __name__ == "__main__":
    raise SystemExit(main())
