from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class InvoiceItem:
    id: str
    client_id: str
    event_id: str
    description: str
    quantity: float
    unit: str
    rate: float | None
    amount: float | None
    currency: str
    status: str = "draft"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
