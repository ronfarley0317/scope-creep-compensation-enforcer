from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from app.workflows.run_single_client import run_single_client


class ConfigDrivenPipelineTest(unittest.TestCase):
    def test_changing_field_mapping_changes_behavior_without_code_changes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            base_path = Path(tmp_dir)
            self._write_client_bundle(
                base_path=base_path,
                client_name="Mapping Test Client",
                work_log_name="work_log.json",
                field_mapping_yaml="""
source_type: structured_documents
client_id: mapping-client
sow_mapping:
  deliverables_section: scope items
  deliverable_fields:
    id:
      - deliverable_key
work_item_mapping:
  work_item_id: record_id
  work_date: logged_on
  task_category: task_type
  deliverable_hint: deliverable_code
  description: details
  hours: effort_hours
  revision_count: revision_count
quantity_mapping:
  by_category:
    ad_creative:
      field: delivered_units
      unit: creative
normalization_rules:
  deliverable_aliases:
    ad-creatives:
      - creative_pack
  category_aliases:
    ad_creative:
      - ad_variant
  quantity_defaults: {}
audit_fields:
  - record_id
""",
            )
            (base_path / "work_log.json").write_text(
                json.dumps(
                    {
                        "work_items": [
                            {
                                "record_id": "item-1",
                                "deliverable_code": "creative_pack",
                                "task_type": "ad_variant",
                                "details": "Delivered six creatives",
                                "delivered_units": 6,
                                "effort_hours": 10,
                                "logged_on": "2026-04-30",
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )

            result = run_single_client(base_path)
            self.assertEqual(len(result["comparison"]["creep_events"]), 1)
            self.assertEqual(result["comparison"]["revenue_impact_estimate"]["estimated_amount"], 400.0)

            (base_path / "field_mapping.yaml").write_text(
                (base_path / "field_mapping.yaml")
                .read_text(encoding="utf-8")
                .replace("field: delivered_units", "field: missing_units"),
                encoding="utf-8",
            )

            changed_result = run_single_client(base_path)
            self.assertEqual(len(changed_result["comparison"]["creep_events"]), 0)
            self.assertEqual(changed_result["comparison"]["revenue_impact_estimate"]["estimated_amount"], 0.0)

    def test_different_clients_produce_different_outputs_using_same_engine(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            client_a = root / "client-a"
            client_b = root / "client-b"

            self._write_client_bundle(base_path=client_a, client_name="Client A", work_log_name="work_log.json")
            self._write_client_bundle(
                base_path=client_b,
                client_name="Client B",
                work_log_name="work_log.json",
                contract_rules_yaml="""
client_id: client-b
contract_name: Alternate Creative Package
contract_version: 1
currency: USD
scope:
  deliverables:
    - id: ad-creatives
      name: Ad Creatives
      included_quantity: 5
      unit: creative
      task_categories:
        - ad_creative
      notes: Includes five ad creatives.
  limits: []
  billing_rules:
    - id: extra-ad-creatives
      applies_to:
        - ad-creatives
      trigger: extra_deliverable_quantity
      billing_type: flat_fee
      amount: 250
      unit: creative
      notes: Extra creatives billed at 250 each.
assumptions: []
interpretation:
  quantity_trigger_by_unit:
    creative: extra_deliverable_quantity
  out_of_scope_trigger: out_of_scope
""",
            )

            work_log = {
                "work_items": [
                    {
                        "record_id": "item-1",
                        "deliverable_code": "creative_pack",
                        "task_type": "ad_variant",
                        "details": "Delivered six creatives",
                        "delivered_units": 6,
                        "effort_hours": 10,
                        "logged_on": "2026-04-30",
                    }
                ]
            }
            (client_a / "work_log.json").write_text(json.dumps(work_log), encoding="utf-8")
            (client_b / "work_log.json").write_text(json.dumps(work_log), encoding="utf-8")

            result_a = run_single_client(client_a)
            result_b = run_single_client(client_b)

            self.assertEqual(result_a["comparison"]["revenue_impact_estimate"]["estimated_amount"], 400.0)
            self.assertEqual(result_b["comparison"]["revenue_impact_estimate"]["estimated_amount"], 250.0)
            self.assertNotEqual(
                result_a["compensation"]["draft_invoice_line_items"][0]["amount"],
                result_b["compensation"]["draft_invoice_line_items"][0]["amount"],
            )

    def _write_client_bundle(
        self,
        *,
        base_path: Path,
        client_name: str,
        work_log_name: str,
        field_mapping_yaml: str | None = None,
        contract_rules_yaml: str | None = None,
    ) -> None:
        base_path.mkdir(parents=True, exist_ok=True)
        (base_path / "client.yaml").write_text(
            f"""
client_id: {base_path.name}
client_name: {client_name}
client_type: test_client
currency: USD
contract_rules_path: contract_rules.yaml
field_mapping_path: field_mapping.yaml
sample_sow_path: structured_sow.md
sample_work_log_path: {work_log_name}
output_dir: outputs
""".strip()
            + "\n",
            encoding="utf-8",
        )
        (base_path / "structured_sow.md").write_text(
            """
# Structured SOW

Client ID: demo
Client Name: Demo
Currency: USD

## Scope Items
- deliverable_key: ad-creatives
  name: Ad Creatives
  included_quantity: 4
  unit: creative
  notes: Includes four ad creatives.
""".strip()
            + "\n",
            encoding="utf-8",
        )
        (base_path / "contract_rules.yaml").write_text(
            (
                contract_rules_yaml
                or """
client_id: mapping-client
contract_name: Creative Package
contract_version: 1
currency: USD
scope:
  deliverables:
    - id: ad-creatives
      name: Ad Creatives
      included_quantity: 4
      unit: creative
      task_categories:
        - ad_creative
      notes: Includes four ad creatives.
  limits: []
  billing_rules:
    - id: extra-ad-creatives
      applies_to:
        - ad-creatives
      trigger: extra_deliverable_quantity
      billing_type: flat_fee
      amount: 200
      unit: creative
      notes: Extra creatives billed at 200 each.
assumptions: []
interpretation:
  quantity_trigger_by_unit:
    creative: extra_deliverable_quantity
  out_of_scope_trigger: out_of_scope
"""
            ).strip()
            + "\n",
            encoding="utf-8",
        )
        (base_path / "field_mapping.yaml").write_text(
            (
                field_mapping_yaml
                or """
source_type: structured_documents
client_id: mapping-client
sow_mapping:
  deliverables_section: scope items
  deliverable_fields:
    id:
      - deliverable_key
work_item_mapping:
  work_item_id: record_id
  work_date: logged_on
  task_category: task_type
  deliverable_hint: deliverable_code
  description: details
  hours: effort_hours
  revision_count: revision_count
quantity_mapping:
  by_category:
    ad_creative:
      field: delivered_units
      unit: creative
normalization_rules:
  deliverable_aliases:
    ad-creatives:
      - creative_pack
  category_aliases:
    ad_creative:
      - ad_variant
  quantity_defaults: {}
"""
            ).strip()
            + "\n",
            encoding="utf-8",
        )


if __name__ == "__main__":
    unittest.main()
