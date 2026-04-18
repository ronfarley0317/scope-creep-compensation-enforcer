from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.services.config_loader import load_yaml


def build_status_report(configs_root: Path) -> str:
    """Return a terminal status table covering all configured clients."""
    client_dirs = sorted(
        p for p in configs_root.iterdir()
        if p.is_dir() and (p / "config" / "client.yaml").exists()
    )
    if not client_dirs:
        return f"No clients found under {configs_root}"

    rows: list[dict[str, Any]] = []
    for client_dir in client_dirs:
        rows.append(_client_row(client_dir))

    return _render(rows)


def _client_row(client_dir: Path) -> dict[str, Any]:
    try:
        cfg = load_yaml(client_dir / "config" / "client.yaml")
    except Exception:
        return {"id": client_dir.name, "name": "?", "error": "config parse error"}

    client_id = cfg.get("client_id", client_dir.name)
    client_name = cfg.get("client_name", client_id)
    work_source = cfg.get("work_source_type", "local_fixture")
    message_sources: list[str] = cfg.get("message_source_types", [])
    channels = ", ".join(message_sources) if message_sources else "none"

    last_run, last_run_creep = _last_run_info(client_dir)
    pending = _pending_approvals(client_dir)

    return {
        "id": client_id,
        "name": client_name,
        "work_source": work_source,
        "channels": channels,
        "last_run": last_run,
        "creep_events": last_run_creep,
        "pending_approvals": pending,
    }


def _last_run_info(client_dir: Path) -> tuple[str, str]:
    runs_dir = client_dir / "runs"
    if not runs_dir.exists():
        return "never", "-"
    run_dirs = sorted(
        [d for d in runs_dir.iterdir() if d.is_dir()],
        key=lambda d: d.name,
    )
    if not run_dirs:
        return "never", "-"
    latest = run_dirs[-1]
    summary_path = latest / "run_summary.json"
    if not summary_path.exists():
        return latest.name[:19], "-"
    try:
        data = json.loads(summary_path.read_text(encoding="utf-8"))
        run_id: str = data.get("run_id", latest.name)
        # Extract date portion: run-YYYYMMDD-HHMMSS-xxxxxxxx
        parts = run_id.split("-")
        if len(parts) >= 3:
            date_str = parts[1]
            ts = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"
        else:
            ts = run_id[:10]
        creep_count = str(len(data.get("scope_creep_events", [])))
        return ts, creep_count
    except Exception:
        return latest.name[:19], "-"


def _pending_approvals(client_dir: Path) -> int:
    store_path = client_dir / "state" / "pending_approvals.json"
    if not store_path.exists():
        return 0
    try:
        data = json.loads(store_path.read_text(encoding="utf-8"))
        return sum(1 for v in data.values() if v.get("status") == "pending")
    except Exception:
        return 0


def _render(rows: list[dict[str, Any]]) -> str:
    now = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    header_parts = [
        f"Scope Creep Enforcer — Status as of {now}",
        "",
    ]

    col_client = max(len(r.get("name", r["id"])) for r in rows)
    col_client = max(col_client, 10)
    col_work = max(len(r.get("work_source", "")) for r in rows)
    col_work = max(col_work, 11)
    col_channels = max(len(r.get("channels", "")) for r in rows)
    col_channels = max(col_channels, 8)

    def row_line(name: str, work: str, channels: str, last: str, creep: str, pending: str) -> str:
        return (
            f"  {name:<{col_client}}  {work:<{col_work}}  "
            f"{channels:<{col_channels}}  {last:<10}  {creep:>6}  {pending:>7}"
        )

    sep = "  " + "-" * (col_client + col_work + col_channels + 37)
    header_parts.append(
        row_line("Client", "Work Source", "Channels", "Last Run", "Creep", "Pending")
    )
    header_parts.append(sep)

    for r in rows:
        if "error" in r:
            header_parts.append(f"  {r['id']}  (error: {r['error']})")
            continue
        header_parts.append(row_line(
            r["name"],
            r["work_source"],
            r["channels"],
            r["last_run"],
            r["creep_events"],
            str(r["pending_approvals"]) if r["pending_approvals"] else "-",
        ))

    header_parts.append("")
    return "\n".join(header_parts)
