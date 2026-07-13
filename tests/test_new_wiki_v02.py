from __future__ import annotations

import sys
import shutil
import tempfile
import unittest
from pathlib import Path

import yaml

from release_test_support import NEW_WIKI, REPO, TEMPLATE, run


def create(parent: Path, *extra: str, check: bool = True, env=None):
    return run(
        [
            sys.executable,
            str(NEW_WIKI),
            "--template", str(TEMPLATE),
            "--parent", str(parent),
            "--name", "fresh-wiki",
            "--title", "Fresh Wiki",
            "--subject", "a neutral test subject",
            "--tag", "neutral-test",
            "--description", "Fresh Wiki is a local-first test knowledge base.",
            *extra,
        ],
        REPO,
        check=check,
        env=env,
    )


class NewWikiV02Tests(unittest.TestCase):
    def test_fresh_wiki_is_versioned_valid_and_has_no_active_grant(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            parent = Path(temporary)
            completed = create(parent)
            root = parent / "fresh-wiki"
            self.assertIn("PASS: created", completed.stdout)
            manifest = yaml.safe_load((root / "wiki-manifest.yml").read_text(encoding="utf-8"))
            self.assertEqual(manifest["profile_version"], "llm-wiki-profile/0.2")
            self.assertEqual(manifest["migration_version"], "rb-wiki-migrations/0.2")
            grants = list((root / "schema" / "authorities").glob("*.yml"))
            self.assertEqual([path.name for path in grants], ["disabled-example.yml"])
            self.assertIn("enabled: false", grants[0].read_text(encoding="utf-8"))
            self.assertTrue(list((root / "reports" / "lint").glob("*.json")))
            readme = (root / "README.md").read_text(encoding="utf-8")
            self.assertTrue(readme.startswith("# Fresh Wiki\n"))
            self.assertIn("Fresh Wiki is a local-first test knowledge base.", readme)
            self.assertNotIn("# Wiki Template", readme)
            self.assertIn("If you are not sure which to choose, use human-driven operation.", readme)
            index = (root / "wiki" / "index.md").read_text(encoding="utf-8")
            self.assertIn('profile: "llm-wiki-profile/0.2"', index)
            ordinary_pages = [
                path for path in (root / "wiki").rglob("*.md")
                if path.name not in {"index.md", "log.md"}
            ]
            self.assertEqual(len(ordinary_pages), 25)
            self.assertTrue(
                all("profile: llm-wiki-profile/0.2" in path.read_text(encoding="utf-8") for path in ordinary_pages)
            )
            setup = (root / "SETUP.md").read_text(encoding="utf-8")
            self.assertIn("**Human-driven:**", setup)
            self.assertIn("**Agent-driven:**", setup)
            self.assertIn("No active authority grant was created", setup)
            self.assertIn("docs/AUTHORITY_GRANTS.md", setup)
            self.assertIn("Base directory name: `fresh-wiki`", setup)
            self.assertNotIn(".fresh-wiki.rb-wiki-staging-", setup)
            top = run(["git", "rev-parse", "--show-toplevel"], root)
            self.assertEqual(Path(top.stdout.strip()).resolve(), root.resolve())
            self.assertEqual(run(["git", "status", "--porcelain"], root).stdout, "")

    def test_explicit_setup_creates_only_bounded_scheduled_authority(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            parent = Path(temporary)
            create(parent, "--enable-scheduled-propose", "--authority-owner", "test owner", "--authority-days", "7")
            path = parent / "fresh-wiki" / "schema" / "authorities" / "scheduled-maintainer.yml"
            text = path.read_text(encoding="utf-8")
            self.assertIn("enabled: true", text)
            self.assertIn("modes: [scheduled-propose]", text)
            self.assertNotIn("authorised-autonomous-apply", text)
            self.assertNotIn("edit-wiki-pages", text)
            setup = (parent / "fresh-wiki" / "SETUP.md").read_text(encoding="utf-8")
            self.assertIn("A bounded `scheduled-maintainer` grant was created", setup)
            self.assertIn("does not authorise ingest or autonomous page editing", setup)

    def test_setup_does_not_copy_template_git_or_runtime_state(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            parent = Path(temporary)
            template = parent / "template"
            shutil.copytree(TEMPLATE, template)
            (template / ".git").mkdir()
            (template / ".git" / "config").write_text("template history\n", encoding="utf-8")
            state = template / ".wiki_state" / "sessions"
            state.mkdir(parents=True)
            (state / "stale.json").write_text('{"run_token":"must-not-copy"}\n', encoding="utf-8")
            completed = run(
                [
                    sys.executable,
                    str(NEW_WIKI),
                    "--template", str(template),
                    "--parent", str(parent),
                    "--name", "isolated-wiki",
                    "--title", "Isolated Wiki",
                    "--subject", "a neutral subject",
                    "--tag", "neutral-subject",
                ],
                REPO,
                check=False,
            )
            self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
            root = parent / "isolated-wiki"
            self.assertTrue((root / ".git").is_dir())
            self.assertNotIn("template history", (root / ".git" / "config").read_text(encoding="utf-8"))
            self.assertFalse((root / ".wiki_state").exists())


if __name__ == "__main__":
    unittest.main()
