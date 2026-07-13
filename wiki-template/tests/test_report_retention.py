from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from wiki_test_support import make_git_wiki, run_controller


class ReportRetentionTests(unittest.TestCase):
    def test_noop_attempts_remain_ephemeral(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = make_git_wiki(Path(temporary))
            for _ in range(2):
                completed = run_controller(root)
                self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
            journals = list((root / ".wiki_state" / "runs").glob("*.json"))
            durable = list((root / "reports" / "runs").glob("*.json"))
            self.assertEqual(len(journals), 2)
            self.assertEqual(durable, [])
            self.assertFalse((root / "reports" / "latest.json").exists())


if __name__ == "__main__":
    unittest.main()
