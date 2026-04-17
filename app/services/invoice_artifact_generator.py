from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from app.models.contract import ContractScope
from app.models.creep_event import CreepEvent


@dataclass(frozen=True)
class InvoiceArtifactResult:
    invoice_json: dict[str, Any]
    invoice_markdown: str


class InvoiceArtifactGenerator:
    """Generate invoice artifacts from normalized scope-creep events."""

    def build(
        self,
        contract: ContractScope,
        creep_events: list[CreepEvent],
        *,
        invoice_date: str | None = None,
    ) -> InvoiceArtifactResult:
        resolved_date = invoice_date or date.today().isoformat()
        line_items = [self._build_line_item(event) for event in creep_events if event.estimated_amount is not None]
        total_amount = round(sum(item["total"] for item in line_items), 2)
        invoice_id = f"invoice-{contract.client_id}-{resolved_date}"
        invoice_json = {
            "invoice_id": invoice_id,
            "client_name": contract.client_name,
            "date": resolved_date,
            "line_items": line_items,
            "total_amount": total_amount,
        }
        invoice_markdown = self._build_markdown(contract.client_name, resolved_date, line_items, total_amount)
        return InvoiceArtifactResult(invoice_json=invoice_json, invoice_markdown=invoice_markdown)

    def write(
        self,
        output_dir: str | Path,
        client_slug: str,
        artifact: InvoiceArtifactResult,
    ) -> dict[str, str]:
        base_path = Path(output_dir)
        base_path.mkdir(parents=True, exist_ok=True)
        json_path = base_path / f"{client_slug}-invoice.json"
        markdown_path = base_path / f"{client_slug}-invoice.md"
        json_path.write_text(json.dumps(artifact.invoice_json, indent=2), encoding="utf-8")
        markdown_path.write_text(artifact.invoice_markdown, encoding="utf-8")
        return {"invoice_json": str(json_path), "invoice_markdown": str(markdown_path)}

    def _build_line_item(self, event: CreepEvent) -> dict[str, Any]:
        quantity = event.billable_quantity
        if quantity is None and event.billable_hours is not None:
            quantity = event.billable_hours
        if quantity is None:
            quantity = 1.0
        unit_price = event.rate or 0.0
        total = round(quantity * unit_price, 2)
        return {
            "description": event.client_explanation,
            "category": event.normalized_category,
            "quantity": quantity,
            "unit_price": unit_price,
            "total": total,
        }

    def _build_markdown(
        self,
        client_name: str,
        invoice_date: str,
        line_items: list[dict[str, Any]],
        total_amount: float,
    ) -> str:
        lines = [
            f"# Invoice Draft: {client_name}",
            "",
            f"- Date: {invoice_date}",
            "",
            "## Line Items",
        ]
        for item in line_items:
            lines.append(
                f"- {item['description']} ({item['category']}): {item['quantity']:g} x {item['unit_price']:g} = {item['total']:.2f}"
            )
        lines.extend(
            [
                "",
                f"## Total Amount Due",
                f"{total_amount:.2f}",
                "",
                "## Notes",
                "This draft reflects additional completed work identified through the configured scope review process.",
            ]
        )
        return "\n".join(lines)
