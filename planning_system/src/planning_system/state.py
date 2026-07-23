"""State helpers for symbolic disassembly planning."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any, Dict, Iterable, Tuple, Union

State = Dict[str, Any]
Goal = Dict[str, Any]


def validate_structured_state(state: State) -> None:
    """Validate the entity-based state schema used by generic action templates."""
    required_sections = ("assembly", "components", "connections", "tools", "robot")
    missing = [section for section in required_sections if section not in state]
    if missing:
        raise ValueError(
            "Structured state is missing sections: " + ", ".join(missing) + "."
        )

    for section in ("assembly", "components", "connections", "tools", "robot"):
        if not isinstance(state[section], dict):
            raise ValueError(f"Structured state section {section!r} must be an object.")

    components = state["components"]
    for component_id, component in components.items():
        if not isinstance(component, dict):
            raise ValueError(f"Component {component_id!r} must be an object.")
        if "type" not in component or "status" not in component:
            raise ValueError(
                f"Component {component_id!r} must define type and status."
            )
        for blocker in component.get("blocked_by", []):
            if blocker not in components:
                raise ValueError(
                    f"Component {component_id!r} references unknown blocker {blocker!r}."
                )

    for connection_id, connection in state["connections"].items():
        if not isinstance(connection, dict):
            raise ValueError(f"Connection {connection_id!r} must be an object.")
        if "type" not in connection or "status" not in connection:
            raise ValueError(
                f"Connection {connection_id!r} must define type and status."
            )
        connected_components = connection.get("connects")
        if not isinstance(connected_components, list) or not connected_components:
            raise ValueError(
                f"Connection {connection_id!r} must define a non-empty connects list."
            )
        for component_id in connected_components:
            if component_id not in components:
                raise ValueError(
                    f"Connection {connection_id!r} references unknown component "
                    f"{component_id!r}."
                )
        for blocker in connection.get("blocked_by", []):
            if blocker not in components:
                raise ValueError(
                    f"Connection {connection_id!r} references unknown blocker {blocker!r}."
                )

    tools = state["tools"]
    for tool_id, tool in tools.items():
        if not isinstance(tool, dict):
            raise ValueError(f"Tool {tool_id!r} must be an object.")
        if not isinstance(tool.get("capabilities"), list):
            raise ValueError(f"Tool {tool_id!r} must define a capabilities list.")
        if not isinstance(tool.get("available"), bool):
            raise ValueError(f"Tool {tool_id!r} must define boolean availability.")

    mounted_tool = state["robot"].get("mounted_tool")
    if mounted_tool is not None and mounted_tool not in tools:
        raise ValueError(f"Robot references unknown mounted tool {mounted_tool!r}.")


def load_state_from_json(path: Union[str, Path]) -> State:
    """Load a state dictionary from a JSON file."""
    with Path(path).open("r", encoding="utf-8") as file:
        data = json.load(file)
    if not isinstance(data, dict):
        raise ValueError("Expected a JSON object at the top level.")
    return data


def state_satisfies_goal(state: State, goal: Goal) -> bool:
    """Return True when the goal is a matching subset of the current state."""
    return _mapping_contains(state, goal)


def get_nested_value(values: Dict[str, Any], path: str) -> Any:
    """Read a dot-separated path from a nested dictionary."""
    current: Any = values
    for part in path.split("."):
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    return current


def set_nested_value(values: State, path: str, value: Any) -> State:
    """Return a deep-copied state with one dot-separated path updated."""
    updated = copy.deepcopy(values)
    current: Dict[str, Any] = updated
    parts = path.split(".")
    for part in parts[:-1]:
        child = current.get(part)
        if not isinstance(child, dict):
            child = {}
            current[part] = child
        current = child
    current[parts[-1]] = value
    return updated


def make_hashable_state(state: State) -> Tuple[Tuple[str, Any], ...]:
    """Create a hashable representation of a symbolic state."""
    return tuple(sorted((key, _freeze(value)) for key, value in state.items()))


def _freeze(value: Any) -> Any:
    if isinstance(value, dict):
        return tuple(sorted((key, _freeze(item)) for key, item in value.items()))
    if isinstance(value, list):
        return tuple(sorted(_freeze(item) for item in value))
    if isinstance(value, set):
        return tuple(sorted(_freeze(item) for item in value))
    return value


def missing_goal_fields(state: State, goal: Goal) -> Iterable[str]:
    """Yield goal fields that are not currently satisfied."""
    yield from _missing_goal_paths(state, goal)


def _mapping_contains(actual: Any, expected: Any) -> bool:
    if isinstance(expected, dict):
        if not isinstance(actual, dict):
            return False
        return all(
            key in actual and _mapping_contains(actual[key], value)
            for key, value in expected.items()
        )
    return actual == expected


def _missing_goal_paths(actual: Any, expected: Any, prefix: str = "") -> Iterable[str]:
    if not isinstance(expected, dict):
        if actual != expected:
            yield prefix
        return

    actual_mapping = actual if isinstance(actual, dict) else {}
    for key, value in expected.items():
        path = f"{prefix}.{key}" if prefix else key
        if key not in actual_mapping:
            yield path
        else:
            yield from _missing_goal_paths(actual_mapping[key], value, path)


# Backward-compatible aliases used by early skeleton modules.
load_json = load_state_from_json
goal_satisfied = state_satisfies_goal
state_key = make_hashable_state
