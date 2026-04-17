import json
import tempfile
import unittest
from pathlib import Path

from app.workflows.run_single_client import run_single_client


class RunHistoryTest(unittest.TestCase):
    def test_successful_run_writes_run_history(self) -> None:
        run_history_dir = Path("outputs/run_history")
        before = {path.name for path in run_history_dir.glob("*.json")} if run_history_dir.exists() else set()

        result = run_single_client(Path("configs/clients/demo-client"))

        run_history_path = Path(result["output_paths"]["run_history"])
        self.assertTrue(run_history_path.exists())
        self.assertNotIn(run_history_path.name, before)

        metadata = json.loads(run_history_path.read_text(encoding="utf-8"))
        self.assertEqual(metadata["status"], "success")
        self.assertEqual(metadata["client_name"], "BrightPath Creative")
        self.assertEqual(metadata["total_scope_creep_events"], 3)
        self.assertEqual(metadata["total_billable_impact"], 1000.0)

    def test_failed_run_writes_run_history(self) -> None:
        demo_dir = Path("configs/clients/demo-client").resolve()
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            client_dir = tmp_path / "broken-client"
            client_dir.mkdir(parents=True, exist_ok=True)
            output_dir = tmp_path / "outputs" / "broken-client"
            client_yaml = "\n".join(
                [
                    "client_id: broken-client",
                    "client_name: Broken Client",
                    "client_type: small_marketing_agency",
                    "currency: USD",
                    "industry: marketing_agency",
                    f"contract_rules_path: {demo_dir / 'contract_rules.yaml'}",
                    f"field_mapping_path: {demo_dir / 'field_mapping.yaml'}",
                    f"sample_sow_path: {demo_dir / 'structured_sow.md'}",
                    f"sample_work_log_path: {demo_dir / 'structured_work_log.json'}",
                    "scope_source_type: local_fixture",
                    "work_source_type: local_fixture",
                    "billing_source_type: unsupported",
                    f"output_dir: {output_dir}",
                ]
            )
            (client_dir / "client.yaml").write_text(client_yaml, encoding="utf-8")

            with self.assertRaises(ValueError):
                run_single_client(client_dir)

            run_history_dir = client_dir / "runs"
            history_files = list(run_history_dir.glob("*/run_metadata.json"))
            self.assertEqual(len(history_files), 1)
            metadata = json.loads(history_files[0].read_text(encoding="utf-8"))
            self.assertEqual(metadata["status"], "failure")
            self.assertEqual(metadata["client_name"], "Broken Client")
            self.assertEqual(metadata["billing_source_type"], "unsupported")
            self.assertIn("Unsupported billing adapter type", metadata["error_message"])

    def test_artifact_paths_are_captured_in_run_history(self) -> None:
        result = run_single_client(Path("configs/clients/demo-client"))

        run_history_path = Path(result["output_paths"]["run_history"])
        metadata = json.loads(run_history_path.read_text(encoding="utf-8"))
        artifacts = metadata["generated_artifacts"]

        self.assertEqual(artifacts["client_report"], result["output_paths"]["client_report"])
        self.assertEqual(artifacts["invoice_json"], result["output_paths"]["invoice_json"])
        self.assertEqual(artifacts["invoice_markdown"], result["output_paths"]["invoice_markdown"])
        self.assertEqual(artifacts["billing_package_json"], result["output_paths"]["billing_package_json"])
        self.assertEqual(artifacts["billing_cover_markdown"], result["output_paths"]["billing_cover_markdown"])
        self.assertEqual(artifacts["delivery_package_json"], result["output_paths"]["delivery_package_json"])
        self.assertEqual(artifacts["delivery_summary_markdown"], result["output_paths"]["delivery_summary_markdown"])


if __name__ == "__main__":
    unittest.main()
