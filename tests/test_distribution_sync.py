from __future__ import annotations

import sys
import unittest

from release_test_support import REPO, run


class DistributionSyncTests(unittest.TestCase):
    def test_deliberate_design_copy_is_in_sync(self) -> None:
        completed = run([sys.executable, "scripts/sync_distributed.py", "--check"], REPO)
        self.assertIn("PASS", completed.stdout)

    def test_template_is_declared_runtime_canonical_source(self) -> None:
        ownership = (REPO / "docs" / "CANONICAL_OWNERSHIP.md").read_text(encoding="utf-8")
        self.assertIn("`wiki-template/` is the canonical source", ownership)


if __name__ == "__main__":
    unittest.main()
