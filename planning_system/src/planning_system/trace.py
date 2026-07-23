"""Step-by-step execution trace helpers for generated plans."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List

from .planner import PlanningAction
from .state import State


@dataclass
class TraceStep:
    """State transition produced by one action in a plan."""

    step: int
    action_name: str
    state_before: State
    state_after: State
    changed_fields: Dict[str, Dict[str, Any]]


def build_plan_trace(
    initial_state: State,
    plan: List[PlanningAction],
) -> List[TraceStep]:
    """Build a state-change trace for a plan without mutating the input state."""
    current_state = dict(initial_state)
    trace: List[TraceStep] = []

    for step_number, action in enumerate(plan, start=1):
        failed = action.failed_reasons(current_state)
        if failed:
            reason = "; ".join(failed)
            raise ValueError(
                f"Action {action.name!r} is not applicable at step {step_number}: {reason}"
            )

        state_before = dict(current_state)
        state_after = action.apply(current_state)
        trace.append(
            TraceStep(
                step=step_number,
                action_name=action.name,
                state_before=state_before,
                state_after=dict(state_after),
                changed_fields=_changed_fields(state_before, state_after),
            )
        )
        current_state = state_after

    return trace


def _changed_fields(state_before: State, state_after: State) -> Dict[str, Dict[str, Any]]:
    changed: Dict[str, Dict[str, Any]] = {}
    _collect_changes(state_before, state_after, "", changed)
    return changed


def _collect_changes(
    before: Any,
    after: Any,
    prefix: str,
    changed: Dict[str, Dict[str, Any]],
) -> None:
    if isinstance(before, dict) and isinstance(after, dict):
        for key in sorted(set(before) | set(after)):
            path = f"{prefix}.{key}" if prefix else key
            _collect_changes(before.get(key), after.get(key), path, changed)
        return
    if before != after:
        changed[prefix] = {"before": before, "after": after}
