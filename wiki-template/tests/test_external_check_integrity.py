from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from run_lib import RunError  # noqa: E402
from wiki_run import finish_session, parse_checks, start_session, terminate_session  # noqa: E402
from wiki_test_support import add_authority, make_git_wiki  # noqa: E402


class ExternalCheckIntegrityTests(unittest.TestCase):
    def make_manual(self, parent: Path) -> tuple[Path, dict[str, object]]:
        root = make_git_wiki(parent)
        add_authority(
            root,
            "manual-editor",
            mode="manual-assist",
            lane="semantic",
            action="edit-wiki-pages",
            writable_paths=[
                "wiki/concepts/**",
                "reports/runs/**",
                "reports/latest.json",
            ],
            page_types=["Concept"],
        )
        return root, start_session(root, "semantic", "manual-assist", "manual-editor")

    def test_duplicate_check_cannot_mask_an_earlier_failure(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root, envelope = self.make_manual(Path(temporary))
            with self.assertRaisesRegex(RunError, "duplicate check ID"):
                finish_session(
                    root,
                    str(envelope["run_id"]),
                    str(envelope["run_token"]),
                    ["quick-lint=fail", "quick-lint=pass"],
                )
            record = json.loads(
                (root / ".wiki_state" / "runs" / f"{envelope['run_id']}.json").read_text(encoding="utf-8")
            )
            self.assertEqual(record["state"], "running")
            self.assertIsNone(record["result"])
            self.assertIsNone(record["finished_at"])
            terminate_session(
                root, str(envelope["run_id"]), str(envelope["run_token"]), "failed", "test cleanup"
            )

    def test_check_parser_rejects_malformed_empty_duplicate_and_excessive_inputs(self) -> None:
        invalid = [
            ["quick-lint"],
            ["=pass"],
            ["UPPER=pass"],
            ["quick-lint=unknown"],
            ["quick-lint=pass", "quick-lint=pass"],
            [f"check-{index}=pass" for index in range(65)],
        ]
        for values in invalid:
            with self.subTest(values=values):
                with self.assertRaises(RunError):
                    parse_checks(values)

    def test_external_checks_cannot_impersonate_controller_checks(self) -> None:
        for check_id in ["semantic-output", "provenance", "proposal-payload", "approval-binding"]:
            with self.subTest(check_id=check_id):
                with self.assertRaisesRegex(RunError, "controller-owned check"):
                    parse_checks([f"{check_id}=pass"])

    def test_external_attestations_are_labelled_in_the_run_record(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root, envelope = self.make_manual(Path(temporary))
            code, record = finish_session(
                root,
                str(envelope["run_id"]),
                str(envelope["run_token"]),
                ["quick-lint=pass"],
            )
            self.assertEqual(code, 0)
            self.assertEqual(record["checks"][0]["provenance"], "external-attestation")

    def test_a_failed_attestation_prevents_closure(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root, envelope = self.make_manual(Path(temporary))
            with self.assertRaisesRegex(RunError, "validation failure"):
                finish_session(
                    root,
                    str(envelope["run_id"]),
                    str(envelope["run_token"]),
                    ["quick-lint=pass", "agent-review=fail"],
                )
            self.assertTrue((root / ".wiki_state" / "mutation.lock").exists())
            terminate_session(
                root, str(envelope["run_id"]), str(envelope["run_token"]), "failed", "test cleanup"
            )

    def test_external_agent_cannot_impersonate_a_controller_run_record(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root, envelope = self.make_manual(Path(temporary))
            fake = root / "reports" / "runs" / "20260101T000000Z-aaaaaaaaaaaa.json"
            fake.write_text("{}\n", encoding="utf-8")
            with self.assertRaisesRegex(RunError, "lane contract.*prohibits changed paths"):
                finish_session(
                    root,
                    str(envelope["run_id"]),
                    str(envelope["run_token"]),
                    ["quick-lint=pass"],
                )
            terminate_session(
                root, str(envelope["run_id"]), str(envelope["run_token"]), "failed", "test cleanup"
            )


if __name__ == "__main__":
    unittest.main()
