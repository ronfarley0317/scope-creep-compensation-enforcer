from __future__ import annotations

import difflib
import json
import unittest
from pathlib import Path

from app.workflows.run_single_client import run_single_client


class DemoExpectedOutputTest(unittest.TestCase):
    def test_demo_pipeline_matches_expected_scope_creep_output(self) -> None:
        result = run_single_client(Path("configs/client/demo-client"))
        actual = self._project_actual_output(result)
        expected = json.loads(
            Path("configs/client/demo-client/expected_scope_creep_output.json").read_text(
                encoding="utf-8"
            )
        )

        missing_events = self._missing_events(expected["scope_creep_events"], actual["scope_creep_events"])
        field_mismatches = self._field_mismatches(
            expected["scope_creep_events"], actual["scope_creep_events"]
        )
        classification_mismatches = self._classification_mismatches(
            expected["scope_creep_events"], actual["scope_creep_events"]
        )
        revenue_mismatch = (
            expected["estimated_billable_amount"]["amount"]
            != actual["estimated_billable_amount"]["amount"]
        )

        if missing_events or field_mismatches or classification_mismatches or revenue_mismatch:
            expected_json = json.dumps(expected, indent=2, sort_keys=True)
            actual_json = json.dumps(actual, indent=2, sort_keys=True)
            diff = "\n".join(
                difflib.unified_diff(
                    expected_json.splitlines(),
                    actual_json.splitlines(),
                    fromfile="expected_scope_creep_output.json",
                    tofile="actual_pipeline_output.json",
                    lineterm="",
                )
            )
            failure_parts = []
            if missing_events:
                failure_parts.append(f"Missing events: {missing_events}")
            if classification_mismatches:
                failure_parts.append(f"Incorrect classification: {classification_mismatches}")
            if field_mismatches:
                failure_parts.append(f"Trace field mismatches: {field_mismatches}")
            if revenue_mismatch:
                failure_parts.append(
                    "Incorrect revenue calculation: "
                    f"expected {expected['estimated_billable_amount']['amount']} "
                    f"got {actual['estimated_billable_amount']['amount']}"
                )
            self.fail("\n".join(failure_parts + ["Diff:", diff]))

    def _project_actual_output(self, result: dict) -> dict:
        comparison = result["comparison"]
        events = []
        for event in comparison["creep_events"]:
            matching_limit = next(
                (
                    limit
                    for limit in comparison["exceeded_limits"]
                    if limit["work_item_id"] == event["work_item_id"]
                ),
                None,
            )
            events.append(
                {
                    "event_id": event["event_id"],
                    "normalized_category": event["normalized_category"],
                    "event_type": event["event_type"],
                    "source_type": event["source_type"],
                    "source_reference": event["source_reference"],
                    "source_excerpt": event["source_excerpt"],
                    "scope_reference_id": (
                        matching_limit["limit_id"]
                        if event["event_type"] == "limit_exceeded" and matching_limit is not None
                        else event["scope_reference_id"]
                    ),
                    "work_item_id": event["work_item_id"],
                    "description": self._expected_style_description(event, matching_limit),
                    "agreed_allowance": event["agreed_allowance"],
                    "actual_delivered_amount": event["actual_delivered_amount"],
                    "exceeded_amount": event["exceeded_amount"],
                    "billing_rule_applied": event["billing_rule_applied"],
                    "revenue_impact_calculation": event["revenue_impact_calculation"],
                    "system_explanation": event["system_explanation"],
                    "client_explanation": event["client_explanation"],
                    "included_quantity": matching_limit["allowed_value"] if matching_limit else None,
                    "actual_quantity": matching_limit["actual_value"] if matching_limit else None,
                    "excess_quantity": event["billable_quantity"],
                    "unit": self._normalize_unit(event["billable_unit"]),
                    "rate": event["rate"],
                    "estimated_amount": event["estimated_amount"],
                    "currency": event["currency"],
                }
            )

        return {
            "client_id": result["client"]["client_id"],
            "scope_creep_events": events,
            "estimated_billable_amount": {
                "currency": comparison["revenue_impact_estimate"]["currency"],
                "amount": comparison["revenue_impact_estimate"]["estimated_amount"],
                "formula": "(2 extra ad creatives x 200) + (2 extra revision rounds x 150) + (1 extra landing page section x 300)",
            },
        }

    def _missing_events(self, expected_events: list[dict], actual_events: list[dict]) -> list[str]:
        actual_ids = {event["event_id"] for event in actual_events}
        return [event["event_id"] for event in expected_events if event["event_id"] not in actual_ids]

    def _field_mismatches(self, expected_events: list[dict], actual_events: list[dict]) -> list[str]:
        actual_by_id = {event["event_id"]: event for event in actual_events}
        mismatches: list[str] = []
        for expected_event in expected_events:
            actual_event = actual_by_id.get(expected_event["event_id"])
            if actual_event is None:
                continue
            for field_name, expected_value in expected_event.items():
                actual_value = actual_event.get(field_name)
                if expected_value != actual_value:
                    mismatches.append(
                        f"{expected_event['event_id']}.{field_name}: expected {expected_value!r} got {actual_value!r}"
                    )
        return mismatches

    def _classification_mismatches(
        self, expected_events: list[dict], actual_events: list[dict]
    ) -> list[str]:
        actual_by_id = {event["event_id"]: event for event in actual_events}
        mismatches: list[str] = []
        for expected_event in expected_events:
            actual_event = actual_by_id.get(expected_event["event_id"])
            if actual_event is None:
                continue
            if expected_event["event_type"] != actual_event["event_type"]:
                mismatches.append(
                    f"{expected_event['event_id']}: expected {expected_event['event_type']} got {actual_event['event_type']}"
                )
        return mismatches

    def _normalize_unit(self, unit: str | None) -> str | None:
        if unit == "rounds":
            return "round"
        return unit

    def _expected_style_description(self, event: dict, matching_limit: dict | None) -> str:
        if event["work_item_id"] == "demo-work-001":
            return "Delivered 6 ad creatives against an included scope of 4."
        if event["work_item_id"] == "demo-work-002":
            return "Completed 4 revision rounds against an included limit of 2."
        if event["work_item_id"] == "demo-work-003":
            return "Requested 1 extra landing page section beyond the included base section."
        return event["reason"]


if __name__ == "__main__":
    unittest.main()
