"""Plan verification skeleton."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from .planner import PlanningAction
from .state import Goal, State, state_satisfies_goal


@dataclass
class VerificationResult:
    """Validation result for a generated plan."""

    valid: bool
    goal_reached: bool
    final_state: State = field(default_factory=dict)
    failed_step: Optional[int] = None
    action_name: Optional[str] = None
    reason: Optional[str] = None
    messages: list[str] = field(default_factory=list)


def verify_plan(
    initial_state: State,
    goal: Goal,
    plan: list[PlanningAction],
) -> VerificationResult:
    """Check action applicability and final goal satisfaction."""
    state = dict(initial_state)
    for step_index, action in enumerate(plan, start=1):
        failed = action.failed_reasons(state)
        if failed:
            reason = "; ".join(failed)
            return VerificationResult(
                valid=False,
                goal_reached=False,
                final_state=state,
                failed_step=step_index,
                action_name=action.name,
                reason=reason,
                messages=[reason],
            )

        previous_state = dict(state)
        state = action.apply(state)
        effect_failures = getattr(action, "effect_failures", None)
        if callable(effect_failures):
            failed_effects = effect_failures(previous_state, state)
        else:
            failed_effects = [
                (
                    f"Effect failed: {key} expected {expected!r} "
                    f"after {action.name} but found {state.get(key)!r}."
                )
                for key, expected in action.effects.items()
                if state.get(key) != expected
            ]

        if failed_effects:
            reason = "; ".join(failed_effects)
            return VerificationResult(
                valid=False,
                goal_reached=False,
                final_state=previous_state,
                failed_step=step_index,
                action_name=action.name,
                reason=reason,
                messages=failed_effects,
            )

    reached = state_satisfies_goal(state, goal)
    if not reached:
        reason = "Plan executed but goal not reached."
        return VerificationResult(
            valid=False,
            goal_reached=False,
            final_state=state,
            reason=reason,
            messages=[reason],
        )

    return VerificationResult(
        valid=True,
        goal_reached=True,
        final_state=state,
        messages=["All action preconditions satisfied.", "Goal reached."],
    )
