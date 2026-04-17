import json
import unittest
from pathlib import Path

from app.services.config_loader import load_client_bundle
from app.sources.manual_billing_adapter import ManualBillingAdapter
from app.workflows.run_single_client import run_single_client


class ManualBillingAdapterTest(unittest.TestCase):
    def test_manual_billing_adapter_produces_expected_files(self) -> None:
        result = run_single_client(Path("configs/clients/demo-client"))

        billing_json_path = Path(result["output_paths"]["billing_package_json"])
        billing_markdown_path = Path(result["output_paths"]["billing_cover_markdown"])

        self.assertTrue(billing_json_path.exists())
        self.assertTrue(billing_markdown_path.exists())

        billing_package = json.loads(billing_json_path.read_text(encoding="utf-8"))
        self.assertEqual(billing_package["review_status"], "pending")
        self.assertEqual(billing_package["client_id"], "demo-client")
        self.assertEqual(billing_package["total_amount"], 1000.0)
        self.assertIn("recommended_action", billing_package)
        self.assertIn("invoice_file_references", billing_package)
        self.assertTrue(billing_package["invoice_file_references"]["invoice_json"].endswith("demo-client-invoice.json"))
        self.assertTrue(billing_package["invoice_file_references"]["invoice_markdown"].endswith("demo-client-invoice.md"))
        self.assertIn("manual billing review and send", billing_markdown_path.read_text(encoding="utf-8"))

    def test_manual_billing_adapter_healthcheck(self) -> None:
        client_dir = Path("configs/clients/demo-client")
        bundle = load_client_bundle(client_dir)
        client_config = {**bundle.client, "_client_dir": str(client_dir)}

        health = ManualBillingAdapter().healthcheck(client_config)

        self.assertEqual(health["adapter"], "manual")
        self.assertTrue(health["healthy"])
        self.assertEqual(health["mode"], "human_review")


if __name__ == "__main__":
    unittest.main()
