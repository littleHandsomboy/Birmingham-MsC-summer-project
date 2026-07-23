"""Command-line entry point for the planning system prototype."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Optional

from .action_grounder import ground_action_templates
from .action_library import load_action_templates
from .planner import PlanningResult, plan_disassembly
from .report import generate_markdown_report, planning_result_to_json_payload
from .state import load_state_from_json, validate_structured_state
from .verifier import VerificationResult, verify_plan


DEFAULT_ACTION_LIBRARY = (
    Path(__file__).resolve().parents[2]
    / "data"
    / "generic_disassembly_action_library.json"
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the planning system prototype.")
    parser.add_argument("--case", required=True, help="Path to an object state JSON file.")
    parser.add_argument("--goal", required=True, help="Path to a goal JSON file.")
    parser.add_argument(
        "--action-library",
        default=str(DEFAULT_ACTION_LIBRARY),
        help="Reusable action-template library JSON file.",
    )
    parser.add_argument("--output", help="Optional Markdown report output path.")
    parser.add_argument("--json-output", help="Optional JSON result output path.")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    try:
        initial_state = load_state_from_json(args.case)
        goal = load_state_from_json(args.goal)
        validate_structured_state(initial_state)
        actions = ground_action_templates(
            initial_state,
            load_action_templates(args.action_library),
        )
    except (OSError, json.JSONDecodeError, ValueError) as error:
        print(f"Input error: {error}")
        return 2

    planning_result = plan_disassembly(initial_state, goal, actions)
    verification_result = (
        verify_plan(initial_state, goal, planning_result.plan)
        if planning_result.success
        else None
    )

    _print_summary(planning_result, verification_result)

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        report = generate_markdown_report(
            case_name=Path(args.case).stem,
            initial_state=initial_state,
            goal=goal,
            planning_result=planning_result,
            verification_result=verification_result,
        )
        output_path.write_text(report, encoding="utf-8")
        print(f"Report written to: {output_path}")

    if args.json_output:
        json_output_path = Path(args.json_output)
        json_output_path.parent.mkdir(parents=True, exist_ok=True)
        payload = planning_result_to_json_payload(
            case_name=Path(args.case).stem,
            initial_state=initial_state,
            goal=goal,
            planning_result=planning_result,
            verification_result=verification_result,
        )
        json_output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        print(f"JSON result written to: {json_output_path}")

    return 0 if planning_result.success else 1


def _print_summary(
    planning_result: PlanningResult,
    verification_result: Optional[VerificationResult],
) -> None:
    print(f"Planning success: {planning_result.success}")
    if planning_result.plan:
        print("Plan: " + " -> ".join(action.name for action in planning_result.plan))
    else:
        print("Plan: No valid plan found.")

    if verification_result is None:
        print("Validation: skipped")
    else:
        print(f"Validation valid: {verification_result.valid}")

    if planning_result.failure_reasons:
        print("Failure reasons:")
        for reason in planning_result.failure_reasons:
            print(f"- {reason}")


if __name__ == "__main__":
    raise SystemExit(main())
