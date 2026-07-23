"""Report helpers for planning and verification output."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Union

from .planner import PlanningResult
from .online_planner import OnlinePlanningResult
from .trace import TraceStep, build_plan_trace
from .verifier import VerificationResult


def planning_result_to_dict(result: PlanningResult) -> Dict[str, Any]:
    """Convert a planning result into a JSON-serializable dictionary."""
    return {
        "success": result.success,
        "plan": [action.name for action in result.plan],
        "plan_length": len(result.plan),
        "final_state": result.final_state,
        "failure_reasons": result.failure_reasons,
        "visited_states": result.visited_states,
    }


def verification_result_to_dict(result: VerificationResult) -> Dict[str, Any]:
    """Convert a verification result into a JSON-serializable dictionary."""
    return {
        "valid": result.valid,
        "goal_reached": result.goal_reached,
        "final_state": result.final_state,
        "failed_step": result.failed_step,
        "action_name": result.action_name,
        "reason": result.reason,
        "messages": result.messages,
    }


def write_json_report(path: Union[str, Path], payload: Dict[str, Any]) -> None:
    """Write a JSON report to disk."""
    Path(path).write_text(json.dumps(payload, indent=2), encoding="utf-8")


def generate_markdown_report(
    case_name: str,
    initial_state: Dict[str, Any],
    goal: Dict[str, Any],
    planning_result: PlanningResult,
    verification_result: Union[VerificationResult, None],
) -> str:
    """Generate a human-readable Markdown report for a planning run."""
    trace = _safe_trace(initial_state, planning_result.plan)
    lines = [
        "# Disassembly Planning Report",
        "",
        f"## Case",
        "",
        f"- Name: `{case_name}`",
        "",
        "## Initial State Summary",
        "",
        *_format_mapping(initial_state),
        "",
        "## Goal",
        "",
        *_format_mapping(goal),
        "",
        "## Planning Status",
        "",
        f"- Success: `{planning_result.success}`",
        f"- Visited states: `{planning_result.visited_states}`",
        "",
        "## Generated Plan",
        "",
    ]

    if planning_result.plan:
        for index, action in enumerate(planning_result.plan, start=1):
            lines.append(f"{index}. `{action.name}` - {action.description}")
    else:
        lines.append("No valid plan generated.")

    lines.extend(["", "## Step-by-Step Trace", ""])
    if trace:
        for step in trace:
            lines.extend(
                [
                    f"### Step {step.step}: `{step.action_name}`",
                    "",
                    "Changed Fields:",
                    "",
                ]
            )
            if step.changed_fields:
                for field_name, change in step.changed_fields.items():
                    lines.append(
                        f"- `{field_name}`: `{change['before']}` -> `{change['after']}`"
                    )
            else:
                lines.append("- No state fields changed.")
            lines.append("")
    else:
        lines.append("No trace available.")

    lines.extend(["", "## Mermaid Flowchart", "", "```mermaid"])
    lines.extend(generate_mermaid_flowchart(planning_result).splitlines())
    lines.append("```")

    lines.extend(["", "## Validation Result", ""])
    if verification_result is None:
        lines.append("Validation was not run.")
    else:
        lines.extend(
            [
                f"- Valid: `{verification_result.valid}`",
                f"- Goal reached: `{verification_result.goal_reached}`",
            ]
        )
        if verification_result.failed_step is not None:
            lines.append(f"- Failed step: `{verification_result.failed_step}`")
        if verification_result.action_name is not None:
            lines.append(f"- Failed action: `{verification_result.action_name}`")
        if verification_result.reason is not None:
            lines.append(f"- Reason: {verification_result.reason}")
        for message in verification_result.messages:
            lines.append(f"- Message: {message}")

    final_state = (
        verification_result.final_state
        if verification_result is not None
        else planning_result.final_state
    )
    lines.extend(["", "## Final State", ""])
    if final_state:
        lines.extend(_format_mapping(final_state))
    else:
        lines.append("No final state available.")

    if planning_result.failure_reasons:
        lines.extend(["", "## Failure Reasons", ""])
        for reason in planning_result.failure_reasons:
            lines.append(f"- {reason}")

    return "\n".join(lines).strip() + "\n"


def _format_mapping(values: Dict[str, Any]) -> list[str]:
    return [f"- `{key}`: `{value}`" for key, value in sorted(values.items())]


def generate_mermaid_flowchart(planning_result: PlanningResult) -> str:
    """Return a Mermaid flowchart for a successful or failed planning result."""
    lines = ['flowchart TD', '  S0["Initial State"]']
    if not planning_result.plan:
        lines.append('  S0 --> F["No Valid Plan"]')
        return "\n".join(lines)

    previous_node = "S0"
    for index, action in enumerate(planning_result.plan, start=1):
        current_node = f"S{index}"
        lines.append(f'  {previous_node} --> {current_node}["{action.name}"]')
        previous_node = current_node
    lines.append(f'  {previous_node} --> G["Goal Reached"]')
    return "\n".join(lines)


def planning_result_to_json_payload(
    case_name: str,
    initial_state: Dict[str, Any],
    goal: Dict[str, Any],
    planning_result: PlanningResult,
    verification_result: Union[VerificationResult, None],
) -> Dict[str, Any]:
    """Build the stable JSON payload used by the CLI and UI."""
    final_state = (
        verification_result.final_state
        if verification_result is not None
        else planning_result.final_state
    )
    return {
        "case_name": case_name,
        "success": planning_result.success,
        "plan": [action.name for action in planning_result.plan],
        "visited_states": planning_result.visited_states,
        "initial_state": initial_state,
        "goal": goal,
        "final_state": final_state,
        "failure_reasons": planning_result.failure_reasons,
        "verification": (
            verification_result_to_dict(verification_result)
            if verification_result is not None
            else None
        ),
        "trace": [_trace_step_to_dict(step) for step in _safe_trace(initial_state, planning_result.plan)],
    }


def _safe_trace(initial_state: Dict[str, Any], plan) -> list[TraceStep]:
    if not plan:
        return []
    try:
        return build_plan_trace(initial_state, plan)
    except ValueError:
        return []


def _trace_step_to_dict(step: TraceStep) -> Dict[str, Any]:
    return {
        "step": step.step,
        "action_name": step.action_name,
        "state_before": step.state_before,
        "state_after": step.state_after,
        "changed_fields": step.changed_fields,
    }


def online_result_to_json_payload(result: OnlinePlanningResult) -> Dict[str, Any]:
    """Convert an online experiment result into a stable JSON payload."""
    return {
        "scenario_name": result.scenario_name,
        "success": result.success,
        "goal_reached": result.goal_reached,
        "failure_reason": result.failure_reason,
        "initial_state": result.initial_state,
        "goal": result.goal,
        "final_state": result.final_state,
        "summary": {
            "cycles": len(result.cycles),
            "executed_actions": sum(
                cycle.selected_action is not None for cycle in result.cycles
            ),
            "replanning_count": result.replanning_count,
            "mismatch_count": result.mismatch_count,
            "setup_ms": result.setup_ms,
            "total_planning_ms": result.total_planning_ms,
            "total_cycle_ms": result.total_cycle_ms,
            "experiment_total_ms": result.experiment_total_ms,
        },
        "cycles": [_online_cycle_to_dict(cycle) for cycle in result.cycles],
    }


def generate_online_markdown_report(result: OnlinePlanningResult) -> str:
    """Generate a concise experiment report for online replanning."""
    lines = [
        "# Observation-Driven Replanning Report",
        "",
        "## Scenario",
        "",
        f"- Name: `{result.scenario_name}`",
        f"- Success: `{result.success}`",
        f"- Final goal reached: `{result.goal_reached}`",
        f"- Cycles: `{len(result.cycles)}`",
        f"- Replanning count: `{result.replanning_count}`",
        f"- Observation mismatch count: `{result.mismatch_count}`",
        f"- Setup time: `{result.setup_ms:.6f} ms`",
        f"- Total planning time: `{result.total_planning_ms:.6f} ms`",
        f"- Sum of cycle times: `{result.total_cycle_ms:.6f} ms`",
        f"- Experiment total time: `{result.experiment_total_ms:.6f} ms`",
        "",
        "## Selected Actions",
        "",
    ]
    selected_actions = [
        cycle.selected_action for cycle in result.cycles if cycle.selected_action
    ]
    if selected_actions:
        for index, action_name in enumerate(selected_actions, start=1):
            lines.append(f"{index}. `{action_name}`")
    else:
        lines.append("No action was selected.")

    lines.extend(
        [
            "",
            "## Cycle Timing",
            "",
            "| Cycle | Observation | Goal type | Selected action | Chosen search states | "
            "All search states | "
            "Load (ms) | Merge (ms) | Grounding (ms) | Planning (ms) | "
            "Verification (ms) | Selection (ms) | State update (ms) | "
            "Expected action (s) | "
            "Cycle total (ms) |",
            "| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | "
            "---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for cycle in result.cycles:
        lines.append(
            "| "
            + " | ".join(
                [
                    str(cycle.cycle),
                    cycle.observation_id,
                    cycle.goal_type,
                    _escape_markdown_cell(cycle.selected_action or "-"),
                    str(cycle.visited_states),
                    str(cycle.total_visited_states),
                    f"{cycle.timing.observation_load_ms:.6f}",
                    f"{cycle.timing.state_merge_ms:.6f}",
                    f"{cycle.timing.action_grounding_ms:.6f}",
                    f"{cycle.timing.planning_ms:.6f}",
                    f"{cycle.timing.verification_ms:.6f}",
                    f"{cycle.timing.action_selection_ms:.6f}",
                    f"{cycle.timing.state_update_ms:.6f}",
                    (
                        f"{cycle.expected_action_time_s:.3f}"
                        if cycle.expected_action_time_s is not None
                        else "-"
                    ),
                    f"{cycle.timing.cycle_total_ms:.6f}",
                ]
            )
            + " |"
        )

    lines.extend(["", "## Prediction and Observation Differences", ""])
    mismatch_lines = []
    for cycle in result.cycles:
        for mismatch in cycle.mismatches:
            mismatch_lines.append(
                f"- Cycle {cycle.cycle}, `{mismatch.path}`: expected "
                f"`{mismatch.expected}`, observed `{mismatch.observed}`."
            )
    lines.extend(mismatch_lines or ["No prediction/observation mismatch was detected."])

    lines.extend(["", "## Final State", "", *_format_mapping(result.final_state)])
    if result.failure_reason:
        lines.extend(["", "## Failure Reason", "", result.failure_reason])
    return "\n".join(lines).strip() + "\n"


def _online_cycle_to_dict(cycle) -> Dict[str, Any]:
    return {
        "cycle": cycle.cycle,
        "observation_id": cycle.observation_id,
        "observation_source": cycle.observation_source,
        "mismatches": [
            {
                "path": mismatch.path,
                "expected": mismatch.expected,
                "observed": mismatch.observed,
            }
            for mismatch in cycle.mismatches
        ],
        "goal_type": cycle.goal_type,
        "planning_goal": cycle.planning_goal,
        "planning_attempts": cycle.planning_attempts,
        "planning_success": cycle.planning_success,
        "visited_states": cycle.visited_states,
        "total_visited_states": cycle.total_visited_states,
        "generated_plan": cycle.generated_plan,
        "verification_valid": cycle.verification_valid,
        "verification_reason": cycle.verification_reason,
        "selected_action": cycle.selected_action,
        "selected_action_template": cycle.selected_action_template,
        "expected_action_time_s": cycle.expected_action_time_s,
        "state_after_observation": cycle.state_after_observation,
        "expected_state_after_action": cycle.expected_state_after_action,
        "timing": cycle.timing.to_dict(),
        "failure_reason": cycle.failure_reason,
    }


def _escape_markdown_cell(value: str) -> str:
    return value.replace("|", "\\|")
