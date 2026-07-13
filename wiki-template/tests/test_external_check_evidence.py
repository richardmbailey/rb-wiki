from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from run_lib import ContractError  # noqa: E402
from wiki_run import finish_session, parse_checks, start_session  # noqa: E402
from wiki_test_support import add_authority, make_git_wiki, run  # noqa: E402


class ExternalCheckEvidenceTests(unittest.TestCase):
    def test_local_bounded_evidence_is_referenced_without_embedding_content(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            evidence = root / "reports" / "checks" / "review.json"
            evidence.parent.mkdir(parents=True)
            evidence.write_text('{"outcome":"pass"}\n', encoding="utf-8")
            checks = parse_checks(["agent-review=pass@reports/checks/review.json"], root)
            self.assertEqual(checks[0]["evidence_ref"], "reports/checks/review.json")
            self.assertNotIn("outcome", str(checks[0]))

    def test_remote_escaped_missing_symlinked_oversized_and_secret_like_references_fail(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "reports").mkdir()
            outside = root / "outside.json"
            outside.write_text("{}", encoding="utf-8")
            (root / "reports" / "linked.json").symlink_to(outside)
            oversized = root / "reports" / "large.json"
            oversized.write_bytes(b"x" * (1024 * 1024 + 1))
            invalid = [
                "agent-review=pass@https://example.invalid/evidence",
                "agent-review=pass@reports/../outside.json",
                "agent-review=pass@reports/missing.json",
                "agent-review=pass@reports/linked.json",
                "agent-review=pass@reports/large.json",
                "agent-review=pass@reports/api_key.json",
                "agent-review=pass@",
            ]
            for value in invalid:
                with self.subTest(value=value), self.assertRaises(ContractError):
                    parse_checks([value], root)

    def test_reference_syntax_is_bounded_even_without_a_root(self) -> None:
        with self.assertRaises(ContractError):
            parse_checks(["agent-review=pass@reports/" + "a" * 233])

    def test_evidence_reference_survives_validated_session_persistence(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = make_git_wiki(Path(temporary))
            add_authority(
                root, "manual-editor", mode="manual-assist", lane="semantic",
                action="edit-wiki-pages",
                writable_paths=["wiki/concepts/**", "reports/runs/**", "reports/latest.json"],
                page_types=["Concept"],
            )
            evidence = root / "reports" / "checks" / "review.json"
            evidence.parent.mkdir()
            evidence.write_text('{"outcome":"pass"}\n', encoding="utf-8")
            run(["git", "add", "reports/checks/review.json"], root)
            run(["git", "commit", "-q", "-m", "add external review evidence"], root)
            envelope = start_session(root, "semantic", "manual-assist", "manual-editor")
            code, record = finish_session(
                root, envelope["run_id"], envelope["run_token"],
                ["quick-lint=pass", "agent-review=pass@reports/checks/review.json"],
            )
            self.assertEqual(code, 0)
            evidence_check = next(item for item in record["checks"] if item["check_id"] == "agent-review")
            self.assertEqual(evidence_check["evidence_ref"], "reports/checks/review.json")
            persisted = json.loads(
                (root / ".wiki_state" / "runs" / f"{record['run_id']}.json").read_text()
            )
            self.assertEqual(persisted["checks"], record["checks"])


if __name__ == "__main__":
    unittest.main()
