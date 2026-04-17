from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Sequence

from app.workflows.run_all_clients import run_all_clients
from app.workflows.run_single_client import run_single_client


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    configs_root = Path(args.configs_root)

    if args.all_clients:
        return _run_all_clients(configs_root)

    client_key = args.client or "demo-client"
    return _run_single_client(configs_root, client_key)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run Scope Creep Enforcer for one client or all configured clients."
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--client", help="Client key under configs/clients/, for example demo-client.")
    group.add_argument("--all-clients", action="store_true", help="Run every client under configs/clients/.")
    parser.add_argument(
        "--configs-root",
        default="configs/clients",
        help="Root directory containing client configuration folders.",
    )
    return parser


def _run_single_client(configs_root: Path, client_key: str) -> int:
    client_dir = configs_root / client_key
    if not client_dir.exists():
        print(f"Client config not found: {client_dir}", file=sys.stderr)
        return 1

    result = run_single_client(client_dir)
    print(result["terminal_summary"])
    return 0


def _run_all_clients(configs_root: Path) -> int:
    if not configs_root.exists():
        print(f"Configs root not found: {configs_root}", file=sys.stderr)
        return 1

    client_dirs = [path for path in configs_root.iterdir() if path.is_dir() and (path / "client.yaml").exists()]
    if not client_dirs:
        print(f"No client configs found under: {configs_root}", file=sys.stderr)
        return 1

    try:
        result = run_all_clients(configs_root)
    except Exception as exc:
        print(f"Batch initialization failed: {exc}", file=sys.stderr)
        return 1

    print(build_batch_terminal_summary(result))
    return 0


def build_batch_terminal_summary(result: dict) -> str:
    failed_names = [
        item["client_name"] for item in result["per_client_results"] if item["status"] != "success"
    ]
    lines = [
        f"Batch: {result['batch_id']}",
        f"Clients attempted: {result['total_clients_attempted']}",
        f"Clients succeeded: {result['total_clients_succeeded']}",
        f"Clients failed: {result['total_clients_failed']}",
        f"Batch summary: {result['output_paths']['batch_summary_markdown']}",
    ]
    if failed_names:
        lines.append(f"Failed clients: {', '.join(failed_names)}")
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
