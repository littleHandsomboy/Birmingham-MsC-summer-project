"""Instantiate reusable action templates for entities in a state."""

from __future__ import annotations

import itertools
from typing import Any, Dict, Iterable, List, Tuple

from .action_template import ActionTemplate, GroundedAction
from .state import State


def ground_action_templates(
    state: State, templates: Iterable[ActionTemplate]
) -> List[GroundedAction]:
    """Create deterministic concrete actions from templates and state entities."""
    grounded: List[GroundedAction] = []
    for template in templates:
        parameter_names = list(template.parameters)
        candidate_groups = [
            _candidate_entities(state, template.parameters[name])
            for name in parameter_names
        ]
        if any(not candidates for candidates in candidate_groups):
            continue

        for candidate_tuple in itertools.product(*candidate_groups):
            bindings = dict(zip(parameter_names, candidate_tuple))
            action = GroundedAction(
                template=template,
                bindings=bindings,
                expected_time=_expected_time(template.expected_time, bindings, state),
            )
            if _binding_is_compatible(action, state):
                grounded.append(action)
    return grounded


def _candidate_entities(state: State, selector: Dict[str, Any]) -> List[str]:
    source = selector["source"]
    entities = state.get(source, {})
    if not isinstance(entities, dict):
        return []

    allowed_types = selector.get("type_in")
    if allowed_types is None and "type" in selector:
        allowed_types = [selector["type"]]

    candidates = []
    for entity_id, entity in sorted(entities.items()):
        if not isinstance(entity, dict):
            continue
        if allowed_types is not None and entity.get("type") not in allowed_types:
            continue
        if any(
            entity.get(field_name) != expected
            for field_name, expected in selector.get("where", {}).items()
        ):
            continue
        candidates.append(entity_id)
    return candidates


def _binding_is_compatible(action: GroundedAction, state: State) -> bool:
    reason = action._tool_requirement_failure(state)
    return reason is None


def _expected_time(specification: Any, bindings: Dict[str, str], state: State) -> Any:
    if specification is None or isinstance(specification, (int, float)):
        return float(specification) if specification is not None else None
    if not isinstance(specification, dict):
        raise ValueError(f"Unsupported expected_time specification: {specification!r}.")

    total = float(specification.get("base_seconds", 0.0))
    reference = specification.get("quantity_from")
    if reference:
        quantity = _resolve_reference(reference, bindings, state)
        total += float(specification.get("per_item_seconds", 0.0)) * float(quantity)
    return total


def _resolve_reference(reference: str, bindings: Dict[str, str], state: State) -> Any:
    parameter, field_name = reference[1:].split(".", 1)
    entity_id = bindings[parameter]
    for source in ("components", "connections", "tools"):
        entity = state.get(source, {}).get(entity_id)
        if isinstance(entity, dict):
            return entity.get(field_name)
    raise ValueError(f"Could not resolve expected-time reference {reference!r}.")
