from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class CreepEvent:
    event_id: str
    client_id: str
    work_item_id: str
    event_type: str
    normalized_category: str
    source_type: str
    source_reference: str | None
    source_excerpt: str | None
    reason: str
    scope_reference_id: str | None
    rule_code: str
    agreed_allowance: float | None
    actual_delivered_amount: float | None
    exceeded_amount: float | None
    billing_rule_applied: str | None
    revenue_impact_calculation: str
    system_explanation: str
    client_explanation: str
    billable_hours: float | None
    billable_quantity: float | None
    billable_unit: str | None
    rate: float | None
    estimated_amount: float | None
    currency: str | None

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["id"] = self.event_id
        return payload
