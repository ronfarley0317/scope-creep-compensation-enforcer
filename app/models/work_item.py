from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class WorkItem:
    id: str
    deliverable_hint: str | None
    category: str
    description: str
    hours: float
    source_type: str = "task"
    source_reference: str | None = None
    source_excerpt: str | None = None
    quantity: float | None = None
    quantity_unit: str | None = None
    section_count: float | None = None
    revision_number: int | None = None
    performed_on: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
