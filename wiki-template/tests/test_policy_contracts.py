from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from errors import ContractError  # noqa: E402
from authority import load_runtime_policy  # noqa: E402
from contracts import load_yaml_text  # noqa: E402


class PolicyContractTests(unittest.TestCase):
    def test_template_manifest_and_policy_validate(self) -> None:
        manifest, policy = load_runtime_policy(ROOT)
        self.assertEqual(manifest["schema_version"], "rb-wiki-manifest/0.2")
        self.assertIn("scheduled-propose", policy["permitted_modes"])

    def test_safe_loader_rejects_python_tags(self) -> None:
        with self.assertRaisesRegex(ContractError, "unsafe or invalid YAML"):
            load_yaml_text(
                "!!python/object/apply:os.system ['echo unsafe']\n",
                "wiki-manifest",
                "unsafe.yml",
                ROOT,
            )

    def test_contract_rejects_unknown_fields(self) -> None:
        text = (ROOT / "wiki-manifest.yml").read_text(encoding="utf-8") + "unknown_producer_field: true\n"
        with self.assertRaisesRegex(ContractError, "Additional properties"):
            load_yaml_text(text, "wiki-manifest", "manifest.yml", ROOT)

    def test_manifest_binds_the_operational_policy_identity(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            from wiki_test_support import make_git_wiki

            root = make_git_wiki(Path(temporary))
            policy = root / "schema" / "agent_policy.yml"
            policy.write_text(
                policy.read_text(encoding="utf-8").replace(
                    "policy_id: conservative-default", "policy_id: substituted-policy"
                ),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ContractError, "policy_id does not match requested identity"):
                load_runtime_policy(root)

    def test_authority_contract_rejects_parent_traversal(self) -> None:
        text = """schema_version: rb-wiki-authority-grant/0.2
authority_id: unsafe
enabled: true
owner: tests
issued_at: "2026-01-01T00:00:00Z"
expires_at: "2099-01-01T00:00:00Z"
revoked_at: null
modes: [scheduled-propose]
lanes: [maintain]
actions: [deterministic-maintenance]
input_roots: []
writable_paths: [../outside]
page_types: []
required_checks: [quick-lint]
consequence_tier: routine
budgets:
  max_runtime_seconds: 60
  max_changed_paths: 25
  max_acquired_sources: 0
commit_policy: forbidden
commit_identity: null
governance_maintenance: false
"""
        with self.assertRaises(ContractError):
            load_yaml_text(text, "authority-grant", "unsafe-authority.yml", ROOT)

    def test_yaml_size_is_bounded(self) -> None:
        with self.assertRaisesRegex(ContractError, "YAML limit"):
            load_yaml_text("x" * (1024 * 1024 + 1), "wiki-manifest", "large.yml", ROOT)

    def test_operational_yaml_symlink_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            outside = root / "outside.yml"
            outside.write_text((ROOT / "wiki-manifest.yml").read_text(encoding="utf-8"), encoding="utf-8")
            linked = root / "linked.yml"
            linked.symlink_to(outside)
            from contracts import load_yaml_contract

            with self.assertRaisesRegex(ContractError, "must not be a symlink"):
                load_yaml_contract(linked, "wiki-manifest", ROOT)


if __name__ == "__main__":
    unittest.main()
