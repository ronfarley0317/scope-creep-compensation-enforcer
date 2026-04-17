import json
import unittest
from pathlib import Path

from app.workflows.run_single_client import run_single_client


class DeliveryArtifactGeneratorTest(unittest.TestCase):
    def test_delivery_files_are_created(self) -> None:
        result = run_single_client(Path("configs/clients/demo-client"))

        package_path = Path(result["output_paths"]["delivery_package_json"])
        summary_path = Path(result["output_paths"]["delivery_summary_markdown"])

        self.assertTrue(package_path.exists())
        self.assertTrue(summary_path.exists())
        self.assertIn("Files Ready For Review/Send", summary_path.read_text(encoding="utf-8"))

    def test_delivery_package_references_expected_artifact_paths(self) -> None:
        result = run_single_client(Path("configs/clients/demo-client"))

        package_path = Path(result["output_paths"]["delivery_package_json"])
        delivery_package = json.loads(package_path.read_text(encoding="utf-8"))
        included = delivery_package["included_artifacts"]

        self.assertEqual(delivery_package["client_name"], "BrightPath Creative")
        self.assertEqual(delivery_package["delivery_status"], "ready_for_review")
        self.assertEqual(delivery_package["recommended_recipient_type"], "finance")
        self.assertEqual(included["scope_creep_report_path"], result["output_paths"]["client_report"])
        self.assertEqual(included["invoice_markdown_path"], result["output_paths"]["invoice_markdown"])
        self.assertEqual(included["invoice_json_path"], result["output_paths"]["invoice_json"])
        self.assertEqual(included["billing_cover_path"], result["output_paths"]["billing_cover_markdown"])
        self.assertEqual(included["billing_package_path"], result["output_paths"]["billing_package_json"])


if __name__ == "__main__":
    unittest.main()
