from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from wiki_test_support import make_git_wiki, run  # noqa: E402


class GraphCacheIntegrityTests(unittest.TestCase):
    def test_stale_malformed_and_old_cache_are_rebuilt_or_bypassed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = make_git_wiki(Path(temporary))
            cache = root / ".wiki_cache" / "graph.json"
            original = json.loads(cache.read_text(encoding="utf-8"))
            second = run([sys.executable, "tools/build_graph.py"], root)
            self.assertIn("reused current", second.stdout)
            page = root / "wiki" / "concepts" / "frontmatter.md"
            page.write_text(page.read_text(encoding="utf-8") + "\nchanged\n", encoding="utf-8")
            stale_query = run(
                [sys.executable, "tools/query.py", "graph", "neighbors", "/concepts/frontmatter.md"],
                root,
                check=False,
            )
            self.assertEqual(stale_query.returncode, 0, stale_query.stdout + stale_query.stderr)
            self.assertEqual(json.loads(cache.read_text(encoding="utf-8")), original)
            rebuilt = run([sys.executable, "tools/build_graph.py"], root)
            self.assertIn("wrote", rebuilt.stdout)
            cache.write_text("{bad json", encoding="utf-8")
            malformed = run(
                [sys.executable, "tools/query.py", "graph", "neighbors", "/concepts/frontmatter.md"], root,
                check=False,
            )
            self.assertEqual(malformed.returncode, 0)
            cache.write_text(json.dumps({"schema_version": "old"}), encoding="utf-8")
            old = run([sys.executable, "tools/build_graph.py"], root, check=False)
            self.assertEqual(old.returncode, 0)

    def test_symlinked_cache_is_not_read(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            parent = Path(temporary)
            root = make_git_wiki(parent)
            cache = root / ".wiki_cache" / "graph.json"
            outside = parent / "outside.json"
            outside.write_text('{"marker":"SECRET"}', encoding="utf-8")
            cache.unlink()
            cache.symlink_to(outside)
            query = run(
                [sys.executable, "tools/query.py", "graph", "neighbors", "/concepts/frontmatter.md"], root,
                check=False,
            )
            self.assertEqual(query.returncode, 0)
            self.assertNotIn("SECRET", query.stdout + query.stderr)

    def test_add_rename_and_delete_each_invalidate_the_source_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = make_git_wiki(Path(temporary))
            cache = root / ".wiki_cache" / "graph.json"
            added = root / "wiki" / "concepts" / "cache-added.md"
            added.write_text("# Cache addition\n", encoding="utf-8")
            run([sys.executable, "tools/build_graph.py"], root)
            self.assertIn("/concepts/cache-added.md", json.loads(cache.read_text())["nodes"])
            renamed = added.with_name("cache-renamed.md")
            added.rename(renamed)
            run([sys.executable, "tools/build_graph.py"], root)
            nodes = json.loads(cache.read_text())["nodes"]
            self.assertNotIn("/concepts/cache-added.md", nodes)
            self.assertIn("/concepts/cache-renamed.md", nodes)
            renamed.unlink()
            run([sys.executable, "tools/build_graph.py"], root)
            self.assertNotIn("/concepts/cache-renamed.md", json.loads(cache.read_text())["nodes"])

    def test_interrupted_prepublication_temporary_file_never_replaces_current_cache(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = make_git_wiki(Path(temporary))
            cache = root / ".wiki_cache" / "graph.json"
            before = cache.read_bytes()
            interrupted = cache.with_name(".graph.json.interrupted.tmp")
            interrupted.write_text('{"schema_version":"corrupt"}', encoding="utf-8")
            query = run(
                [sys.executable, "tools/query.py", "graph", "neighbors", "/concepts/frontmatter.md"], root
            )
            self.assertEqual(query.returncode, 0)
            self.assertEqual(cache.read_bytes(), before)

    def test_source_digest_never_reads_a_symlinked_markdown_target(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            parent = Path(temporary)
            root = make_git_wiki(parent)
            outside = parent / "outside.md"
            outside.write_text("SECRET-GRAPH-MARKER", encoding="utf-8")
            (root / "wiki" / "outside-link.md").symlink_to(outside)
            query = run(
                [sys.executable, "tools/query.py", "graph", "neighbors", "/concepts/frontmatter.md"],
                root,
                check=False,
            )
            self.assertEqual(query.returncode, 0)
            self.assertNotIn("SECRET-GRAPH-MARKER", query.stdout + query.stderr)
            rebuilt = run([sys.executable, "tools/build_graph.py"], root, check=False)
            self.assertEqual(rebuilt.returncode, 0)
            self.assertNotIn("SECRET-GRAPH-MARKER", rebuilt.stdout + rebuilt.stderr)


if __name__ == "__main__":
    unittest.main()
