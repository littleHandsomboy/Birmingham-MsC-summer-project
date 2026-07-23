"""Planner interface for the rule-based disassembly prototype."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Any, Deque, Dict, List, Optional, Protocol, Tuple

from .state import Goal, State, make_hashable_state, state_satisfies_goal


class PlanningAction(Protocol):
    """Behaviour required by the planner, verifier, and trace builder."""

    name: str
    description: str
    effects: Dict[str, Any]

    def failed_reasons(self, state: State) -> List[str]:
        ...

    def apply(self, state: State) -> State:
        ...


@dataclass
class PlanningResult:
    """Result returned by a planner."""

    success: bool
    plan: list[PlanningAction] = field(default_factory=list)
    final_state: Optional[State] = None
    failure_reasons: list[str] = field(default_factory=list)
    visited_states: int = 0


def plan_disassembly(
    initial_state: State,
    goal: Goal,
    actions: list[PlanningAction],
    max_iterations: int = 1000,
) -> PlanningResult:
    """Find a valid action sequence with breadth-first forward search."""
    start_state = dict(initial_state)

    if state_satisfies_goal(start_state, goal):
        return PlanningResult(
            success=True,
            plan=[],
            final_state=start_state,
            visited_states=1,
        )

    queue: Deque[Tuple[State, List[PlanningAction]]] = deque([(start_state, [])])
    visited = {make_hashable_state(start_state)}
    rejected_reasons: set[str] = set()
    blocking_tool_reasons: set[str] = set()
    iterations = 0

    while queue:
        if iterations >= max_iterations:
            return PlanningResult(
                success=False,
                final_state=None,
                failure_reasons=[
                    f"Maximum iterations reached: {max_iterations}.",
                    *_prioritized_reasons(blocking_tool_reasons, rejected_reasons),
                ],
                visited_states=len(visited),
            )

        current_state, current_plan = queue.popleft()
        iterations += 1

        for action in actions:
            failed = action.failed_reasons(current_state)
            if failed:
                if all(reason.startswith("Required tool missing:") for reason in failed):
                    for reason in failed:
                        blocking_tool_reasons.add(f"{action.name}: {reason}")
                for reason in failed:
                    rejected_reasons.add(f"{action.name}: {reason}")
                continue

            new_state = action.apply(current_state)
            new_key = make_hashable_state(new_state)
            if new_key in visited:
                continue

            new_plan = current_plan + [action]
            if state_satisfies_goal(new_state, goal):
                return PlanningResult(
                    success=True,
                    plan=new_plan,
                    final_state=new_state,
                    visited_states=len(visited) + 1,
                )

            visited.add(new_key)
            queue.append((new_state, new_plan))

    return PlanningResult(
        success=False,
        final_state=None,
        failure_reasons=[
            "No valid plan found.",
            *_prioritized_reasons(blocking_tool_reasons, rejected_reasons),
            "Goal cannot be reached from the current action library and initial state.",
        ],
        visited_states=len(visited),
    )


def plan(
    initial_state: State,
    goal: Goal,
    actions: list[PlanningAction],
) -> PlanningResult:
    """Backward-compatible wrapper for early skeleton code."""
    return plan_disassembly(initial_state, goal, actions)


def _prioritized_reasons(
    blocking_tool_reasons: set[str],
    rejected_reasons: set[str],
    limit: int = 20,
) -> list[str]:
    prioritized = list(sorted(blocking_tool_reasons))
    for reason in sorted(rejected_reasons):
        if reason not in blocking_tool_reasons:
            prioritized.append(reason)
    return prioritized[:limit]
