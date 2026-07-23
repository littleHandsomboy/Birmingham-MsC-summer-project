"""Shared helpers for the current structured planning system tests."""

from __future__ import annotations

from pathlib import Path

from planning_system.action_grounder import ground_action_templates
from planning_system.action_library import load_action_templates
from planning_system.state import State, load_state_from_json


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
CASE_PATH = DATA_DIR / "case_07_generic_motor_m3_m4.json"
GOAL_PATH = DATA_DIR / "goal_collect_generic_rotor.json"
LIBRARY_PATH = DATA_DIR / "generic_disassembly_action_library.json"


def load_case() -> State:
    return load_state_from_json(CASE_PATH)


def load_goal() -> State:
    return load_state_from_json(GOAL_PATH)


def load_actions(state: State):
    return ground_action_templates(state, load_action_templates(LIBRARY_PATH))
