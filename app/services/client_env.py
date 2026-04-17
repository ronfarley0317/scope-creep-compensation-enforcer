from __future__ import annotations

import os
from contextlib import contextmanager
from pathlib import Path
from typing import Generator


def load_client_env(client_root: Path) -> dict[str, str]:
    """Parse clients/<id>/.env and return key/value pairs without modifying os.environ."""
    env_path = client_root / ".env"
    if not env_path.exists():
        return {}
    result: dict[str, str] = {}
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key:
            result[key] = value
    return result


@contextmanager
def client_env_context(client_root: Path) -> Generator[None, None, None]:
    """Temporarily overlay client-specific env vars onto os.environ for the duration of a run.

    Vars from clients/<id>/.env are applied at entry and fully removed at exit,
    restoring any previously set values. This keeps multi-client batch runs isolated.
    """
    overrides = load_client_env(client_root)
    previous: dict[str, str | None] = {}

    for key, value in overrides.items():
        previous[key] = os.environ.get(key)
        os.environ[key] = value

    try:
        yield
    finally:
        for key, old_value in previous.items():
            if old_value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = old_value
