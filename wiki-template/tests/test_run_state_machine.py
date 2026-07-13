from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from run_lib import RunError, require_transition  # noqa: E402


class RunStateMachineTests(unittest.TestCase):
    def test_forward_transitions_are_explicit(self) -> None:
        for current, target in [
            ("created", "locked"),
            ("locked", "preflight"),
            ("preflight", "running"),
            ("running", "validating"),
            ("validating", "completed"),
        ]:
            require_transition(current, target)

    def test_repeated_regressive_and_terminal_transitions_fail(self) -> None:
        for current, target in [
            ("running", "running"),
            ("validating", "running"),
            ("completed", "running"),
            ("failed", "completed"),
        ]:
            with self.assertRaises(RunError):
                require_transition(current, target)


if __name__ == "__main__":
    unittest.main()
