from __future__ import annotations

import re
import sys
import unittest

import yaml

from release_test_support import REPO, TEMPLATE

sys.path.insert(0, str(TEMPLATE / "tools"))

from contracts import validate_contract  # noqa: E402
from lane_runtime import select_lane_contract, validate_lane_authority  # noqa: E402


class OperatingModeDocumentationTests(unittest.TestCase):
    def test_root_readme_explains_the_system_for_non_experts(self) -> None:
        root_readme = (REPO / "README.md").read_text(encoding="utf-8")

        for explanation in (
            "If you are not sure which model to choose, start with human-driven operation.",
            "An AI assistant is software such as Codex or Claude",
            "Git is the change history for the wiki",
            "An authority grant is a small permission file",
            "High-consequence work means work where a mistake could cause serious harm",
            "Use $rb-wiki-ingest to process this wiki's inbox while I supervise.",
        ):
            self.assertIn(explanation, root_readme)

        for unexplained_specialist_phrase in (
            "immutable evidence layer",
            "digest-bound",
            "transaction-journalled",
            "exact-payload semantic apply",
        ):
            self.assertNotIn(unexplained_specialist_phrase, root_readme)

    def test_template_readme_gives_new_users_a_plain_language_path(self) -> None:
        template_readme = (TEMPLATE / "README.md").read_text(encoding="utf-8")

        for explanation in (
            "If this folder has just been used to create a new wiki, read `SETUP.md` first.",
            "If you are not sure which to choose, use human-driven operation.",
            "The command above uses the built-in safety program",
            "A successful automatic check does not prove that every statement is true.",
            "Most users can stop here.",
        ):
            self.assertIn(explanation, template_readme)

        for unexplained_specialist_phrase in (
            "digest-keyed journals",
            "controller-owned ingest flow",
            "exact target content is hash-bound",
            "External `--check` values remain attestations",
        ):
            self.assertNotIn(unexplained_specialist_phrase, template_readme)

    def test_readmes_make_both_operating_models_explicit(self) -> None:
        root_readme = (REPO / "README.md").read_text(encoding="utf-8")
        template_readme = (TEMPLATE / "README.md").read_text(encoding="utf-8")
        for text in (root_readme, template_readme):
            self.assertIn("Human-driven", text)
            self.assertIn("Agent-driven", text)
            self.assertIn("manual-assist", text)
            self.assertIn("scheduled-propose", text)
            self.assertIn("authorised-autonomous-apply", text)
            self.assertIn("no active grant", text.lower())
            self.assertIn("never push", text.lower())

    def test_canonical_guides_explain_human_control_and_agent_authority(self) -> None:
        operations = (TEMPLATE / "docs" / "AGENT_OPERATIONS.md").read_text(encoding="utf-8")
        grants = (TEMPLATE / "docs" / "AUTHORITY_GRANTS.md").read_text(encoding="utf-8")
        self.assertIn("## Choose An Operating Model", operations)
        self.assertIn("### Direct human editing", operations)
        self.assertIn("## Create And Commit Authority", operations)
        self.assertIn("git show HEAD:schema/authorities/AUTHORITY_ID.yml", operations)
        self.assertIn("No authority grant permits `git push`", grants)
        self.assertIn("## Expiry And Revocation", grants)
        self.assertIn("Do not call `tools/ingest.py` directly", grants)

    def test_documented_grant_examples_match_current_contracts(self) -> None:
        guide = (TEMPLATE / "docs" / "AUTHORITY_GRANTS.md").read_text(encoding="utf-8")
        examples = re.findall(r"```yaml\n(.*?)```", guide, flags=re.DOTALL)
        self.assertEqual(len(examples), 5)
        for source in examples:
            grant = yaml.safe_load(source)
            validate_contract(grant, "authority-grant", TEMPLATE)
            self.assertFalse(grant["enabled"])
            self.assertEqual(len(grant["modes"]), 1)
            self.assertEqual(len(grant["lanes"]), 1)
            selected = select_lane_contract(TEMPLATE, grant["lanes"][0])
            validate_lane_authority(selected["contract"], grant, grant["modes"][0])


if __name__ == "__main__":
    unittest.main()
