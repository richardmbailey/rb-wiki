from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

from release_test_support import TEMPLATE
from test_new_wiki_v02 import create

sys.path.insert(0, str(TEMPLATE / "tools"))
sys.path.insert(0, str(TEMPLATE / "tests"))

from wiki_test_support import add_authority, run


class FullV02WorkflowTests(unittest.TestCase):
    def test_fresh_setup_text_pdf_query_lint_provenance_and_doctor(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            parent = Path(temporary)
            create(parent)
            root = parent / "fresh-wiki"
            refused = run(
                [
                    sys.executable, "tools/wiki_run.py", "run", "--lane", "maintain",
                    "--mode", "scheduled-propose", "--authority", "disabled-example",
                ],
                root,
                check=False,
            )
            self.assertNotEqual(refused.returncode, 0)
            add_authority(
                root,
                "workflow-ingest",
                mode="scheduled-propose",
                lane="ingest",
                action="ingest-sources",
                input_roots=["inbox"],
                writable_paths=[
                    "sources/raw/**", "sources/derived/**", "sources/_source_registry.yml",
                    "wiki/references/**", "wiki/index.md", ".wiki_cache/graph.json",
                    "reports/ingest/**", "reports/runs/**", "reports/latest.json",
                ],
                page_types=["Reference"],
                commit_policy="scoped-auto",
            )
            (root / "inbox" / "workflow.txt").write_text("workflow evidence text\n", encoding="utf-8")
            (root / "inbox" / "workflow.pdf").write_bytes(b"%PDF-1.4\nintentionally incomplete workflow fixture\n")
            ingest = run(
                [sys.executable, "tools/wiki_cron.py", "inbox", "--authority", "workflow-ingest"],
                root,
                check=False,
            )
            self.assertEqual(ingest.returncode, 0, ingest.stdout + ingest.stderr)
            self.assertEqual(
                len([path for path in (root / "sources" / "raw").iterdir() if "workflow" in path.name]), 2
            )
            self.assertEqual(run([sys.executable, "tools/provenance.py", "validate"], root).returncode, 0)
            self.assertEqual(run([sys.executable, "tools/build_index.py"], root).returncode, 0)
            self.assertEqual(run([sys.executable, "tools/build_graph.py"], root).returncode, 0)
            search = run([sys.executable, "tools/query.py", "search", "workflow evidence"], root)
            self.assertIn("workflow", search.stdout.lower())
            self.assertEqual(run([sys.executable, "tools/lint.py", "--quick"], root).returncode, 0)
            self.assertEqual(run([sys.executable, "tools/lint.py", "--full"], root).returncode, 0)
            doctor = run([sys.executable, "tools/wiki_doctor.py", "--json"], root, check=False)
            self.assertIn(doctor.returncode, {0})
            self.assertIn('"schema_version":"rb-wiki-doctor-report/0.2"', doctor.stdout)


if __name__ == "__main__":
    unittest.main()
