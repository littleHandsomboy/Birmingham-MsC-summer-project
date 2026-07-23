"""Observation loading, state fusion, and prediction mismatch detection."""

from __future__ import annotations

import copy
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Union

from .state import State


@dataclass(frozen=True)
class Observation:
    """Partial symbolic state update produced by a simulated perception source."""

    observation_id: str
    source: str
    updates: Dict[str, Any]
    note: str = ""


@dataclass(frozen=True)
class StateMismatch:
    """Difference between a predicted field and a later observed value."""

    path: str
    expected: Any
    observed: Any


def load_observation(path: Union[str, Path]) -> Observation:
    """Load and validate one partial observation JSON file."""
    with Path(path).open("r", encoding="utf-8") as file:
        payload = json.load(file)
    return observation_from_payload(payload)


def observation_from_payload(
    payload: Any, context: str = "Observation"
) -> Observation:
    """Validate one inline observation frame from an observation stream."""
    if not isinstance(payload, dict):
        raise ValueError(f"{context} must be a JSON object.")

    required = ("observation_id", "source", "updates")
    missing = [field for field in required if field not in payload]
    if missing:
        raise ValueError(
            f"{context} is missing fields: " + ", ".join(missing) + "."
        )
    if not isinstance(payload["updates"], dict):
        raise ValueError(f"{context} updates must be a JSON object.")

    return Observation(
        observation_id=str(payload["observation_id"]),
        source=str(payload["source"]),
        updates=payload["updates"],
        note=str(payload.get("note", "")),
    )


def merge_observation(state: State, observation: Observation) -> State:
    """Merge a partial observation into a copied persistent state."""
    return _deep_merge(state, observation.updates)


def find_observation_mismatches(
    expected_state: State,
    observation: Observation,
) -> List[StateMismatch]:
    """Compare observed fields that already existed in the predicted state."""
    mismatches: List[StateMismatch] = []
    for path, observed in _leaf_values(observation.updates):
        exists, expected = _read_existing_path(expected_state, path)
        if exists and expected != observed:
            mismatches.append(
                StateMismatch(path=path, expected=expected, observed=observed)
            )
    return mismatches


def _deep_merge(base: Dict[str, Any], updates: Dict[str, Any]) -> Dict[str, Any]:
    merged = copy.deepcopy(base)
    for key, value in updates.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = copy.deepcopy(value)
    return merged


def _leaf_values(values: Dict[str, Any], prefix: str = ""):
    for key, value in values.items():
        path = f"{prefix}.{key}" if prefix else key
        if isinstance(value, dict):
            yield from _leaf_values(value, path)
        else:
            yield path, value


def _read_existing_path(values: Dict[str, Any], path: str):
    current: Any = values
    for part in path.split("."):
        if not isinstance(current, dict) or part not in current:
            return False, None
        current = current[part]
    return True, current
