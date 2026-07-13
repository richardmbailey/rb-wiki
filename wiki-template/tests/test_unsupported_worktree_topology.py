from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from wiki_test_support import latest_record, make_git_wiki, run, run_controller


class UnsupportedWorktreeTopologyTests(unittest.TestCase):
    def test_additional_worktree_blocks_scheduled_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            parent = Path(temporary)
            root = make_git_wiki(parent)
            second = parent / "second-worktree"
            run(["git", "worktree", "add", "-q", "-b", "test-second", str(second)], root)
            completed = run_controller(root)
            self.assertEqual(completed.returncode, 2)
            record = latest_record(root)
            self.assertEqual(record["state"], "blocked")
            self.assertIn("multiple Git worktrees", record["error"])
            self.assertFalse((root / ".wiki_state" / "mutation.lock").exists())


if __name__ == "__main__":
    unittest.main()

