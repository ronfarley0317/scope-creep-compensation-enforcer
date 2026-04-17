import json
import tempfile
import unittest
from pathlib import Path

from app.workflows.run_all_clients import run_all_clients


class BatchRunnerTest(unittest.TestCase):
    def test_multiple_clients_can_run_in_one_batch(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            clients_root = self._build_test_clients(Path(tmpdir), include_broken=False)

            result = run_all_clients(clients_root)

            self.assertEqual(result["total_clients_attempted"], 2)
            self.assertEqual(result["total_clients_succeeded"], 2)
            self.assertEqual(result["total_clients_failed"], 0)
            self.assertEqual(len(result["per_client_results"]), 2)

    def test_one_client_failure_does_not_stop_the_batch(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            clients_root = self._build_test_clients(Path(tmpdir), include_broken=True)

            result = run_all_clients(clients_root)

            self.assertEqual(result["total_clients_attempted"], 3)
            self.assertEqual(result["total_clients_succeeded"], 2)
            self.assertEqual(result["total_clients_failed"], 1)
            statuses = {item["client_name"]: item["status"] for item in result["per_client_results"]}
            self.assertEqual(statuses["Broken Client"], "failure")
            self.assertEqual(statuses["BrightPath Batch A"], "success")
            self.assertEqual(statuses["BrightPath Batch B"], "success")

    def test_batch_summary_files_are_created_correctly(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            clients_root = self._build_test_clients(Path(tmpdir), include_broken=True)

            result = run_all_clients(clients_root)

            json_path = Path(result["output_paths"]["batch_summary_json"])
            markdown_path = Path(result["output_paths"]["batch_summary_markdown"])
            self.assertTrue(json_path.exists())
            self.assertTrue(markdown_path.exists())

            summary_json = json.loads(json_path.read_text(encoding="utf-8"))
            self.assertEqual(summary_json["batch_id"], result["batch_id"])
            self.assertEqual(summary_json["total_clients_attempted"], 3)
            self.assertEqual(len(summary_json["per_client_results"]), 3)
            self.assertIn("Per-Client Results", markdown_path.read_text(encoding="utf-8"))

    def _build_test_clients(self, root: Path, *, include_broken: bool) -> Path:
        demo_dir = Path("configs/clients/demo-client").resolve()
        clients_root = root / "configs" / "clients"
        clients_root.mkdir(parents=True, exist_ok=True)

        self._write_client(
            clients_root / "client-a",
            client_id="client-a",
            client_name="BrightPath Batch A",
            output_dir=root / "outputs" / "client-a",
            demo_dir=demo_dir,
            billing_source_type="manual",
        )
        self._write_client(
            clients_root / "client-b",
            client_id="client-b",
            client_name="BrightPath Batch B",
            output_dir=root / "outputs" / "client-b",
            demo_dir=demo_dir,
            billing_source_type="manual",
        )
        if include_broken:
            self._write_client(
                clients_root / "broken-client",
                client_id="broken-client",
                client_name="Broken Client",
                output_dir=root / "outputs" / "broken-client",
                demo_dir=demo_dir,
                billing_source_type="unsupported",
            )
        return clients_root

    def _write_client(
        self,
        client_dir: Path,
        *,
        client_id: str,
        client_name: str,
        output_dir: Path,
        demo_dir: Path,
        billing_source_type: str,
    ) -> None:
        client_dir.mkdir(parents=True, exist_ok=True)
        client_yaml = "\n".join(
            [
                f"client_id: {client_id}",
                f"client_name: {client_name}",
                "client_type: small_marketing_agency",
                "currency: USD",
                "industry: marketing_agency",
                f"contract_rules_path: {demo_dir / 'contract_rules.yaml'}",
                f"field_mapping_path: {demo_dir / 'field_mapping.yaml'}",
                f"sample_sow_path: {demo_dir / 'structured_sow.md'}",
                f"sample_work_log_path: {demo_dir / 'structured_work_log.json'}",
                "scope_source_type: local_fixture",
                "work_source_type: local_fixture",
                f"billing_source_type: {billing_source_type}",
                f"output_dir: {output_dir}",
                "default_outputs:",
                "  compensation_enforcement_mode: recommend",
            ]
        )
        (client_dir / "client.yaml").write_text(client_yaml, encoding="utf-8")


if __name__ == "__main__":
    unittest.main()
