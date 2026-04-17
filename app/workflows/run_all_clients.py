from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.services.config_loader import load_yaml
from app.workflows.run_single_client import run_single_client


def run_all_clients(configs_root: str | Path = Path("clients")) -> dict[str, Any]:
    base_path = Path(configs_root)
    client_dirs = _discover_client_dirs(base_path)
    batch_id = _generate_batch_id()
    started_at = datetime.now()
    per_client_results: list[dict[str, Any]] = []

    for client_dir in client_dirs:
        client_stub = _load_client_stub(client_dir)
        run_history_dir = _resolve_run_history_dir(client_dir, client_stub)
        before = _history_snapshot(run_history_dir)

        try:
            result = run_single_client(client_dir)
            per_client_results.append(
                {
                    "client_name": result["client"]["client_name"],
                    "run_id": result["run_id"],
                    "status": "success",
                    "total_scope_creep_events": len(result["comparison"]["creep_events"]),
                    "total_billable_impact": float(
                        result["comparison"]["revenue_impact_estimate"]["estimated_amount"] or 0.0
                    ),
                }
            )
        except Exception:
            run_history = _read_new_run_history(run_history_dir, before)
            per_client_results.append(
                {
                    "client_name": run_history.get("client_name", client_stub.get("client_name", client_dir.name)),
                    "run_id": run_history.get("run_id", "unknown"),
                    "status": run_history.get("status", "failure"),
                    "total_scope_creep_events": int(run_history.get("total_scope_creep_events", 0)),
                    "total_billable_impact": float(run_history.get("total_billable_impact", 0.0)),
                }
            )

    completed_at = datetime.now()
    total_succeeded = sum(1 for item in per_client_results if item["status"] == "success")
    total_failed = sum(1 for item in per_client_results if item["status"] != "success")
    summary = {
        "batch_id": batch_id,
        "started_at": started_at.isoformat(timespec="seconds"),
        "completed_at": completed_at.isoformat(timespec="seconds"),
        "total_clients_attempted": len(client_dirs),
        "total_clients_succeeded": total_succeeded,
        "total_clients_failed": total_failed,
        "per_client_results": per_client_results,
    }
    batch_paths = _write_batch_outputs(_batch_output_dir(base_path), summary)
    summary["output_paths"] = batch_paths
    return summary


def main() -> None:
    result = run_all_clients(Path("clients"))
    print(result["output_paths"]["batch_summary_markdown"])


def _discover_client_dirs(configs_root: Path) -> list[Path]:
    if not configs_root.exists():
        return []
    discovered: list[Path] = []
    for path in configs_root.iterdir():
        if not path.is_dir():
            continue
        if (path / "config" / "client.yaml").exists():
            discovered.append(path)
            continue
        if (path / "client.yaml").exists():
            discovered.append(path)
    return sorted(discovered)


def _load_client_stub(client_dir: Path) -> dict[str, Any]:
    client_yaml = client_dir / "config" / "client.yaml"
    if not client_yaml.exists():
        client_yaml = client_dir / "client.yaml"
    if not client_yaml.exists():
        return {}
    return load_yaml(client_yaml)


def _resolve_run_history_dir(client_dir: Path, client_stub: dict[str, Any]) -> Path:
    return client_dir / "runs"


def _history_snapshot(run_history_dir: Path) -> set[str]:
    if not run_history_dir.exists():
        return set()
    return {
        str(path.relative_to(run_history_dir))
        for path in run_history_dir.glob("*/run_metadata.json")
    }


def _read_new_run_history(run_history_dir: Path, before: set[str]) -> dict[str, Any]:
    if not run_history_dir.exists():
        return {}
    candidates = [
        path
        for path in run_history_dir.glob("*/run_metadata.json")
        if str(path.relative_to(run_history_dir)) not in before
    ]
    if not candidates:
        candidates = list(run_history_dir.glob("*/run_metadata.json"))
    if not candidates:
        return {}
    latest = max(candidates, key=lambda path: path.stat().st_mtime)
    return json.loads(latest.read_text(encoding="utf-8"))


def _batch_output_dir(configs_root: Path) -> Path:
    return _workspace_root_from_configs(configs_root) / "outputs" / "batches"


def _workspace_root_from_configs(configs_root: Path) -> Path:
    resolved = configs_root.resolve()
    if resolved.name == "clients":
        return resolved.parent
    if resolved.name == "clients" and resolved.parent.name == "configs":
        return resolved.parent.parent
    return Path.cwd().resolve()


def _generate_batch_id() -> str:
    return f"batch-{datetime.now().strftime('%Y%m%d%H%M%S')}-{uuid4().hex[:8]}"


def _write_batch_outputs(output_dir: Path, summary: dict[str, Any]) -> dict[str, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / f"{summary['batch_id']}-summary.json"
    markdown_path = output_dir / f"{summary['batch_id']}-summary.md"
    json_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    markdown_path.write_text(_build_batch_markdown(summary), encoding="utf-8")
    return {
        "batch_summary_json": str(json_path),
        "batch_summary_markdown": str(markdown_path),
    }


def _build_batch_markdown(summary: dict[str, Any]) -> str:
    lines = [
        f"# Batch Summary: {summary['batch_id']}",
        "",
        f"- Started at: {summary['started_at']}",
        f"- Completed at: {summary['completed_at']}",
        f"- Clients attempted: {summary['total_clients_attempted']}",
        f"- Clients succeeded: {summary['total_clients_succeeded']}",
        f"- Clients failed: {summary['total_clients_failed']}",
        "",
        "## Per-Client Results",
    ]
    for item in summary["per_client_results"]:
        lines.extend(
            [
                f"### {item['client_name']}",
                f"- Run ID: {item['run_id']}",
                f"- Status: {item['status']}",
                f"- Scope-creep events: {item['total_scope_creep_events']}",
                f"- Total billable impact: {item['total_billable_impact']:.2f}",
                "",
            ]
        )
    return "\n".join(lines)


def _resolve_path(base_path: Path, value: str) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    if path.exists():
        return path.resolve()
    nested = base_path / path
    if nested.exists():
        return nested.resolve()
    return path.resolve()


if __name__ == "__main__":
    main()
