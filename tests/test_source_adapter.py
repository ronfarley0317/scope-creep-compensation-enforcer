import unittest
from pathlib import Path

from app.models.source_inputs import ScopeInput, WorkActivityInput
from app.services.config_loader import load_client_bundle
from app.sources.local_fixture_adapter import LocalFixtureAdapter
from app.sources.manual_billing_adapter import ManualBillingAdapter
from app.sources.resolver import SourceResolver
from app.workflows.run_single_client import run_single_client


class SourceAdapterTest(unittest.TestCase):
    def test_local_fixture_adapter_returns_valid_inputs(self) -> None:
        client_dir = Path("configs/clients/demo-client")
        bundle = load_client_bundle(client_dir)
        client_config = {**bundle.client, "_client_dir": str(client_dir)}
        adapter = LocalFixtureAdapter()

        scope_input = adapter.fetch_scope_inputs(client_config)
        work_input = adapter.fetch_work_activity_inputs(client_config)
        health = adapter.healthcheck(client_config)

        self.assertIsInstance(scope_input, ScopeInput)
        self.assertIsInstance(work_input, WorkActivityInput)
        self.assertEqual(scope_input.source_type, "local_fixture")
        self.assertEqual(work_input.source_type, "local_fixture")
        self.assertIn("metadata", scope_input.payload)
        self.assertIn("work_items", work_input.payload)
        self.assertTrue(health["healthy"])

    def test_system_runs_end_to_end_using_adapter(self) -> None:
        client_dir = Path("configs/clients/demo-client")
        bundle = load_client_bundle(client_dir)
        client_config = {**bundle.client, "_client_dir": str(client_dir)}
        resolver = SourceResolver()
        lanes = resolver.resolve_lanes(client_config)
        scope_adapter = lanes["scope_adapter"]
        work_adapter = lanes["work_adapter"]

        self.assertIsInstance(scope_adapter, LocalFixtureAdapter)
        self.assertIsInstance(work_adapter, LocalFixtureAdapter)
        self.assertIsInstance(lanes["billing_adapter"], ManualBillingAdapter)
        self.assertEqual(lanes["scope_source_type"], "local_fixture")
        self.assertEqual(lanes["work_source_type"], "local_fixture")
        self.assertEqual(lanes["billing_source_type"], "manual")

        result = run_single_client(client_dir)

        self.assertEqual(result["source_lanes"]["scope_source_type"], "local_fixture")
        self.assertEqual(result["source_lanes"]["work_source_type"], "local_fixture")
        self.assertEqual(result["source_lanes"]["billing_source_type"], "manual")
        self.assertEqual(result["scope_input"]["source_type"], "local_fixture")
        self.assertEqual(result["work_activity_input"]["source_type"], "local_fixture")
        self.assertTrue(result["source_healthcheck"]["scope"]["healthy"])
        self.assertTrue(result["source_healthcheck"]["work"]["healthy"])
        self.assertTrue(result["source_healthcheck"]["billing"]["healthy"])
        self.assertEqual(len(result["comparison"]["creep_events"]), 3)
        self.assertTrue(Path(result["output_paths"]["billing_package_json"]).exists())
        self.assertTrue(Path(result["output_paths"]["billing_cover_markdown"]).exists())
        self.assertTrue(Path(result["output_paths"]["delivery_package_json"]).exists())
        self.assertTrue(Path(result["output_paths"]["delivery_summary_markdown"]).exists())


if __name__ == "__main__":
    unittest.main()
