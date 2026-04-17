from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.sources.billing_base import BillingAdapter


class ManualBillingAdapter(BillingAdapter):
    def prepare_billing_package(
        self,
        client_config: dict[str, Any],
        invoice_artifacts: dict[str, Any],
        compensation: dict[str, Any],
        invoice_file_refs: dict[str, str],
    ) -> dict[str, Any]:
        invoice_json = invoice_artifacts["invoice_json"]
        package_json = {
            "client_id": client_config["client_id"],
            "client_name": client_config["client_name"],
            "review_status": "pending",
            "recommended_action": compensation["client_facing_summary"]["requested_action"],
            "invoice_file_references": invoice_file_refs,
            "invoice_id": invoice_json["invoice_id"],
            "total_amount": invoice_json["total_amount"],
        }
        cover_markdown = self._build_cover_markdown(
            client_name=client_config["client_name"],
            invoice_id=invoice_json["invoice_id"],
            invoice_date=invoice_json["date"],
            total_amount=invoice_json["total_amount"],
            recommended_action=package_json["recommended_action"],
            invoice_file_refs=invoice_file_refs,
        )
        return {
            "billing_package_json": package_json,
            "billing_cover_markdown": cover_markdown,
        }

    def write(
        self,
        output_dir: str | Path,
        client_slug: str,
        package: dict[str, Any],
    ) -> dict[str, str]:
        base_path = Path(output_dir)
        base_path.mkdir(parents=True, exist_ok=True)
        json_path = base_path / f"{client_slug}-billing-package.json"
        markdown_path = base_path / f"{client_slug}-billing-cover.md"
        json_path.write_text(json.dumps(package["billing_package_json"], indent=2), encoding="utf-8")
        markdown_path.write_text(package["billing_cover_markdown"], encoding="utf-8")
        return {
            "billing_package_json": str(json_path),
            "billing_cover_markdown": str(markdown_path),
        }

    def healthcheck(self, client_config: dict[str, Any]) -> dict[str, Any]:
        return {
            "adapter": "manual",
            "healthy": True,
            "mode": "human_review",
            "client_id": client_config["client_id"],
        }

    def _build_cover_markdown(
        self,
        *,
        client_name: str,
        invoice_id: str,
        invoice_date: str,
        total_amount: float,
        recommended_action: str,
        invoice_file_refs: dict[str, str],
    ) -> str:
        return "\n".join(
            [
                f"# Billing Cover: {client_name}",
                "",
                f"- Invoice ID: {invoice_id}",
                f"- Invoice Date: {invoice_date}",
                f"- Review Status: pending",
                f"- Recommended Action: {recommended_action}",
                f"- Total Amount: {total_amount:.2f}",
                "",
                "## Invoice Files",
                f"- JSON: {invoice_file_refs['invoice_json']}",
                f"- Markdown: {invoice_file_refs['invoice_markdown']}",
                "",
                "## Notes",
                "This package is prepared for manual billing review and send.",
            ]
        )
