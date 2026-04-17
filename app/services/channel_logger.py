from __future__ import annotations

import json
import logging
import logging.handlers
from pathlib import Path
from typing import Any


def get_channel_logger(client_root: Path, name: str = "scope_enforcer") -> logging.Logger:
    """Return a logger that writes JSON lines to client state/poll.log (5 MB rotating)."""
    log_dir = client_root / "state"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / "poll.log"

    log = logging.getLogger(f"{name}.{client_root.name}")
    if log.handlers:
        return log

    log.setLevel(logging.DEBUG)

    handler = logging.handlers.RotatingFileHandler(
        log_path,
        maxBytes=5 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8",
    )
    handler.setFormatter(_JsonFormatter())
    log.addHandler(handler)

    console = logging.StreamHandler()
    console.setLevel(logging.INFO)
    console.setFormatter(logging.Formatter("%(levelname)s [%(name)s] %(message)s"))
    log.addHandler(console)

    return log


class _JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        entry: dict[str, Any] = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        if record.exc_info:
            entry["exc"] = self.formatException(record.exc_info)
        return json.dumps(entry)
