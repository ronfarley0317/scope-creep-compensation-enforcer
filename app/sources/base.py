from __future__ import annotations

from abc import ABC, abstractmethod
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
