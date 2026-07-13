from __future__ import annotations

import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from lane_runtime import load_lane_contracts, validate_lane_changes, validate_lane_contracts  # noqa: E402
from run_lib import ContractError, RunError  # noqa: E402


class LaneContractTests(unittest.TestCase):
    def test_complete_lane_set_is_versioned_and_valid(self) -> None:
        contracts = validate_lane_contracts(ROOT)
        self.assertEqual(len(contracts), 6)
        self.assertTrue(all(item["schema_version"] == "rb-wiki-lane-contract/0.2" for item in contracts))
        self.assertTrue(
            all(
                set(item["allowed_modes"])
                == set(item["actions_by_mode"])
                == set(item["closure_profile_by_mode"])
                == set(item["produces_by_mode"])
                == set(item["required_checks_by_mode"])
                for item in contracts
            )
        )

    def test_synthesis_actions_are_explicit_per_mode(self) -> None:
        contracts = {item["lane_id"]: item for item in validate_lane_contracts(ROOT)}
        self.assertEqual(
            contracts["synthesize"]["actions_by_mode"],
            {
                "manual-assist": "edit-wiki-pages",
                "scheduled-propose": "propose-synthesis",
                "authorised-autonomous-apply": "edit-wiki-pages",
            },
        )

    def test_every_non_substantive_mode_rejects_an_ordinary_page_change(self) -> None:
        for _path, contract in load_lane_contracts(ROOT):
            for mode in contract["allowed_modes"]:
                if mode in contract["substantive_wiki_edit_modes"]:
                    continue
                with self.subTest(lane=contract["controller_lane"], mode=mode):
                    with self.assertRaisesRegex(RunError, "forbids substantive wiki edits"):
                        validate_lane_changes(contract, mode, ["wiki/concepts/forbidden.md"])

    def test_invalid_lane_contract_sets_fail_closed(self) -> None:
        cases = ("missing", "malformed", "unknown-field", "incompatible-version", "duplicate-controller")
        for case in cases:
            with self.subTest(case=case), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary) / "wiki"
                shutil.copytree(ROOT, root, ignore=shutil.ignore_patterns(".git", ".wiki_state"))
                acquire = root / "schema" / "lanes" / "acquire.yml"
                if case == "missing":
                    acquire.unlink()
                elif case == "malformed":
                    acquire.write_text("schema_version: [\n", encoding="utf-8")
                elif case == "unknown-field":
                    acquire.write_text(acquire.read_text(encoding="utf-8") + "unknown: true\n", encoding="utf-8")
                elif case == "incompatible-version":
                    acquire.write_text(
                        acquire.read_text(encoding="utf-8").replace(
                            "rb-wiki-lane-contract/0.2", "rb-wiki-lane-contract/9.9"
                        ),
                        encoding="utf-8",
                    )
                else:
                    acquire.write_text(
                        acquire.read_text(encoding="utf-8").replace(
                            "controller_lane: acquire", "controller_lane: maintain"
                        ),
                        encoding="utf-8",
                    )
                with self.assertRaises(ContractError):
                    load_lane_contracts(root)

    def test_symlinked_lane_contract_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "wiki"
            shutil.copytree(ROOT, root, ignore=shutil.ignore_patterns(".git", ".wiki_state"))
            lane = root / "schema" / "lanes" / "acquire.yml"
            target = Path(temporary) / "outside.yml"
            target.write_text(lane.read_text(encoding="utf-8"), encoding="utf-8")
            lane.unlink()
            lane.symlink_to(target)
            with self.assertRaisesRegex(ContractError, "symlink"):
                load_lane_contracts(root)


if __name__ == "__main__":
    unittest.main()
