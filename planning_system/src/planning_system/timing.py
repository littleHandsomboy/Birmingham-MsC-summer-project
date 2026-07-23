"""Timing data structures for observation-driven planning experiments."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Optional


def now_ns() -> int:
    """Return a monotonic high-resolution timestamp."""
    return time.perf_counter_ns()


def elapsed_ms(start_ns: int, end_ns: Optional[int] = None) -> float:
    """Convert an elapsed monotonic interval to milliseconds."""
    finish_ns = now_ns() if end_ns is None else end_ns
    return (finish_ns - start_ns) / 1_000_000.0


@dataclass
class CycleTiming:
    """Measured computation time for one observation/planning cycle."""

    observation_load_ms: float = 0.0
    state_merge_ms: float = 0.0
    action_grounding_ms: float = 0.0
    planning_ms: float = 0.0
    verification_ms: float = 0.0
    action_selection_ms: float = 0.0
    state_update_ms: float = 0.0
    cycle_total_ms: float = 0.0

    def to_dict(self) -> dict[str, float]:
        return {
            "observation_load_ms": self.observation_load_ms,
            "state_merge_ms": self.state_merge_ms,
            "action_grounding_ms": self.action_grounding_ms,
            "planning_ms": self.planning_ms,
            "verification_ms": self.verification_ms,
            "action_selection_ms": self.action_selection_ms,
            "state_update_ms": self.state_update_ms,
            "cycle_total_ms": self.cycle_total_ms,
        }
