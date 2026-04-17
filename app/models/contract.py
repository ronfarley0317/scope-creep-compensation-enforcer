from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class Deliverable:
    id: str
    name: str
    task_categories: tuple[str, ...] = field(default_factory=tuple)
    quantity_limits: dict[str, float] = field(default_factory=dict)
    included_quantity: float | None = None
    included_sections: float | None = None
    included_hours: float | None = None
    included_revisions: int | None = None
    notes: str = ""

    def matches(self, deliverable_hint: str | None, category: str) -> bool:
        normalized_hint = (deliverable_hint or "").strip().lower()
        normalized_name = self.name.strip().lower()
        normalized_id = self.id.strip().lower()
        normalized_categories = {item.strip().lower() for item in self.task_categories}
        return (
            normalized_hint in {normalized_id, normalized_name}
            or bool(category and category.strip().lower() in normalized_categories)
        )


@dataclass(frozen=True)
class ScopeLimit:
    id: str
    limit_type: str
    deliverable_id: str | None
    value: float
    unit: str
    description: str = ""
    applies_to: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class BillingRule:
    id: str
    rule_type: str
    trigger: str
    rate: float | None
    unit: str | None
    currency: str
    description: str = ""
    billing_type: str = "flat_fee"
    applies_to: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class ContractScope:
    client_id: str
    client_name: str
    currency: str
    deliverables: tuple[Deliverable, ...]
    limits: tuple[ScopeLimit, ...] = field(default_factory=tuple)
    billing_rules: tuple[BillingRule, ...] = field(default_factory=tuple)
    exclusions: tuple[str, ...] = field(default_factory=tuple)
    assumptions: tuple[str, ...] = field(default_factory=tuple)
    interpretation: dict[str, Any] = field(default_factory=dict)

    def get_deliverable(self, work_deliverable_hint: str | None, category: str) -> Deliverable | None:
        for deliverable in self.deliverables:
            if deliverable.matches(work_deliverable_hint, category):
                return deliverable
        return None

    def get_limit(self, deliverable_id: str, limit_type: str) -> ScopeLimit | None:
        for limit in self.limits:
            if limit.limit_type != limit_type:
                continue
            if limit.deliverable_id == deliverable_id or deliverable_id in limit.applies_to:
                return limit
        return None

    def get_billing_rule(self, rule_type: str, deliverable_id: str | None = None) -> BillingRule | None:
        for rule in self.billing_rules:
            if rule.rule_type != rule_type:
                continue
            if deliverable_id is None or not rule.applies_to or deliverable_id in rule.applies_to:
                return rule
        return None

    def is_excluded(self, work_text: str | None) -> bool:
        if not work_text:
            return False
        normalized = work_text.strip().lower()
        return any(item.strip().lower() == normalized for item in self.exclusions)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
