import json
import unittest
from pathlib import Path

from app.models.work_item import WorkItem
from app.services.comparison_engine import ComparisonEngine
from app.services.contract_parser import ContractParser


class ComparisonEngineTest(unittest.TestCase):
    def test_compare_demo_work_log(self) -> None:
        contract = ContractParser().parse_file(
            Path("configs/clients/demo-client/contract.md")
        )
        payload = json.loads(
            Path("configs/clients/demo-client/work_log.json").read_text(encoding="utf-8")
        )
        work_items = [WorkItem(**item) for item in payload["work_items"]]

        result = ComparisonEngine().compare(contract, work_items)

        self.assertEqual(len(result.in_scope_items), 1)
        self.assertEqual(len(result.out_of_scope_items), 1)
        self.assertEqual(len(result.exceeded_limits), 1)
        self.assertEqual(len(result.creep_events), 2)
        self.assertEqual(result.out_of_scope_items[0].reason_code, "excluded_category")
        self.assertEqual(result.revenue_impact_estimate.estimated_amount, 725.0)


if __name__ == "__main__":
    unittest.main()
