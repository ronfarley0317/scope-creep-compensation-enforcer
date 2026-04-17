from __future__ import annotations

from pathlib import Path
from typing import Any

from app.services.scope_normalizer import ScopeNormalizer


class ContractParserError(ValueError):
    """Raised when a structured SOW fixture is malformed."""


class ContractParser:
    """Parse a structured markdown SOW into raw sections or normalized contract scope."""

    def parse_raw_file(self, contract_path: str | Path) -> dict[str, Any]:
        path = Path(contract_path)
        return self.parse_raw_text(path.read_text(encoding="utf-8"))

    def parse_raw_text(self, content: str) -> dict[str, Any]:
        metadata: dict[str, str] = {}
        sections: dict[str, list[dict[str, Any]] | list[str]] = {}
        current_section: str | None = None

        for raw_line in content.splitlines():
            line = raw_line.rstrip()
            if not line.strip():
                continue
            if line.startswith("# "):
                continue
            if line.startswith("## "):
                current_section = line[3:].strip().lower()
                sections.setdefault(current_section, [])
                continue
            if current_section is None:
                key, value = self._split_key_value(line)
                metadata[key.lower()] = value
                continue

            if line.startswith("- "):
                value = line[2:].strip()
                if ":" in value:
                    key, raw_value = self._split_key_value(value)
                    sections[current_section].append({key: raw_value})
                else:
                    sections[current_section].append(value)
                continue

            if not sections[current_section]:
                raise ContractParserError(f"Section item missing leading bullet in section '{current_section}'.")

            current_items = sections[current_section]
            if isinstance(current_items[-1], str):
                raise ContractParserError(f"Unexpected mapping detail line in simple list section '{current_section}'.")
            key, value = self._split_key_value(line.strip())
            current_items[-1][key] = value

        return {"metadata": metadata, "sections": sections}

    def parse_file(
        self,
        contract_path: str | Path,
        *,
        client_config: dict[str, Any] | None = None,
        contract_rules: dict[str, Any] | None = None,
        field_mapping: dict[str, Any] | None = None,
    ) -> Any:
        raw_contract = self.parse_raw_file(contract_path)
        if client_config is None or contract_rules is None or field_mapping is None:
            client_config = {
                "client_id": raw_contract["metadata"].get("client id", "unknown-client"),
                "client_name": raw_contract["metadata"].get("client name", "Unknown Client"),
                "currency": raw_contract["metadata"].get("currency", "USD"),
            }
            contract_rules = self._build_legacy_rules(raw_contract)
            field_mapping = self._legacy_field_mapping()
        normalizer = ScopeNormalizer(client_config, contract_rules, field_mapping)
        return normalizer.normalize_contract(raw_contract)

    def _build_legacy_rules(self, raw_contract: dict[str, Any]) -> dict[str, Any]:
        sections = raw_contract["sections"]
        deliverables = []
        for item in sections.get("deliverables", []) or sections.get("included scope", []):
            if not isinstance(item, dict):
                continue
            deliverables.append(
                {
                    "id": item.get("id", item.get("deliverable_id")),
                    "name": item["name"],
                    "included_quantity": item.get("included_quantity"),
                    "included_hours": item.get("included_hours"),
                    "included_revisions": item.get("included_revisions"),
                    "unit": item.get("unit", "item"),
                    "task_categories": [
                        category.strip()
                        for category in str(item.get("task_categories", "")).split(",")
                        if category.strip()
                    ],
                    "notes": item.get("notes", ""),
                }
            )

        limits = []
        for item in sections.get("limits", []):
            if not isinstance(item, dict):
                continue
            limits.append(
                {
                    "id": item.get("id", item.get("limit_id")),
                    "type": item.get("type", item.get("limit_type")),
                    "applies_to": [
                        part.strip()
                        for part in str(item.get("deliverable_id", item.get("applies_to", ""))).split(",")
                        if part.strip()
                    ],
                    "included_quantity": item.get("value", item.get("included_quantity")),
                    "unit": item["unit"],
                    "notes": item.get("description", item.get("notes", "")),
                }
            )

        billing_rules = []
        for item in sections.get("billing rules", []) or sections.get("overage pricing", []):
            if not isinstance(item, dict):
                continue
            billing_rules.append(
                {
                    "id": item.get("id", item.get("rule_id")),
                    "trigger": item.get("rule_type", item.get("trigger")),
                    "amount": item.get("rate", item.get("amount")),
                    "unit": item.get("unit"),
                    "notes": item.get("description", item.get("notes", "")),
                    "billing_type": "flat_fee",
                    "applies_to": [],
                }
            )

        return {
            "currency": raw_contract["metadata"].get("currency", "USD"),
            "scope": {
                "deliverables": deliverables,
                "limits": limits,
                "billing_rules": billing_rules,
                "exclusions": sections.get("exclusions", []),
            },
            "assumptions": sections.get("assumptions", []),
            "interpretation": {
                "revision_limit_type": "included_revisions",
                "revision_billing_trigger": "revision_overage_hourly",
                "quantity_trigger_by_unit": {"item": "extra_deliverable_quantity", "section": "extra_section"},
                "out_of_scope_trigger": "out_of_scope_hourly",
            },
        }

    def _legacy_field_mapping(self) -> dict[str, Any]:
        return {
            "sow_mapping": {
                "deliverables_section": "deliverables",
                "deliverable_fields": {
                    "id": ["id", "deliverable_id"],
                    "extra_quantity_fields": {"section": "included_sections"},
                },
            },
            "work_item_mapping": {
                "work_item_id": "id",
                "work_date": "performed_on",
                "task_category": "category",
                "deliverable_hint": "deliverable_hint",
                "description": "description",
                "hours": "hours",
                "revision_count": "revision_number",
            },
            "quantity_mapping": {
                "by_category": {
                    "landing_page": {"field": "section_count", "unit": "section"},
                }
            },
            "normalization_rules": {
                "deliverable_aliases": {},
                "category_aliases": {},
                "quantity_defaults": {},
            },
        }

    def _split_key_value(self, line: str) -> tuple[str, str]:
        if ":" not in line:
            raise ContractParserError(f"Expected key/value pair, got: {line}")
        key, value = line.split(":", 1)
        return key.strip(), value.strip()
