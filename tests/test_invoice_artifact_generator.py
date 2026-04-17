import unittest
from pathlib import Path

from app.services.invoice_artifact_generator import InvoiceArtifactGenerator
from app.workflows.run_single_client import run_single_client


class InvoiceArtifactGeneratorTest(unittest.TestCase):
    def test_invoice_totals_and_config_pricing(self) -> None:
        result = run_single_client(Path("configs/client/demo-client"))
        invoice_json = result["invoice_artifacts"]["invoice_json"]
        line_items = invoice_json["line_items"]

        self.assertEqual(invoice_json["invoice_id"], "invoice-demo-client-2026-04-30")
        self.assertEqual(invoice_json["client_name"], "BrightPath Creative")
        self.assertEqual(invoice_json["date"], "2026-04-30")
        self.assertEqual(len(line_items), 3)

        summed_total = round(sum(item["total"] for item in line_items), 2)
        self.assertEqual(invoice_json["total_amount"], summed_total)

        by_category = {item["category"]: item for item in line_items}
        self.assertEqual(by_category["ad_creative"]["unit_price"], 200.0)
        self.assertEqual(by_category["revision"]["unit_price"], 150.0)
        self.assertEqual(by_category["landing_page"]["unit_price"], 300.0)

    def test_invoice_output_files_are_created(self) -> None:
        result = run_single_client(Path("configs/client/demo-client"))

        invoice_json_path = Path(result["output_paths"]["invoice_json"])
        invoice_markdown_path = Path(result["output_paths"]["invoice_markdown"])

        self.assertTrue(invoice_json_path.exists())
        self.assertTrue(invoice_markdown_path.exists())
        self.assertIn("Total Amount Due", invoice_markdown_path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
