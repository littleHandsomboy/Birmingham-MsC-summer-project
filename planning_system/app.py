"""Streamlit demo UI for the rule-based disassembly planner."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import streamlit as st

from planning_system.action_grounder import ground_action_templates
from planning_system.action_library import load_action_templates
from planning_system.online_planner import run_online_scenario
from planning_system.planner import PlanningResult, plan_disassembly
from planning_system.report import (
    generate_online_markdown_report,
    generate_markdown_report,
    generate_mermaid_flowchart,
    online_result_to_json_payload,
    planning_result_to_json_payload,
)
from planning_system.state import State, load_state_from_json, validate_structured_state
from planning_system.verifier import VerificationResult, verify_plan


PROJECT_ROOT = Path(__file__).resolve().parent
DATA_DIR = PROJECT_ROOT / "data"
GENERIC_LIBRARY_PATH = DATA_DIR / "generic_disassembly_action_library.json"
STREAM_SCENARIO_DIR = DATA_DIR / "stream_scenarios"


def main() -> None:
    st.set_page_config(page_title="Rule-Based Disassembly Planning Demo")
    st.title("Rule-Based Disassembly Planning Demo")

    mode = st.sidebar.radio(
        "Planning mode",
        ["Incremental replanning", "Complete-state planning"],
    )
    if mode == "Incremental replanning":
        _render_incremental_mode()
    else:
        _render_complete_state_mode()


def _render_complete_state_mode() -> None:
    st.subheader("Complete-State Planning")

    case_files = sorted(DATA_DIR.glob("case_*.json"))
    goal_files = sorted(DATA_DIR.glob("goal_*.json"))

    selected_case = st.sidebar.selectbox(
        "Case JSON file",
        case_files,
        format_func=lambda path: path.name,
    )

    initial_state = _load_json_for_display(selected_case, "case")
    default_goal_index = _default_goal_index(goal_files, initial_state)
    selected_goal = st.sidebar.selectbox(
        "Goal JSON file",
        goal_files,
        index=default_goal_index,
        key=f"goal_for_{selected_case.name}",
        format_func=lambda path: path.name,
    )
    run_planner = st.sidebar.button("Run Planner")

    goal = _load_json_for_display(selected_goal, "goal")
    recommended_goal = goal_files[default_goal_index] if goal_files else None
    if recommended_goal is not None and selected_goal != recommended_goal:
        st.sidebar.warning(
            f"Recommended goal for this case: {recommended_goal.name}"
        )

    st.subheader("Initial State JSON")
    st.json(initial_state)

    st.subheader("Goal JSON")
    st.json(goal)

    if not run_planner:
        st.info("Select input files and click Run Planner.")
        return

    actions = _actions_for_state(initial_state)
    planning_result = plan_disassembly(initial_state, goal, actions)
    verification_result = (
        verify_plan(initial_state, goal, planning_result.plan)
        if planning_result.success
        else None
    )

    _render_results(
        selected_case.stem,
        initial_state,
        goal,
        planning_result,
        verification_result,
    )


def _render_incremental_mode() -> None:
    st.subheader("Observation-Driven Incremental Replanning")
    scenario_files = sorted(STREAM_SCENARIO_DIR.glob("*.json"))
    selected_scenario = st.sidebar.selectbox(
        "Observation stream JSON",
        scenario_files,
        format_func=lambda path: path.stem,
    )
    run_scenario = st.sidebar.button("Run Incremental Scenario")

    scenario_metadata = _load_json_for_display(selected_scenario, "scenario")
    test_case = scenario_metadata.get("test_case", {})
    observation_stream = scenario_metadata.get("observation_stream", [])
    st.subheader("Test Case")
    st.write(f"**{test_case.get('title', selected_scenario.stem)}**")
    st.write(test_case.get("situation", "No situation description provided."))
    st.caption(
        f"Expected outcome: {test_case.get('expected_outcome', 'not specified')} | "
        f"Stream frames: {len(observation_stream)}"
    )

    st.subheader("Observation Stream")
    st.dataframe(
        [
            {
                "sequence": frame.get("sequence"),
                "observation": frame.get("observation_id"),
                "source": frame.get("source"),
                "updated sections": ", ".join(frame.get("updates", {}).keys()) or "none",
                "note": frame.get("note", ""),
            }
            for frame in observation_stream
        ],
        use_container_width=True,
    )
    with st.expander("View complete single-file JSON input"):
        st.json(scenario_metadata)

    if not run_scenario:
        st.info("Select a scenario and run the incremental planner.")
        return

    try:
        result = run_online_scenario(selected_scenario)
    except Exception as error:
        st.error(f"Could not run incremental scenario: {error}")
        return

    if result.success:
        st.success("Final goal reached.")
    else:
        st.error(result.failure_reason or "Incremental planning failed.")

    summary_columns = st.columns(4)
    summary_columns[0].metric("Cycles", len(result.cycles))
    summary_columns[1].metric("Replans", result.replanning_count)
    summary_columns[2].metric("Mismatches", result.mismatch_count)
    summary_columns[3].metric("Planning time", f"{result.total_planning_ms:.3f} ms")
    st.caption(
        f"Setup: {result.setup_ms:.3f} ms | "
        f"Complete experiment: {result.experiment_total_ms:.3f} ms"
    )

    st.subheader("Cycle Results")
    timing_rows = []
    notes_by_observation = {
        frame.get("observation_id"): frame.get("note", "")
        for frame in observation_stream
    }
    for cycle in result.cycles:
        timing_rows.append(
            {
                "stream frame": cycle.cycle,
                "observation": cycle.observation_id,
                "observation note": notes_by_observation.get(cycle.observation_id, ""),
                "goal type": cycle.goal_type,
                "selected action": cycle.selected_action or "-",
                "visited states": cycle.visited_states,
                "all search states": cycle.total_visited_states,
                "load ms": cycle.timing.observation_load_ms,
                "merge ms": cycle.timing.state_merge_ms,
                "grounding ms": cycle.timing.action_grounding_ms,
                "planning ms": cycle.timing.planning_ms,
                "verification ms": cycle.timing.verification_ms,
                "selection ms": cycle.timing.action_selection_ms,
                "state update ms": cycle.timing.state_update_ms,
                "cycle total ms": cycle.timing.cycle_total_ms,
            }
        )
    st.dataframe(timing_rows, use_container_width=True)

    st.subheader("Prediction and Observation Differences")
    mismatch_rows = [
        {
            "cycle": cycle.cycle,
            "field": mismatch.path,
            "expected": mismatch.expected,
            "observed": mismatch.observed,
        }
        for cycle in result.cycles
        for mismatch in cycle.mismatches
    ]
    if mismatch_rows:
        st.dataframe(mismatch_rows, use_container_width=True)
    else:
        st.write("No prediction/observation mismatch detected.")

    st.subheader("Final State")
    st.json(result.final_state)

    report = generate_online_markdown_report(result)
    payload = online_result_to_json_payload(result)
    st.download_button(
        "Download Incremental Markdown Report",
        data=report,
        file_name=f"{result.scenario_name}_report.md",
        mime="text/markdown",
    )
    st.download_button(
        "Download Incremental JSON Result",
        data=_json_dump(payload),
        file_name=f"{result.scenario_name}_result.json",
        mime="application/json",
    )


def _default_goal_index(goal_files: list[Path], initial_state: State) -> int:
    preferred_goal = _preferred_goal_name(initial_state)
    for index, path in enumerate(goal_files):
        if path.name == preferred_goal:
            return index
    return 0


def _preferred_goal_name(initial_state: State) -> str:
    return "goal_collect_generic_rotor.json"


def _actions_for_state(initial_state: State):
    validate_structured_state(initial_state)
    return ground_action_templates(
        initial_state,
        load_action_templates(GENERIC_LIBRARY_PATH),
    )


def _load_json_for_display(path: Path, label: str) -> State:
    try:
        return load_state_from_json(path)
    except Exception as error:  # Streamlit should show bad input without crashing.
        st.error(f"Could not load {label} JSON: {error}")
        st.stop()


def _render_results(
    case_name: str,
    initial_state: State,
    goal: State,
    planning_result: PlanningResult,
    verification_result: Optional[VerificationResult],
) -> None:
    st.subheader("Planning Status")
    if planning_result.success:
        st.success("Planning succeeded.")
    else:
        st.error("Planning failed.")

    st.write(f"Visited states: `{planning_result.visited_states}`")

    st.subheader("Generated Plan")
    if planning_result.plan:
        st.code(" -> ".join(action.name for action in planning_result.plan))
    else:
        st.warning("No valid plan generated.")

    st.subheader("Verification Result")
    if verification_result is None:
        st.warning("Verification skipped because no valid plan was generated.")
    elif verification_result.valid:
        st.success("Verification valid=True.")
    else:
        st.error("Verification failed.")
        if verification_result.reason:
            st.write(verification_result.reason)

    st.subheader("Final State")
    final_state = (
        verification_result.final_state
        if verification_result is not None
        else planning_result.final_state
    )
    st.json(final_state or {})

    st.subheader("Failure Reasons")
    if planning_result.failure_reasons:
        for reason in planning_result.failure_reasons:
            st.write(f"- {reason}")
    else:
        st.write("No failure reasons.")

    st.subheader("Markdown Report Preview")
    report = generate_markdown_report(
        case_name=case_name,
        initial_state=initial_state,
        goal=goal,
        planning_result=planning_result,
        verification_result=verification_result,
    )
    st.markdown(report)

    payload = planning_result_to_json_payload(
        case_name=case_name,
        initial_state=initial_state,
        goal=goal,
        planning_result=planning_result,
        verification_result=verification_result,
    )

    st.subheader("Step-by-Step Trace Table")
    trace_rows = [
        {
            "step": step["step"],
            "action": step["action_name"],
            "changed fields": ", ".join(step["changed_fields"].keys())
            or "none",
        }
        for step in payload["trace"]
    ]
    if trace_rows:
        st.table(trace_rows)
    else:
        st.warning("No trace available.")

    st.subheader("Changed Fields Table")
    changed_rows = []
    for step in payload["trace"]:
        for field_name, change in step["changed_fields"].items():
            changed_rows.append(
                {
                    "step": step["step"],
                    "action": step["action_name"],
                    "field": field_name,
                    "before": change["before"],
                    "after": change["after"],
                }
            )
    if changed_rows:
        st.table(changed_rows)
    else:
        st.write("No changed fields.")

    st.subheader("Mermaid Code Preview")
    st.code(generate_mermaid_flowchart(planning_result), language="mermaid")

    st.subheader("JSON Result Preview")
    st.json(payload)

    st.download_button(
        "Download Markdown Report",
        data=report,
        file_name=f"{case_name}_report.md",
        mime="text/markdown",
    )
    st.download_button(
        "Download JSON Result",
        data=_json_dump(payload),
        file_name=f"{case_name}_result.json",
        mime="application/json",
    )


def _json_dump(payload) -> str:
    return json.dumps(payload, indent=2)


if __name__ == "__main__":
    main()
