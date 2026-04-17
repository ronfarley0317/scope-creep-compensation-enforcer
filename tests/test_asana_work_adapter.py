import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.models.source_inputs import WorkActivityInput
from app.sources.asana_work_adapter import AsanaWorkAdapter
from app.workflows.run_single_client import run_single_client


class AsanaWorkAdapterTest(unittest.TestCase):
    def test_fetch_work_activity_inputs_from_mocked_asana(self) -> None:
        adapter = AsanaWorkAdapter()
        client_config = {
            "client_id": "asana-client",
            "client_name": "Asana Client",
            "asana": {
                "access_token_env": "ASANA_ACCESS_TOKEN",
                "project_gid": "proj-123",
                "completed_since": "2026-04-01T00:00:00Z",
            },
        }

        with patch.dict(os.environ, {"ASANA_ACCESS_TOKEN": "token"}):
            with patch.object(adapter, "_request_json", side_effect=self._mock_request_json):
                work_input = adapter.fetch_work_activity_inputs(client_config)
                health = adapter.healthcheck(client_config)

        self.assertIsInstance(work_input, WorkActivityInput)
        self.assertEqual(work_input.source_type, "asana")
        self.assertEqual(work_input.source_reference, "asana_project:proj-123")
        self.assertEqual(work_input.payload["period"]["start_date"], "2026-04-10")
        self.assertEqual(work_input.payload["period"]["end_date"], "2026-04-12")
        self.assertEqual(len(work_input.payload["work_items"]), 2)
        self.assertEqual(work_input.payload["work_items"][0]["tracked_hours"], 6.5)
        self.assertEqual(work_input.payload["work_items"][0]["deliverable"], "ad-creatives")
        self.assertEqual(work_input.payload["work_items"][0]["revision_rounds"], 2)
        self.assertTrue(health["healthy"])
        self.assertEqual(health["actor_name"], "Adapter Test User")

    def test_workflow_runs_with_asana_work_source_and_mocked_responses(self) -> None:
        demo_dir = Path("configs/clients/demo-client").resolve()
        with tempfile.TemporaryDirectory() as tmpdir:
            client_dir = Path(tmpdir) / "asana-client"
            client_dir.mkdir(parents=True, exist_ok=True)
            (client_dir / "client.yaml").write_text(
                "\n".join(
                    [
                        "client_id: asana-client",
                        "client_name: Asana Agency",
                        "client_type: small_marketing_agency",
                        "currency: USD",
                        f"contract_rules_path: {demo_dir / 'contract_rules.yaml'}",
                        f"field_mapping_path: {client_dir / 'field_mapping.yaml'}",
                        f"sample_sow_path: {demo_dir / 'structured_sow.md'}",
                        "scope_source_type: local_fixture",
                        "work_source_type: asana",
                        "billing_source_type: manual",
                        f"output_dir: {Path(tmpdir) / 'outputs' / 'asana-client'}",
                        "asana:",
                        "  access_token_env: ASANA_ACCESS_TOKEN",
                        "  project_gid: proj-123",
                        "  completed_since: 2026-04-01T00:00:00Z",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            (client_dir / "field_mapping.yaml").write_text(
                "\n".join(
                    [
                        "source_type: structured_documents",
                        "field_aliases:",
                        "  deliverables:",
                        "    - deliverable",
                        "    - deliverable_hint",
                        "  revisions:",
                        "    - revision_rounds",
                        "  hours:",
                        "    - tracked_hours",
                        "  assets:",
                        "    - assets_delivered",
                        "sow_mapping:",
                        "  deliverables_section: included scope",
                        "  deliverable_fields:",
                        "    id:",
                        "      - deliverable_id",
                        "      - id",
                        "    extra_quantity_fields:",
                        "      section: included_sections",
                        "work_item_mapping:",
                        "  work_item_id: id",
                        "  work_date: performed_on",
                        "  task_category: task_category",
                        "  deliverable_hint: deliverables",
                        "  description: description",
                        "  hours: hours",
                        "  revision_count: revisions",
                        "quantity_mapping:",
                        "  by_category:",
                        "    ad_creative:",
                        "      field: assets",
                        "      unit: creative",
                        "    landing_page:",
                        "      field: section_count",
                        "      unit: section",
                        "normalization_rules:",
                        "  deliverable_aliases:",
                        "    ad-creatives:",
                        "      - ad-creatives",
                        "    landing-page:",
                        "      - landing-page",
                        "  category_aliases:",
                        "    ad_creative:",
                        "      - ad_creative",
                        "    landing_page:",
                        "      - landing_page",
                        "  unit_aliases:",
                        "    creative:",
                        "      - creative",
                        "      - creatives",
                        "    section:",
                        "      - section",
                        "  quantity_defaults: {}",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            with patch.dict(os.environ, {"ASANA_ACCESS_TOKEN": "token"}):
                with patch.object(AsanaWorkAdapter, "_request_json", side_effect=self._mock_request_json):
                    result = run_single_client(client_dir)

        self.assertEqual(result["work_activity_input"]["source_type"], "asana")
        self.assertTrue(result["source_healthcheck"]["work"]["healthy"])
        self.assertEqual(len(result["comparison"]["creep_events"]), 2)
        self.assertEqual(result["comparison"]["revenue_impact_estimate"]["estimated_amount"], 700.0)

    def _mock_request_json(self, path, settings, *, query=None):
        if path == "/users/me":
            return {"data": {"gid": "user-1", "name": "Adapter Test User"}}
        if path.startswith("/projects/proj-123/tasks"):
            return {
                "data": [
                    {
                        "gid": "task-1",
                        "name": "Create extra ad creatives",
                        "notes": "Delivered six creatives for the April campaign.",
                        "completed": True,
                        "completed_at": "2026-04-10T12:00:00Z",
                        "created_at": "2026-04-09T12:00:00Z",
                        "modified_at": "2026-04-10T12:00:00Z",
                        "permalink_url": "https://app.asana.com/0/1/task-1",
                        "custom_fields": [
                            {
                                "gid": "cf-hours",
                                "name": "Tracked Hours",
                                "resource_subtype": "number",
                                "number_value": 6.5,
                            },
                            {
                                "gid": "cf-deliverable",
                                "name": "Deliverable",
                                "resource_subtype": "text",
                                "text_value": "ad-creatives",
                            },
                            {
                                "gid": "cf-category",
                                "name": "Task Category",
                                "resource_subtype": "enum",
                                "enum_value": {"name": "ad_creative"},
                            },
                            {
                                "gid": "cf-assets",
                                "name": "Assets Delivered",
                                "resource_subtype": "number",
                                "number_value": 6,
                            },
                            {
                                "gid": "cf-revisions",
                                "name": "Revision Rounds",
                                "resource_subtype": "number",
                                "number_value": 2,
                            },
                        ],
                    },
                    {
                        "gid": "task-2",
                        "name": "Build extra landing page section",
                        "notes": "Added one extra landing page section requested during review.",
                        "completed": True,
                        "completed_at": "2026-04-12T15:30:00Z",
                        "created_at": "2026-04-11T15:30:00Z",
                        "modified_at": "2026-04-12T15:30:00Z",
                        "permalink_url": "https://app.asana.com/0/1/task-2",
                        "custom_fields": [
                            {
                                "gid": "cf-hours",
                                "name": "Tracked Hours",
                                "resource_subtype": "number",
                                "number_value": 3.0,
                            },
                            {
                                "gid": "cf-deliverable",
                                "name": "Deliverable",
                                "resource_subtype": "text",
                                "text_value": "landing-page",
                            },
                            {
                                "gid": "cf-category",
                                "name": "Task Category",
                                "resource_subtype": "enum",
                                "enum_value": {"name": "landing_page"},
                            },
                            {
                                "gid": "cf-sections",
                                "name": "Section Count",
                                "resource_subtype": "number",
                                "number_value": 2,
                            },
                        ],
                    },
                ],
                "next_page": None,
            }
        raise AssertionError(f"Unexpected path: {path}")
