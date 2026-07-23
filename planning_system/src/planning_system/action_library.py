"""Load and validate reusable action templates from JSON."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Union

from .action_template import ActionTemplate


def load_action_templates(path: Union[str, Path]) -> List[ActionTemplate]:
    """Load a JSON action-template library with basic schema validation."""
    with Path(path).open("r", encoding="utf-8") as file:
        payload = json.load(file)
    if not isinstance(payload, dict) or not isinstance(payload.get("actions"), list):
        raise ValueError("Action library must be an object containing an 'actions' list.")

    templates = [_template_from_dict(item) for item in payload["actions"]]
    names = [template.name for template in templates]
    if len(names) != len(set(names)):
        raise ValueError("Action template names must be unique.")
    return templates


def _template_from_dict(values: Any) -> ActionTemplate:
    if not isinstance(values, dict):
        raise ValueError("Each action template must be a JSON object.")
    required = {"name", "description", "parameters", "preconditions", "effects"}
    missing = sorted(required - set(values))
    if missing:
        raise ValueError(f"Action template is missing fields: {', '.join(missing)}.")
    if not isinstance(values["parameters"], dict):
        raise ValueError("Action template parameters must be an object.")
    if not isinstance(values["preconditions"], list):
        raise ValueError("Action template preconditions must be a list.")
    if not isinstance(values["effects"], list):
        raise ValueError("Action template effects must be a list.")

    for parameter_name, selector in values["parameters"].items():
        if not isinstance(selector, dict) or "source" not in selector:
            raise ValueError(
                f"Parameter {parameter_name!r} must define an entity source."
            )

    return ActionTemplate(
        name=str(values["name"]),
        description=str(values["description"]),
        parameters=values["parameters"],
        preconditions=values["preconditions"],
        effects=values["effects"],
        tool_requirement=values.get("tool_requirement"),
        cost=float(values.get("cost", 1.0)),
        risk=float(values.get("risk", 0.0)),
        expected_time=values.get("expected_time"),
    )
