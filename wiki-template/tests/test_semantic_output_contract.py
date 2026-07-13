from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from run_lib import ContractError  # noqa: E402
from semantic_protocol import validate_semantic_output  # noqa: E402
from fake_agent_harness import proposal, semantic_output


class SemanticOutputContractTests(unittest.TestCase):
    def test_attribution_sources_uncertainty_and_checks_are_required(self) -> None:
        proposed = proposal("proposal-run")
        output = semantic_output("apply-run", proposed)
        validate_semantic_output(output, "apply-run", proposed, ROOT)
        output["agent"] = {"agent_label": "other", "runtime_label": "unknown"}
        with self.assertRaisesRegex(ContractError, "attribution"):
            validate_semantic_output(output, "apply-run", proposed, ROOT)


if __name__ == "__main__":
    unittest.main()
