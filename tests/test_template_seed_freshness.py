from __future__ import annotations

import hashlib
import unittest

import yaml

from release_test_support import REPO, TEMPLATE


CURRENT_SOURCE_ID = "2026-07-13-llm-wiki-system-instructions"
CURRENT_REFERENCE = f"/references/{CURRENT_SOURCE_ID}.md"
HISTORICAL_SOURCE_ID = "2026-07-09-llm-wiki-system-instructions"


def frontmatter(path):
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        return None
    _, source, _body = text.split("---", 2)
    return yaml.safe_load(source)


class TemplateSeedFreshnessTests(unittest.TestCase):
    def test_current_system_instructions_are_the_active_seed_source(self) -> None:
        canonical = (REPO / "llm-wiki-system-instructions.md").read_bytes()
        expected_hash = hashlib.sha256(canonical).hexdigest()
        raw = TEMPLATE / "sources" / "raw" / f"{CURRENT_SOURCE_ID}.md"

        self.assertEqual(raw.read_bytes(), canonical)

        registry = yaml.safe_load(
            (TEMPLATE / "sources" / "_source_registry.yml").read_text(encoding="utf-8")
        )
        by_id = {entry["source_id"]: entry for entry in registry["sources"]}
        self.assertEqual(by_id[CURRENT_SOURCE_ID]["status"], "active")
        self.assertEqual(by_id[CURRENT_SOURCE_ID]["hash_sha256"], expected_hash)
        self.assertEqual(by_id[HISTORICAL_SOURCE_ID]["status"], "superseded")

        reference = TEMPLATE / "wiki" / "references" / f"{CURRENT_SOURCE_ID}.md"
        metadata = frontmatter(reference)
        self.assertEqual(metadata["hash_sha256"], expected_hash)
        self.assertEqual(metadata["resource"], f"sources/raw/{CURRENT_SOURCE_ID}.md")
        reference_text = reference.read_text(encoding="utf-8")
        self.assertIn("Human-driven", reference_text)
        self.assertIn("Agent-driven", reference_text)
        self.assertIn("high-consequence", reference_text.lower())

        readme = (TEMPLATE / "README.md").read_text(encoding="utf-8")
        self.assertIn(f"wiki/references/{CURRENT_SOURCE_ID}.md", readme)
        self.assertIn("clearly marked as superseded", readme)

    def test_seed_pages_cite_the_current_instructions_without_deleting_history(self) -> None:
        old_raw = TEMPLATE / "sources" / "raw" / f"{HISTORICAL_SOURCE_ID}.md"
        old_reference = TEMPLATE / "wiki" / "references" / f"{HISTORICAL_SOURCE_ID}.md"
        self.assertTrue(old_raw.is_file())
        self.assertTrue(old_reference.is_file())
        self.assertEqual(frontmatter(TEMPLATE / "wiki" / "index.md")["profile"], "llm-wiki-profile/0.2")

        excluded = {old_reference.name, f"{CURRENT_SOURCE_ID}.md"}
        checked = []
        for path in sorted((TEMPLATE / "wiki").rglob("*.md")):
            metadata = frontmatter(path)
            if metadata is None or "sources" not in metadata or path.name in excluded:
                continue
            checked.append(path.relative_to(TEMPLATE).as_posix())
            self.assertIn(CURRENT_REFERENCE, metadata["sources"], path)
            self.assertEqual(metadata["profile"], "llm-wiki-profile/0.2", path)
            self.assertIn(metadata["review_state"], {"pending", "reviewed"}, path)
            self.assertEqual(metadata["review_priority"], "normal", path)
            self.assertEqual(metadata["consequence_tier"], "ordinary", path)
        self.assertGreaterEqual(len(checked), 20)


if __name__ == "__main__":
    unittest.main()
