from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any


class BillingAdapter(ABC):
    @abstractmethod
    def prepare_billing_package(
        self,
        client_config: dict[str, Any],
        invoice_artifacts: dict[str, Any],
        compensation: dict[str, Any],
        invoice_file_refs: dict[str, str],
    ) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def write(
        self,
        output_dir: str | Path,
        client_slug: str,
        package: dict[str, Any],
    ) -> dict[str, str]:
        raise NotImplementedError

    @abstractmethod
    def healthcheck(self, client_config: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError
