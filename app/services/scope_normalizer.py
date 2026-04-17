from __future__ import annotations

from typing import Any

from app.models.contract import BillingRule, ContractScope, Deliverable, ScopeLimit
from app.models.source_inputs import ScopeInput, WorkActivityInput
from app.models.work_item import WorkItem


class ScopeNormalizer:
    """Normalize raw SOW and work log data into the internal standard schema."""

    def __init__(
        self,
        client_config: dict[str, Any],
        contract_rules: dict[str, Any],
        field_mapping: dict[str, Any],
    ) -> None:
        self.client_config = client_config
        self.contract_rules = contract_rules
        self.field_mapping = field_mapping
        self.unit_aliases = self.field_mapping.get("normalization_rules", {}).get("unit_aliases", {})
        self.field_aliases = self.field_mapping.get("field_aliases", {})

    def normalize_contract(self, scope_input: ScopeInput | dict[str, Any]) -> ContractScope:
        raw_contract = scope_input.payload if isinstance(scope_input, ScopeInput) else scope_input
        metadata = raw_contract.get("metadata", {})
        sections = raw_contract.get("sections", {})
        sow_mapping = self.field_mapping.get("sow_mapping", {})
        deliverable_section = sow_mapping.get("deliverables_section", "included scope").lower()
        raw_deliverables = sections.get(deliverable_section, [])
        raw_by_id = {
            self._pick(item, sow_mapping.get("deliverable_fields", {}).get("id", ["deliverable_id", "id"])): item
            for item in raw_deliverables
        }

        deliverables: list[Deliverable] = []
        for rule in self.contract_rules.get("scope", {}).get("deliverables", []):
            raw_match = raw_by_id.get(rule["id"], {})
            task_categories = tuple(rule.get("task_categories", ()))
            quantity_limits: dict[str, float] = {}
            unit = rule.get("unit")
            if rule.get("included_quantity") is not None and unit:
                quantity_limits[self._normalize_unit(str(unit))] = float(rule["included_quantity"])
            if raw_match:
                extra_quantity_fields = sow_mapping.get("deliverable_fields", {}).get(
                    "extra_quantity_fields", {"section": "included_sections"}
                )
                for quantity_unit, source_field in extra_quantity_fields.items():
                    raw_value = self._extract(raw_match, source_field)
                    if raw_value not in (None, ""):
                        quantity_limits[self._normalize_unit(quantity_unit)] = float(raw_value)

            deliverables.append(
                Deliverable(
                    id=rule["id"],
                    name=rule["name"],
                    task_categories=task_categories,
                    included_quantity=float(rule["included_quantity"]) if rule.get("included_quantity") is not None else None,
                    included_sections=quantity_limits.get("section"),
                    included_hours=float(rule["included_hours"]) if rule.get("included_hours") is not None else None,
                    included_revisions=int(rule["included_revisions"]) if rule.get("included_revisions") is not None else None,
                    notes=raw_match.get("notes", rule.get("notes", "")),
                    quantity_limits=quantity_limits,
                )
            )

        limits = [
            ScopeLimit(
                id=rule["id"],
                limit_type=rule["type"],
                deliverable_id=",".join(rule.get("applies_to", [])),
                value=float(rule["included_quantity"]),
                unit=rule["unit"],
                description=rule.get("notes", ""),
                applies_to=tuple(rule.get("applies_to", [])),
            )
            for rule in self.contract_rules.get("scope", {}).get("limits", [])
        ]

        billing_rules = [
            BillingRule(
                id=rule["id"],
                rule_type=rule["trigger"],
                trigger=rule["trigger"],
                rate=float(rule["amount"]) if rule.get("amount") is not None else None,
                unit=rule.get("unit"),
                currency=self.contract_rules.get("currency", self.client_config.get("currency", "USD")),
                description=rule.get("notes", ""),
                billing_type=rule.get("billing_type", "flat_fee"),
                applies_to=tuple(rule.get("applies_to", [])),
            )
            for rule in self.contract_rules.get("scope", {}).get("billing_rules", [])
        ]

        return ContractScope(
            client_id=str(metadata.get("client id", self.client_config["client_id"])),
            client_name=str(metadata.get("client name", self.client_config["client_name"])),
            currency=str(metadata.get("currency", self.client_config.get("currency", "USD"))),
            deliverables=tuple(deliverables),
            limits=tuple(limits),
            billing_rules=tuple(billing_rules),
            exclusions=tuple(self.contract_rules.get("scope", {}).get("exclusions", [])),
            assumptions=tuple(self.contract_rules.get("assumptions", [])),
            interpretation=self.contract_rules.get("interpretation", {}),
        )

    def normalize_work_log_from_dicts(self, raw_items: list[dict[str, Any]]) -> list[WorkItem]:
        """Normalize a list of pre-built work item dicts (e.g. from message adapters)."""
        fake_payload: dict[str, Any] = {"work_items": raw_items}
        return self.normalize_work_log(fake_payload)

    def normalize_work_log(self, work_activity_input: WorkActivityInput | dict[str, Any]) -> list[WorkItem]:
        raw_work_log = (
            work_activity_input.payload
            if isinstance(work_activity_input, WorkActivityInput)
            else work_activity_input
        )
        mapping = self.field_mapping.get("work_item_mapping", self.field_mapping.get("field_mapping", {}))
        quantity_mapping = self.field_mapping.get("quantity_mapping", {})
        normalization_rules = self.field_mapping.get("normalization_rules", {})

        work_items: list[WorkItem] = []
        for raw_item in raw_work_log.get("work_items", []):
            raw_category = self._extract(raw_item, mapping.get("task_category", "category"))
            category = self._normalize_alias(raw_category, normalization_rules.get("category_aliases", {}))
            raw_deliverable = self._extract(raw_item, mapping.get("deliverable_hint", "deliverable_hint"))
            deliverable_hint = self._normalize_alias(
                raw_deliverable, normalization_rules.get("deliverable_aliases", {})
            )
            quantity_value, quantity_unit = self._normalize_quantity(raw_item, category, quantity_mapping)
            revision_count = self._extract(raw_item, mapping.get("revision_count", mapping.get("revision_number", "revision_number")))

            work_items.append(
                WorkItem(
                    id=str(self._extract(raw_item, mapping.get("work_item_id", "id"))),
                    deliverable_hint=deliverable_hint,
                    category=category,
                    description=str(self._extract(raw_item, mapping.get("description", "description"), "")),
                    hours=float(self._extract(raw_item, mapping.get("hours", "hours"), 0.0)),
                    source_type=str(self._extract(raw_item, "source_type", "task")),
                    source_reference=str(
                        self._extract(raw_item, "source_reference", self._extract(raw_item, mapping.get("work_item_id", "id")))
                    ),
                    source_excerpt=self._build_source_excerpt(raw_item, mapping),
                    quantity=quantity_value,
                    quantity_unit=quantity_unit,
                    revision_number=int(revision_count) if revision_count not in (None, "") else None,
                    performed_on=self._extract(raw_item, mapping.get("work_date", "performed_on")),
                )
            )
        return work_items

    def _normalize_quantity(
        self, raw_item: dict[str, Any], category: str, quantity_mapping: dict[str, Any]
    ) -> tuple[float | None, str | None]:
        by_category = quantity_mapping.get("by_category", {})
        category_rule = by_category.get(category, {})
        if category_rule:
            raw_value = self._extract(raw_item, category_rule.get("field", "assets"))
            if raw_value not in (None, ""):
                return float(raw_value), self._normalize_unit(category_rule.get("unit"))
        defaults = self.field_mapping.get("normalization_rules", {}).get("quantity_defaults", {})
        if category in defaults:
            return float(defaults[category]), self._normalize_unit(category_rule.get("unit"))
        return None, None

    def _extract(self, payload: dict[str, Any], field_name: str | list[str] | None, default: Any = None) -> Any:
        candidates = self._field_candidates(field_name)
        if not candidates:
            return default
        for candidate in candidates:
            if payload.get(candidate) not in (None, ""):
                return payload[candidate]
        return default

    def _pick(self, payload: dict[str, Any], field_names: list[str] | str) -> str:
        for name in self._field_candidates(field_names):
            if payload.get(name) not in (None, ""):
                return str(payload[name])
        return ""

    def _normalize_alias(self, value: Any, alias_map: dict[str, list[str]]) -> str | None:
        if value in (None, ""):
            return None
        normalized = str(value).strip().lower()
        for canonical, aliases in alias_map.items():
            candidates = {canonical.lower(), *(item.lower() for item in aliases)}
            if normalized in candidates:
                return canonical
        return normalized.replace(" ", "_")

    def _normalize_unit(self, value: str | None) -> str | None:
        if value in (None, ""):
            return None
        normalized = str(value).strip().lower()
        for canonical, aliases in self.unit_aliases.items():
            candidates = {canonical.lower(), *(item.lower() for item in aliases)}
            if normalized in candidates:
                return canonical
        return normalized

    def _field_candidates(self, field_name: str | list[str] | None) -> list[str]:
        if field_name in (None, ""):
            return []
        if isinstance(field_name, list):
            candidates: list[str] = []
            for item in field_name:
                candidates.extend(self._field_candidates(item))
            return candidates
        if field_name in self.field_aliases:
            alias_value = self.field_aliases[field_name]
            if isinstance(alias_value, list):
                return [str(item) for item in alias_value]
            return [str(alias_value)]
        return [str(field_name)]

    def _build_source_excerpt(self, raw_item: dict[str, Any], mapping: dict[str, Any]) -> str | None:
        excerpt = self._extract(raw_item, "source_excerpt")
        if excerpt not in (None, ""):
            return str(excerpt).strip()
        description = self._extract(raw_item, mapping.get("description", "description"), "")
        if description in (None, ""):
            return None
        snippet = str(description).strip()
        return snippet[:160]
