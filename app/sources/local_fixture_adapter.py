from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from app.models.source_inputs import ScopeInput, WorkActivityInput
from app.services.contract_parser import ContractParser
from app.sources.base import SourceAdapter


class LocalFixtureAdapter(SourceAdapter):
    def fetch_scope_inputs(self, client_config: dict[str, Any]) -> ScopeInput:
        base_path = self._base_path(client_config)
        scope_path = self._resolve_path(base_path, client_config["sample_sow_path"])
        payload = ContractParser().parse_raw_file(scope_path)
        return ScopeInput(
            source_type="local_fixture",
            source_reference=str(scope_path),
            payload=payload,
        )

    def fetch_work_activity_inputs(self, client_config: dict[str, Any]) -> WorkActivityInput:
        base_path = self._base_path(client_config)
        work_path = self._resolve_path(base_path, client_config["sample_work_log_path"])
        payload = self._read_work_payload(work_path)
        return WorkActivityInput(
            source_type="local_fixture",
            source_reference=str(work_path),
            payload=payload,
        )

    def healthcheck(self, client_config: dict[str, Any]) -> dict[str, Any]:
        base_path = self._base_path(client_config)
        scope_path_value = client_config.get("sample_sow_path")
        work_path_value = client_config.get("sample_work_log_path")
        scope_path = self._resolve_path(base_path, scope_path_value) if scope_path_value else None
        work_path = self._resolve_path(base_path, work_path_value) if work_path_value else None
        scope_available = scope_path.exists() if scope_path else None
        work_available = work_path.exists() if work_path else None
        healthy_checks = [value for value in (scope_available, work_available) if value is not None]
        return {
            "adapter": "local_fixture",
            "scope_available": scope_available,
            "work_available": work_available,
            "scope_reference": str(scope_path) if scope_path else None,
            "work_reference": str(work_path) if work_path else None,
            "healthy": all(healthy_checks) if healthy_checks else False,
        }

    def _base_path(self, client_config: dict[str, Any]) -> Path:
        return Path(client_config.get("_client_dir", "."))

    def _resolve_path(self, base_path: Path, value: str) -> Path:
        path = Path(value)
        if path.is_absolute():
            return path
        if path.exists():
            return path.resolve()
        nested = base_path / path
        if nested.exists():
            return nested.resolve()
        return path.resolve()

    def _read_work_payload(self, work_path: Path) -> dict[str, Any]:
        suffix = work_path.suffix.lower()
        if suffix == ".csv":
            return self._read_csv_work_log(work_path)
        return json.loads(work_path.read_text(encoding="utf-8"))

    def _read_csv_work_log(self, work_path: Path) -> dict[str, Any]:
        with work_path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            work_items = [
                {key: value for key, value in row.items() if value not in (None, "")}
                for row in reader
            ]
        return {"work_items": work_items}
