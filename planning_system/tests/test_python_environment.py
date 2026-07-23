"""Import smoke test for the current generic planning package."""

import unittest

from planning_system.action_grounder import ground_action_templates
from planning_system.action_library import load_action_templates
from planning_system.action_template import ActionTemplate, GroundedAction
from planning_system.planner import plan_disassembly


class PythonEnvironmentTests(unittest.TestCase):
    def test_python_can_import_current_package(self) -> None:
        self.assertIsNotNone(ActionTemplate)
        self.assertIsNotNone(GroundedAction)
        self.assertTrue(callable(load_action_templates))
        self.assertTrue(callable(ground_action_templates))
        self.assertTrue(callable(plan_disassembly))


if __name__ == "__main__":
    unittest.main()
