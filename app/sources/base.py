from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from app.models.source_inputs import ScopeInput, WorkActivityInput


class SourceAdapter(ABC):
    @abstractmethod
    def fetch_scope_inputs(self, client_config: dict[str, Any]) -> ScopeInput:
        raise NotImplementedError

    @abstractmethod
    def fetch_work_activity_inputs(self, client_config: dict[str, Any]) -> WorkActivityInput:
        raise NotImplementedError

    @abstractmethod
    def healthcheck(self, client_config: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError


@dataclass
class RawMessage:
    id: str
    text: str
    channel: str
    source_type: str
    source_reference: str
    performed_on: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ClassifiedMessage:
    raw: RawMessage
    is_scope_signal: bool
    confidence: str
    excerpt: str
    classification_method: str


class MessageSourceAdapter(ABC):
    """Abstract adapter for fetching and converting channel messages into work items."""

    @abstractmethod
    def fetch_messages(
        self,
        client_config: dict[str, Any],
        since: str | None = None,
    ) -> list[RawMessage]:
        raise NotImplementedError

    @abstractmethod
    def to_work_items(self, messages: list[ClassifiedMessage]) -> list[dict[str, Any]]:
        raise NotImplementedError

    @abstractmethod
    def healthcheck(self, client_config: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError
