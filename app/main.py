from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from typing import Sequence

from app.workflows.run_all_clients import run_all_clients
from app.workflows.run_single_client import run_single_client
from app.workflows.run_with_messages import run_client_with_messages, run_client_with_messages_loop


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    _configure_logging(json_logs=args.log_json)
    configs_root = Path(args.configs_root)

    if args.new_client:
        return _scaffold_new_client(args.new_client, configs_root)

    if args.validate_client:
        return _validate_client(args.validate_client, configs_root)

    if args.status:
        return _print_status(configs_root)

    if args.serve:
        return _run_server(configs_root, host=args.host, port=args.port, reload=args.reload)

    if args.all_clients:
        return _run_all_clients(configs_root)

    client_key = args.client or "demo-client"
    client_dir = configs_root / client_key

    if not client_dir.exists():
        print(f"Client config not found: {client_dir}", file=sys.stderr)
        return 1

    if args.poll:
        if args.poll_interval > 0:
            run_client_with_messages_loop(client_dir, poll_interval_minutes=args.poll_interval)
            return 0
        result = run_client_with_messages(client_dir)
        print(result["terminal_summary"])
        return 0

    return _run_single_client(configs_root, client_key)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run Scope Creep Enforcer for one client or all configured clients."
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--client", help="Client key under clients/, for example demo-client.")
    group.add_argument("--all-clients", action="store_true", help="Run every client under clients/.")
    parser.add_argument(
        "--new-client",
        metavar="NAME",
        help="Scaffold a new client directory under clients/ with template configs.",
    )
    parser.add_argument(
        "--validate-client",
        metavar="CLIENT_KEY",
        help="Validate config files and env vars for a client.",
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="Print a status table across all configured clients.",
    )
    parser.add_argument(
        "--log-json",
        action="store_true",
        help="Emit structured JSON log lines (for log aggregators). Default: human-readable.",
    )
    parser.add_argument(
        "--configs-root",
        default="clients",
        help="Root directory containing client configuration folders.",
    )
    parser.add_argument(
        "--poll",
        action="store_true",
        help="Poll configured message channels (Slack, Gmail, Outlook, Asana comments) before running.",
    )
    parser.add_argument(
        "--poll-interval",
        type=int,
        default=0,
        metavar="MINUTES",
        help="Run continuously, polling every N minutes. Requires --poll. Default: run once.",
    )
    parser.add_argument(
        "--serve",
        action="store_true",
        help="Start the webhook HTTP server (FastAPI/uvicorn). Listens for real-time events from Slack, Gmail, and Outlook.",
    )
    parser.add_argument("--host", default="0.0.0.0", help="Bind host for --serve. Default: 0.0.0.0")
    parser.add_argument("--port", type=int, default=8000, help="Bind port for --serve. Default: 8000")
    parser.add_argument(
        "--reload",
        action="store_true",
        help="Enable auto-reload for --serve (development only).",
    )
    return parser


def _run_server(configs_root: Path, host: str, port: int, reload: bool) -> int:
    import uvicorn
    from app.webhooks.server import create_app

    app = create_app(configs_root)
    print(f"Webhook server starting — http://{host}:{port}")
    print(f"Configs root: {configs_root}")
    print("Endpoints:")
    print(f"  GET  http://{host}:{port}/health")
    print(f"  POST http://{host}:{port}/webhook/{{client_id}}/slack")
    print(f"  POST http://{host}:{port}/webhook/{{client_id}}/gmail")
    print(f"  POST http://{host}:{port}/webhook/{{client_id}}/outlook")
    uvicorn.run(app, host=host, port=port, reload=reload)
    return 0


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

    client_dirs = [
        path
        for path in configs_root.iterdir()
        if path.is_dir() and ((path / "config" / "client.yaml").exists() or (path / "client.yaml").exists())
    ]
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


def _scaffold_new_client(client_name: str, configs_root: Path) -> int:
    from app.workflows.new_client import scaffold_new_client
    client_root = scaffold_new_client(client_name, configs_root)
    print(f"Created: {client_root}")
    print(f"  Edit {client_root}/config/client.yaml to configure work source and channels.")
    print(f"  Edit {client_root}/config/contract_rules.yaml to match your contract.")
    print(f"  Edit {client_root}/inputs/sow.md and inputs/work_log.csv.")
    print(f"  Copy {client_root}/.env.example to {client_root}/.env and fill in credentials.")
    print(f"  Run: python3 -m app.main --validate-client {client_root.name}")
    return 0


def _validate_client(client_key: str, configs_root: Path) -> int:
    from app.workflows.new_client import validate_client
    return validate_client(client_key, configs_root)


def _print_status(configs_root: Path) -> int:
    from app.workflows.dashboard import build_status_report
    print(build_status_report(configs_root))
    return 0


def _configure_logging(json_logs: bool = False) -> None:
    if json_logs:
        import json as _json

        class _JsonFormatter(logging.Formatter):
            def format(self, record: logging.LogRecord) -> str:
                payload = {
                    "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
                    "level": record.levelname,
                    "logger": record.name,
                    "msg": record.getMessage(),
                }
                if record.exc_info:
                    payload["exc"] = self.formatException(record.exc_info)
                return _json.dumps(payload)

        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(_JsonFormatter())
        logging.basicConfig(handlers=[handler], level=logging.INFO, force=True)
    else:
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s %(levelname)s %(name)s — %(message)s",
            stream=sys.stderr,
        )


if __name__ == "__main__":
    raise SystemExit(main())
