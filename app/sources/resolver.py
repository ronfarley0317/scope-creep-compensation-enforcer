from __future__ import annotations

from typing import Any

from app.sources.asana_comments_adapter import AsanaCommentsAdapter
from app.sources.asana_work_adapter import AsanaWorkAdapter
from app.sources.base import MessageSourceAdapter, SourceAdapter
from app.sources.billing_base import BillingAdapter
from app.sources.gmail_adapter import GmailMessageAdapter
from app.sources.local_fixture_adapter import LocalFixtureAdapter
from app.sources.manual_billing_adapter import ManualBillingAdapter
from app.sources.outlook_adapter import OutlookMessageAdapter
from app.sources.slack_adapter import SlackMessageAdapter


class SourceResolver:
    def __init__(self) -> None:
        self._source_registry: dict[str, type[SourceAdapter]] = {
            "local_fixture": LocalFixtureAdapter,
            "asana": AsanaWorkAdapter,
        }
        self._billing_registry: dict[str, type[BillingAdapter]] = {
            "manual": ManualBillingAdapter,
        }
        self._message_registry: dict[str, type[MessageSourceAdapter]] = {
            "slack": SlackMessageAdapter,
            "gmail": GmailMessageAdapter,
            "outlook": OutlookMessageAdapter,
            "asana_comment": AsanaCommentsAdapter,
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

    def resolve_message_adapters(self, client_config: dict[str, Any]) -> list[MessageSourceAdapter]:
        """Return one adapter per configured message_source_type. Unknown types are skipped."""
        types: list[str] = client_config.get("message_source_types", [])
        adapters = []
        for source_type in types:
            adapter_cls = self._message_registry.get(source_type)
            if adapter_cls is None:
                raise ValueError(f"Unsupported message adapter type: {source_type!r}")
            adapters.append(adapter_cls())
        return adapters

    def _build_adapter(self, source_type: str) -> SourceAdapter:
        adapter_cls = self._source_registry.get(source_type)
        if adapter_cls is None:
            raise ValueError(f"Unsupported source adapter type: {source_type}")
        return adapter_cls()
