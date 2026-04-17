import json
import unittest
from pathlib import Path

from app.services.comparison_engine import ComparisonEngine
from app.services.compensation_engine import CompensationEngine
from app.services.config_loader import load_client_bundle
from app.services.contract_parser import ContractParser
from app.services.scope_normalizer import ScopeNormalizer


class CompensationEngineTest(unittest.TestCase):
    def test_build_compensation_from_demo_events(self) -> None:
        contract, comparison_result = self._load_demo_comparison()

        result = CompensationEngine().build(contract, comparison_result.creep_events)

        self.assertEqual(result.enforcement_mode, "recommend")
        self.assertEqual(result.compensation_type, "invoice_line_item")
        self.assertEqual(len(result.draft_invoice_line_items), 3)
        self.assertIsNone(result.draft_change_order_summary)
        self.assertIn("action_to_take", result.internal_approval_note)
        self.assertIn("action_to_take", result.client_facing_summary)
        self.assertEqual(
            result.internal_approval_note["recommended_action"],
            "These items are recommended for inclusion in the upcoming invoice.",
        )
        self.assertEqual(
            result.client_facing_summary["requested_action"],
            "These items are recommended for inclusion in the upcoming invoice.",
        )
        self.assertIn("Flag for review if needed", result.internal_approval_note["action_to_take"])
        self.assertIn("Flag for review if needed", result.client_facing_summary["action_to_take"])
        self.assertIn("Internal Draft", result.human_readable_draft)
        self.assertIn("Client Draft", result.human_readable_draft)

    def test_enforcement_modes_adjust_compensation_language(self) -> None:
        contract, comparison_result = self._load_demo_comparison()
        engine = CompensationEngine()

        suggest_result = engine.build(contract, comparison_result.creep_events, enforcement_mode="suggest")
        enforce_result = engine.build(contract, comparison_result.creep_events, enforcement_mode="enforce")

        self.assertEqual(suggest_result.enforcement_mode, "suggest")
        self.assertEqual(enforce_result.enforcement_mode, "enforce")
        self.assertIn("optional review", suggest_result.internal_approval_note["recommended_action"])
        self.assertIn("future invoice", suggest_result.client_facing_summary["requested_action"])
        self.assertIn("automatic inclusion", enforce_result.internal_approval_note["action_to_take"])
        self.assertIn("included automatically", enforce_result.client_facing_summary["action_to_take"])

    def _load_demo_comparison(self):
        client_dir = Path("configs/client/demo-client")
        bundle = load_client_bundle(client_dir)
        normalizer = ScopeNormalizer(bundle.client, bundle.contract_rules, bundle.field_mapping)
        raw_contract = ContractParser().parse_raw_file(client_dir / "structured_sow.md")
        raw_work_log = json.loads((client_dir / "structured_work_log.json").read_text(encoding="utf-8"))
        contract = normalizer.normalize_contract(raw_contract)
        work_items = normalizer.normalize_work_log(raw_work_log)
        comparison_result = ComparisonEngine().compare(contract, work_items)
        return contract, comparison_result


if __name__ == "__main__":
    unittest.main()
