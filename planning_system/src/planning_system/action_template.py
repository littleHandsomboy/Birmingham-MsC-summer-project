"""Data models for reusable action templates and grounded actions."""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .state import State, get_nested_value, set_nested_value


RETAINING_CONNECTION_TYPES = {
    "threaded_fastener",
    "clip",
    "adhesive_joint",
    "retaining_ring",
    "rivet",
    "welded_joint",
    "permanent_joint",
}


@dataclass(frozen=True)
class ActionTemplate:
    """Reusable action rule whose parameters are bound to state entities."""

    name: str
    description: str
    parameters: Dict[str, Dict[str, Any]]
    preconditions: List[Dict[str, Any]]
    effects: List[Dict[str, Any]]
    tool_requirement: Optional[Dict[str, Any]] = None
    cost: float = 1.0
    risk: float = 0.0
    expected_time: Any = None


@dataclass(frozen=True)
class GroundedAction:
    """Concrete action produced by binding a template to state entities."""

    template: ActionTemplate
    bindings: Dict[str, str]
    expected_time: Optional[float] = None
    name: str = field(init=False)
    description: str = field(init=False)
    cost: float = field(init=False)
    risk: float = field(init=False)

    def __post_init__(self) -> None:
        arguments = ",".join(
            f"{parameter}={entity_id}"
            for parameter, entity_id in self.bindings.items()
        )
        object.__setattr__(self, "name", f"{self.template.name}[{arguments}]")
        try:
            description = self.template.description.format(**self.bindings)
        except (KeyError, ValueError):
            description = self.template.description
        object.__setattr__(self, "description", description)
        object.__setattr__(self, "cost", self.template.cost)
        object.__setattr__(self, "risk", self.template.risk)

    @property
    def effects(self) -> Dict[str, Any]:
        """Expose explicit set effects as paths for reports and verification."""
        resolved: Dict[str, Any] = {}
        for effect in self.template.effects:
            if effect.get("operation") not in {"set", "set_binding"}:
                continue
            path = self._subject_path(effect)
            if path is None:
                continue
            resolved[path] = self._resolve_value(effect.get("value"), {})
        return resolved

    def is_applicable(self, state: State) -> bool:
        return not self.failed_reasons(state)

    def failed_reasons(self, state: State) -> List[str]:
        reasons: List[str] = []
        for condition in self.template.preconditions:
            reason = self._condition_failure(condition, state)
            if reason:
                reasons.append(reason)
        tool_reason = self._tool_requirement_failure(state)
        if tool_reason:
            reasons.append(tool_reason)
        return reasons

    def apply(self, state: State) -> State:
        """Apply explicit effects and derived accessibility to a copied state."""
        updated = copy.deepcopy(state)
        for effect in self.template.effects:
            operation = effect.get("operation")
            if operation in {"set", "set_binding"}:
                path = self._subject_path(effect)
                if path is None:
                    raise ValueError(f"Effect in {self.name} has no resolvable subject.")
                value = self._resolve_value(effect.get("value"), updated)
                updated = set_nested_value(updated, path, value)
            elif operation == "recalculate_accessibility":
                updated = recalculate_accessibility(updated)
            else:
                raise ValueError(
                    f"Unsupported effect operation {operation!r} in {self.name}."
                )
        return updated

    def effect_failures(self, state_before: State, state_after: State) -> List[str]:
        """Check that applying the action produces the supplied resulting state."""
        expected_state = self.apply(state_before)
        if expected_state == state_after:
            return []
        return [f"Effects for {self.name} did not produce the expected state."]

    def _condition_failure(
        self, condition: Dict[str, Any], state: State
    ) -> Optional[str]:
        operator = condition.get("operator")
        subject_path = self._subject_path(condition)

        if operator == "has_no_installed_retaining_connections":
            parameter = _binding_name(condition.get("subject"))
            component_id = self.bindings.get(parameter or "")
            if component_id is None:
                return "Retaining-connection check has no bound component."
            blockers = installed_retaining_connections(state, component_id)
            if blockers:
                return (
                    f"Component {component_id} is still retained by: "
                    + ", ".join(blockers)
                    + "."
                )
            return None

        if subject_path is None:
            return f"Condition in {self.name} has no resolvable subject."

        actual = get_nested_value(state, subject_path)
        expected = self._resolve_value(condition.get("value"), state)
        if operator in {"equals", "equals_binding"}:
            if actual != expected:
                return (
                    f"Precondition failed: {subject_path} expected {expected!r} "
                    f"but found {actual!r}."
                )
            return None
        if operator == "not_equals":
            if actual == expected:
                return (
                    f"Precondition failed: {subject_path} must not equal "
                    f"{expected!r}."
                )
            return None
        if operator == "contains":
            if not isinstance(actual, list) or expected not in actual:
                return f"Precondition failed: {subject_path} does not contain {expected!r}."
            return None
        return f"Unsupported precondition operator {operator!r} in {self.name}."

    def _tool_requirement_failure(self, state: State) -> Optional[str]:
        requirement = self.template.tool_requirement
        tool_id = self.bindings.get("tool")
        if requirement is None:
            return None
        if tool_id is None:
            return f"Action {self.name} requires a bound tool."

        tool = state.get("tools", {}).get(tool_id)
        if not isinstance(tool, dict):
            return f"Required tool missing: {tool_id}."
        if not tool.get("available", False):
            return f"Required tool unavailable: {tool_id}."

        capability = requirement.get("capability")
        if capability not in tool.get("capabilities", []):
            return f"Tool {tool_id} lacks required capability {capability!r}."

        for rule in requirement.get("compatibility", []):
            required_value = self._resolve_reference(
                rule.get("must_contain_from"), state
            )
            supported_values = tool.get(rule.get("tool_field"), [])
            if required_value not in supported_values:
                return (
                    f"Tool {tool_id} is incompatible: {rule.get('tool_field')} "
                    f"does not support {required_value!r}."
                )
        return None

    def _subject_path(self, rule: Dict[str, Any]) -> Optional[str]:
        subject = rule.get("subject")
        field_name = rule.get("field")
        if subject == "$robot":
            base = "robot"
        else:
            parameter = _binding_name(subject)
            if parameter is None or parameter not in self.bindings:
                return None
            source = self.template.parameters[parameter]["source"]
            base = f"{source}.{self.bindings[parameter]}"
        return f"{base}.{field_name}" if field_name else base

    def _resolve_value(self, value: Any, state: State) -> Any:
        if isinstance(value, str) and value.startswith("$"):
            if "." in value:
                return self._resolve_reference(value, state)
            return self.bindings.get(value[1:], value)
        return value

    def _resolve_reference(self, reference: Any, state: State) -> Any:
        if not isinstance(reference, str) or not reference.startswith("$"):
            return reference
        parameter_and_field = reference[1:].split(".", 1)
        parameter = parameter_and_field[0]
        entity_id = self.bindings.get(parameter)
        if entity_id is None:
            return None
        source = self.template.parameters[parameter]["source"]
        path = f"{source}.{entity_id}"
        if len(parameter_and_field) == 2:
            path += f".{parameter_and_field[1]}"
        return get_nested_value(state, path)


def installed_retaining_connections(state: State, component_id: str) -> List[str]:
    """Return installed retaining connections attached to a component."""
    blockers: List[str] = []
    for connection_id, connection in state.get("connections", {}).items():
        if not isinstance(connection, dict):
            continue
        retaining = connection.get("retaining") is True or connection.get("type") in RETAINING_CONNECTION_TYPES
        if (
            retaining
            and component_id in connection.get("connects", [])
            and connection.get("status") == "installed"
        ):
            blockers.append(connection_id)
    return blockers


def recalculate_accessibility(state: State) -> State:
    """Update accessibility fields from explicit blocked_by relationships."""
    updated = copy.deepcopy(state)
    components = updated.get("components", {})

    for entity_group in (components, updated.get("connections", {})):
        for entity in entity_group.values():
            if not isinstance(entity, dict) or "blocked_by" not in entity:
                continue
            if entity.get("status") != "installed":
                entity["accessible"] = False
                continue
            blockers = entity.get("blocked_by", [])
            entity["accessible"] = all(
                components.get(blocker, {}).get("status") in {"removed", "collected"}
                for blocker in blockers
            )
    return updated


def _binding_name(subject: Any) -> Optional[str]:
    if isinstance(subject, str) and subject.startswith("$"):
        return subject[1:].split(".", 1)[0]
    return None
