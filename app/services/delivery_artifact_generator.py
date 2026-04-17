from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class DeliveryArtifactResult:
    package_json: dict[str, Any]
    summary_markdown: str


class DeliveryArtifactGenerator:
    """Build a human-readable delivery bundle from generated workflow artifacts."""

    def build(
        self,
        run_result: dict[str, Any],
        artifact_paths: dict[str, str],
    ) -> DeliveryArtifactResult:
        client_name = run_result["client"]["client_name"]
        total_amount = run_result["comparison"]["revenue_impact_estimate"]["estimated_amount"] or 0.0
        recommended_action = run_result["compensation"]["client_facing_summary"]["requested_action"]
        recipient_type = self._recommended_recipient_type(run_result)
        package_json = {
            "client_name": client_name,
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "included_artifacts": {
                "scope_creep_report_path": artifact_paths["client_report"],
                "invoice_markdown_path": artifact_paths["invoice_markdown"],
                "invoice_json_path": artifact_paths["invoice_json"],
                "billing_cover_path": artifact_paths["billing_cover_markdown"],
                "billing_package_path": artifact_paths["billing_package_json"],
            },
            "delivery_status": "ready_for_review",
            "recommended_recipient_type": recipient_type,
        }
        summary_markdown = self._build_summary_markdown(
            run_result,
            package_json["included_artifacts"],
            total_amount,
            recommended_action,
            recipient_type,
        )
        return DeliveryArtifactResult(package_json=package_json, summary_markdown=summary_markdown)

    def write(
        self,
        output_dir: str | Path,
        client_slug: str,
        artifact: DeliveryArtifactResult,
    ) -> dict[str, str]:
        base_path = Path(output_dir)
        base_path.mkdir(parents=True, exist_ok=True)
        json_path = base_path / f"{client_slug}-delivery-package.json"
        markdown_path = base_path / f"{client_slug}-delivery-summary.md"
        json_path.write_text(json.dumps(artifact.package_json, indent=2), encoding="utf-8")
        markdown_path.write_text(artifact.summary_markdown, encoding="utf-8")
        return {
            "delivery_package_json": str(json_path),
            "delivery_summary_markdown": str(markdown_path),
        }

    def _recommended_recipient_type(self, run_result: dict[str, Any]) -> str:
        if run_result["comparison"]["revenue_impact_estimate"]["estimated_amount"]:
            return "finance"
        return "internal"

    def _build_summary_markdown(
        self,
        run_result: dict[str, Any],
        included_artifacts: dict[str, str],
        total_amount: float,
        recommended_action: str,
        recipient_type: str,
    ) -> str:
        comparison = run_result["comparison"]
        client_name = run_result["client"]["client_name"]
        currency = comparison["revenue_impact_estimate"]["currency"]
        lines = [
            f"# Delivery Summary: {client_name}",
            "",
            "## What Was Detected",
            (
                f"The workflow detected {len(comparison['creep_events'])} scope-creep event(s) "
                f"and {len(comparison['exceeded_limits'])} exceeded-limit finding(s)."
            ),
            "",
            "## Total Billable Impact",
            f"{currency} {total_amount:.2f}",
            "",
            "## Files Ready For Review/Send",
        ]
        for label, path in included_artifacts.items():
            lines.append(f"- {label}: {path}")
        lines.extend(
            [
                "",
                "## Recommended Next Action",
                f"- Recipient type: {recipient_type}",
                f"- Action: {recommended_action}",
            ]
        )
        return "\n".join(lines)
