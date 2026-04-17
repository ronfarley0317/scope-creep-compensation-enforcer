from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class RunMetadata:
    run_id: str
    client_name: str
    started_at: str
    completed_at: str
    status: str
    scope_source_type: str
    work_source_type: str
    billing_source_type: str
    total_scope_creep_events: int
    total_billable_impact: float
    generated_artifacts: dict[str, str]
    error_message: str | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
