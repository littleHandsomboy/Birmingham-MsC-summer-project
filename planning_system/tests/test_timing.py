"""Tests for timing data used by online experiments."""

from __future__ import annotations

import unittest

from planning_system.timing import CycleTiming, elapsed_ms, now_ns


class TimingTests(unittest.TestCase):
    def test_monotonic_elapsed_time_and_payload(self) -> None:
        start = now_ns()
        elapsed = elapsed_ms(start)
        timing = CycleTiming(planning_ms=elapsed, cycle_total_ms=elapsed)
        payload = timing.to_dict()

        self.assertGreaterEqual(elapsed, 0.0)
        self.assertIn("planning_ms", payload)
        self.assertIn("state_update_ms", payload)
        self.assertIn("cycle_total_ms", payload)
        self.assertGreaterEqual(payload["cycle_total_ms"], payload["planning_ms"])


if __name__ == "__main__":
    unittest.main()
