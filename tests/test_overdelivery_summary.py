import unittest
from pathlib import Path

from app.workflows.run_single_client import run_single_client


class OverdeliverySummaryTest(unittest.TestCase):
    def test_demo_overdelivery_summary(self) -> None:
        result = run_single_client(Path("configs/client/demo-client"))
        summary = result["overdelivery_summary"]

        self.assertEqual(summary["overall_agreed_allowance"], 7.0)
        self.assertEqual(summary["overall_actual_delivered_amount"], 12.0)
        self.assertEqual(summary["overall_overdelivery_percent"], 71.4)

        by_category = {item["category"]: item for item in summary["category_insights"]}
        self.assertEqual(by_category["ad_creative"]["overdelivery_percent"], 50.0)
        self.assertEqual(by_category["revision"]["overdelivery_percent"], 100.0)
        self.assertEqual(by_category["landing_page"]["overdelivery_percent"], 100.0)
        self.assertIn("50.0% over-delivery on ad creative work", by_category["ad_creative"]["insight"])


if __name__ == "__main__":
    unittest.main()
