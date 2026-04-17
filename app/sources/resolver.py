from __future__ import annotations

from typing import Any

from app.sources.billing_base import BillingAdapter
from app.sources.asana_work_adapter import AsanaWorkAdapter
from app.sources.base import SourceAdapter
from app.sources.local_fixture_adapter import LocalFixtureAdapter
from app.sources.manual_billing_adapter import ManualBillingAdapter


class SourceResolver:
    def __init__(self) -> None:
        self._source_registry: dict[str, type[SourceAdapter]] = {
            "local_fixture": LocalFixtureAdapter,
            "asana": AsanaWorkAdapter,
        }
        self._billing_registry: dict[str, type[BillingAdapter]] = {
            "manual": ManualBillingAdapter,
        }

    def get_scope_source_type(self, client_config: dict[str, Any]) -> str:
        return client_config.get("scope_source_type", "local_fixture")

    def get_work_source_type(self, client_config: dict[str, Any]) -> str:
        return client_config.get("work_source_type", "local_fixture")

    def get_billing_source_type(self, client_config: dict[str, Any]) -> str:
        return client_config.get("billing_source_type", "manual")

    def resolve_scope_adapter(self, client_config: dict[str, Any]) -> SourceAdapter:
        source_type = self.get_scope_source_type(client_config)
        return self._build_adapter(source_type)

    def resolve_work_adapter(self, client_config: dict[str, Any]) -> SourceAdapter:
        source_type = self.get_work_source_type(client_config)
        return self._build_adapter(source_type)

    def resolve(self, client_config: dict[str, Any]) -> tuple[SourceAdapter, SourceAdapter]:
        return (
            self.resolve_scope_adapter(client_config),
            self.resolve_work_adapter(client_config),
        )

    def resolve_billing_adapter(self, client_config: dict[str, Any]) -> BillingAdapter:
        source_type = self.get_billing_source_type(client_config)
        adapter_cls = self._billing_registry.get(source_type)
        if adapter_cls is None:
            raise ValueError(f"Unsupported billing adapter type: {source_type}")
        return adapter_cls()

    def resolve_lanes(self, client_config: dict[str, Any]) -> dict[str, Any]:
        return {
            "scope_source_type": self.get_scope_source_type(client_config),
            "work_source_type": self.get_work_source_type(client_config),
            "billing_source_type": self.get_billing_source_type(client_config),
            "scope_adapter": self.resolve_scope_adapter(client_config),
            "work_adapter": self.resolve_work_adapter(client_config),
            "billing_adapter": self.resolve_billing_adapter(client_config),
        }

    def _build_adapter(self, source_type: str) -> SourceAdapter:
        adapter_cls = self._source_registry.get(source_type)
        if adapter_cls is None:
            raise ValueError(f"Unsupported source adapter type: {source_type}")
        return adapter_cls()
