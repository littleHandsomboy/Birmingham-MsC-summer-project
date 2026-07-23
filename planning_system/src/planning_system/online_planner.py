"""Observation-driven one-action-per-cycle symbolic replanning."""

from __future__ import annotations

import copy
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from .action_grounder import ground_action_templates
from .action_library import load_action_templates
from .action_template import ActionTemplate, installed_retaining_connections
from .observation import (
    Observation,
    StateMismatch,
    find_observation_mismatches,
    merge_observation,
    observation_from_payload,
)
from .planner import PlanningResult, plan_disassembly
from .state import Goal, State, state_satisfies_goal, validate_structured_state
from .timing import CycleTiming, elapsed_ms, now_ns
from .verifier import verify_plan


REMOVABLE_COMPONENT_TYPES = {"cover", "plate", "guard", "housing_part"}
PULLABLE_COMPONENT_TYPES = {"bearing", "rotor", "shaft", "rotor_shaft_assembly"}
CONNECTION_GOAL_STATUS = {
    "threaded_fastener": "removed",
    "clip": "removed",
    "retaining_ring": "removed",
    "electrical_connector": "disconnected",
    "cable_connection": "disconnected",
    "adhesive_joint": "released",
    "rivet": "cut",
    "welded_joint": "cut",
    "permanent_joint": "cut",
}


@dataclass(frozen=True)
class OnlineScenario:
    """Validated inputs for one incremental planning experiment."""

    name: str
    initial_state: State
    goal: Goal
    action_library_path: Path
    observations: List[Observation]
    expected_success: bool


@dataclass
class OnlineCycleResult:
    """Outcome and timing of one observation/replanning cycle."""

    cycle: int
    observation_id: str
    observation_source: str
    mismatches: List[StateMismatch]
    goal_type: str
    planning_goal: Goal
    planning_attempts: int
    planning_success: bool
    visited_states: int
    total_visited_states: int
    generated_plan: List[str]
    verification_valid: Optional[bool]
    verification_reason: Optional[str]
    selected_action: Optional[str]
    selected_action_template: Optional[str]
    expected_action_time_s: Optional[float]
    state_after_observation: State
    expected_state_after_action: State
    timing: CycleTiming
    failure_reason: Optional[str] = None


@dataclass
class OnlinePlanningResult:
    """Complete result of an observation-driven planning experiment."""

    scenario_name: str
    success: bool
    goal_reached: bool
    initial_state: State
    goal: Goal
    final_state: State
    cycles: List[OnlineCycleResult] = field(default_factory=list)
    failure_reason: Optional[str] = None
    setup_ms: float = 0.0
    experiment_total_ms: float = 0.0

    @property
    def total_planning_ms(self) -> float:
        return sum(cycle.timing.planning_ms for cycle in self.cycles)

    @property
    def total_cycle_ms(self) -> float:
        return sum(cycle.timing.cycle_total_ms for cycle in self.cycles)

    @property
    def mismatch_count(self) -> int:
        return sum(len(cycle.mismatches) for cycle in self.cycles)

    @property
    def replanning_count(self) -> int:
        planning_cycles = sum(cycle.planning_attempts > 0 for cycle in self.cycles)
        return max(0, planning_cycles - 1)


@dataclass(frozen=True)
class _PlanningChoice:
    goal_type: str
    goal: Goal
    result: PlanningResult
    attempts: int
    total_visited_states: int


def load_online_scenario(path: Union[str, Path]) -> OnlineScenario:
    """Load one self-contained incremental observation-stream scenario."""
    scenario_path = Path(path)
    with scenario_path.open("r", encoding="utf-8") as file:
        payload = json.load(file)
    if not isinstance(payload, dict):
        raise ValueError("Online scenario must be a JSON object.")

    required = (
        "stream_schema_version",
        "name",
        "initial_state",
        "goal",
        "action_library",
    )
    missing = [field_name for field_name in required if field_name not in payload]
    if missing:
        raise ValueError("Online scenario is missing fields: " + ", ".join(missing) + ".")
    if str(payload["stream_schema_version"]) != "1.0":
        raise ValueError("Unsupported stream_schema_version; expected 1.0.")

    base = scenario_path.parent
    action_library_path = (base / payload["action_library"]).resolve()

    if "observation_stream" not in payload:
        raise ValueError(
            "Online scenario must contain an inline observation_stream array."
        )
    initial_state = _inline_mapping(payload["initial_state"], "initial_state")
    goal = _inline_mapping(payload["goal"], "goal")
    observations = _inline_observation_stream(payload["observation_stream"])

    return OnlineScenario(
        name=str(payload["name"]),
        initial_state=initial_state,
        goal=goal,
        action_library_path=action_library_path,
        observations=observations,
        expected_success=bool(payload.get("expected_success", True)),
    )


def _inline_mapping(value: Any, field_name: str) -> Dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(
            f"Single-file stream field {field_name} must be a JSON object."
        )
    return copy.deepcopy(value)


def _inline_observation_stream(value: Any) -> List[Observation]:
    if not isinstance(value, list) or not value:
        raise ValueError("observation_stream must be a non-empty JSON array.")

    observations: List[Observation] = []
    identifiers = set()
    for expected_sequence, frame in enumerate(value, start=1):
        if not isinstance(frame, dict):
            raise ValueError(
                f"Observation stream frame {expected_sequence} must be a JSON object."
            )
        if frame.get("sequence") != expected_sequence:
            raise ValueError(
                "Observation stream sequence values must be consecutive and start at 1; "
                f"expected {expected_sequence}."
            )
        observation = observation_from_payload(
            frame, context=f"Observation stream frame {expected_sequence}"
        )
        if observation.observation_id in identifiers:
            raise ValueError(
                f"Duplicate observation_id: {observation.observation_id}."
            )
        identifiers.add(observation.observation_id)
        observations.append(observation)
    return observations


def run_online_scenario(path: Union[str, Path]) -> OnlinePlanningResult:
    """Run one observation-driven scenario and execute one action per cycle."""
    experiment_start = now_ns()
    setup_start = now_ns()
    scenario = load_online_scenario(path)
    initial_state = copy.deepcopy(scenario.initial_state)
    goal = copy.deepcopy(scenario.goal)
    templates = load_action_templates(scenario.action_library_path)
    validate_structured_state(initial_state)
    setup_ms = elapsed_ms(setup_start)

    current_state = initial_state
    cycles: List[OnlineCycleResult] = []
    failure_reason: Optional[str] = None
    success = False

    for stream_index in range(len(scenario.observations)):
        cycle_number = stream_index + 1
        cycle_start = now_ns()
        timing = CycleTiming()

        load_start = now_ns()
        # The index is the stream cursor; exactly one frame is consumed per cycle.
        observation = scenario.observations[stream_index]
        timing.observation_load_ms = elapsed_ms(load_start)

        merge_start = now_ns()
        mismatches = find_observation_mismatches(current_state, observation)
        observed_state = merge_observation(current_state, observation)
        validate_structured_state(observed_state)
        timing.state_merge_ms = elapsed_ms(merge_start)

        if state_satisfies_goal(observed_state, goal):
            timing.cycle_total_ms = elapsed_ms(cycle_start)
            cycles.append(
                OnlineCycleResult(
                    cycle=cycle_number,
                    observation_id=observation.observation_id,
                    observation_source=observation.source,
                    mismatches=mismatches,
                    goal_type="final_observed",
                    planning_goal=goal,
                    planning_attempts=0,
                    planning_success=True,
                    visited_states=1,
                    total_visited_states=1,
                    generated_plan=[],
                    verification_valid=True,
                    verification_reason=None,
                    selected_action=None,
                    selected_action_template=None,
                    expected_action_time_s=None,
                    state_after_observation=observed_state,
                    expected_state_after_action=observed_state,
                    timing=timing,
                )
            )
            current_state = observed_state
            success = True
            break

        grounding_start = now_ns()
        actions = ground_action_templates(observed_state, templates)
        timing.action_grounding_ms = elapsed_ms(grounding_start)

        planning_start = now_ns()
        choice, planning_failure, planning_attempts, total_visited_states = _choose_plan(
            observed_state, goal, actions
        )
        timing.planning_ms = elapsed_ms(planning_start)

        if choice is None:
            failure_reason = planning_failure
            timing.cycle_total_ms = elapsed_ms(cycle_start)
            cycles.append(
                OnlineCycleResult(
                    cycle=cycle_number,
                    observation_id=observation.observation_id,
                    observation_source=observation.source,
                    mismatches=mismatches,
                    goal_type="none",
                    planning_goal={},
                    planning_attempts=planning_attempts,
                    planning_success=False,
                    visited_states=total_visited_states,
                    total_visited_states=total_visited_states,
                    generated_plan=[],
                    verification_valid=None,
                    verification_reason=None,
                    selected_action=None,
                    selected_action_template=None,
                    expected_action_time_s=None,
                    state_after_observation=observed_state,
                    expected_state_after_action=observed_state,
                    timing=timing,
                    failure_reason=failure_reason,
                )
            )
            current_state = observed_state
            break

        verification_start = now_ns()
        verification = verify_plan(observed_state, choice.goal, choice.result.plan)
        timing.verification_ms = elapsed_ms(verification_start)

        if not verification.valid or not choice.result.plan:
            failure_reason = verification.reason or "Planner returned no executable next action."
            timing.cycle_total_ms = elapsed_ms(cycle_start)
            cycles.append(
                _cycle_from_choice(
                    cycle_number,
                    observation.observation_id,
                    observation.source,
                    mismatches,
                    choice,
                    verification.valid,
                    verification.reason,
                    None,
                    observed_state,
                    observed_state,
                    timing,
                    failure_reason,
                )
            )
            current_state = observed_state
            break

        selection_start = now_ns()
        selected_action = choice.result.plan[0]
        timing.action_selection_ms = elapsed_ms(selection_start)

        state_update_start = now_ns()
        expected_state = selected_action.apply(observed_state)
        timing.state_update_ms = elapsed_ms(state_update_start)
        timing.cycle_total_ms = elapsed_ms(cycle_start)

        cycles.append(
            _cycle_from_choice(
                cycle_number,
                observation.observation_id,
                observation.source,
                mismatches,
                choice,
                verification.valid,
                verification.reason,
                selected_action,
                observed_state,
                expected_state,
                timing,
                None,
            )
        )
        current_state = expected_state

    if not success and failure_reason is None:
        failure_reason = (
            "Observation sequence exhausted before the final goal was confirmed "
            "by a subsequent observation."
        )

    return OnlinePlanningResult(
        scenario_name=scenario.name,
        success=success,
        goal_reached=state_satisfies_goal(current_state, goal),
        initial_state=initial_state,
        goal=goal,
        final_state=current_state,
        cycles=cycles,
        failure_reason=failure_reason,
        setup_ms=setup_ms,
        experiment_total_ms=elapsed_ms(experiment_start),
    )


def _choose_plan(
    state: State, final_goal: Goal, actions
) -> Tuple[Optional[_PlanningChoice], Optional[str], int, int]:
    attempts = 1
    final_result = plan_disassembly(state, final_goal, actions)
    total_visited_states = final_result.visited_states
    if final_result.success and final_result.plan:
        return (
            _PlanningChoice(
                "final", final_goal, final_result, attempts, total_visited_states
            ),
            None,
            attempts,
            total_visited_states,
        )

    for goal_type, frontier_goal in _frontier_goals(state):
        attempts += 1
        result = plan_disassembly(state, frontier_goal, actions)
        total_visited_states += result.visited_states
        if result.success and result.plan:
            return (
                _PlanningChoice(
                    goal_type,
                    frontier_goal,
                    result,
                    attempts,
                    total_visited_states,
                ),
                None,
                attempts,
                total_visited_states,
            )

    return (
        None,
        "No reachable final goal or frontier goal was found from the current "
        "observed state and available action library.",
        attempts,
        total_visited_states,
    )


def _frontier_goals(state: State):
    components = state.get("components", {})
    connections = state.get("connections", {})

    for component_id, component in sorted(components.items()):
        if (
            component.get("inspection_required") is True
            and component.get("inspected") is not True
            and component.get("accessible") is True
        ):
            yield (
                "frontier_inspection",
                {"components": {component_id: {"inspected": True}}},
            )

    for connection_id, connection in sorted(connections.items()):
        target_status = CONNECTION_GOAL_STATUS.get(connection.get("type"))
        if (
            target_status is not None
            and connection.get("status") == "installed"
            and connection.get("accessible") is True
        ):
            yield (
                "frontier_connection",
                {"connections": {connection_id: {"status": target_status}}},
            )

    for component_id, component in sorted(components.items()):
        if component.get("status") != "installed" or component.get("accessible") is not True:
            continue
        component_type = component.get("type")
        if component_type not in REMOVABLE_COMPONENT_TYPES | PULLABLE_COMPONENT_TYPES:
            continue
        if installed_retaining_connections(state, component_id):
            continue
        yield (
            "frontier_component",
            {"components": {component_id: {"status": "removed"}}},
        )


def _cycle_from_choice(
    cycle_number: int,
    observation_id: str,
    observation_source: str,
    mismatches: List[StateMismatch],
    choice: _PlanningChoice,
    verification_valid: Optional[bool],
    verification_reason: Optional[str],
    selected_action,
    observed_state: State,
    expected_state: State,
    timing: CycleTiming,
    failure_reason: Optional[str],
) -> OnlineCycleResult:
    return OnlineCycleResult(
        cycle=cycle_number,
        observation_id=observation_id,
        observation_source=observation_source,
        mismatches=mismatches,
        goal_type=choice.goal_type,
        planning_goal=choice.goal,
        planning_attempts=choice.attempts,
        planning_success=choice.result.success,
        visited_states=choice.result.visited_states,
        total_visited_states=choice.total_visited_states,
        generated_plan=[action.name for action in choice.result.plan],
        verification_valid=verification_valid,
        verification_reason=verification_reason,
        selected_action=selected_action.name if selected_action is not None else None,
        selected_action_template=(
            selected_action.template.name if selected_action is not None else None
        ),
        expected_action_time_s=(
            selected_action.expected_time if selected_action is not None else None
        ),
        state_after_observation=observed_state,
        expected_state_after_action=expected_state,
        timing=timing,
        failure_reason=failure_reason,
    )
