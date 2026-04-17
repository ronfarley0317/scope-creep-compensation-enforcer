from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

_CHANNEL_ENV_VARS: dict[str, list[str]] = {
    "slack": ["SLACK_BOT_TOKEN"],
    "gmail": ["GMAIL_SERVICE_ACCOUNT_PATH"],
    "outlook": ["OUTLOOK_CLIENT_ID", "OUTLOOK_CLIENT_SECRET", "OUTLOOK_TENANT_ID"],
    "asana_comment": ["ASANA_ACCESS_TOKEN"],
}


@dataclass
class ValidationReport:
    valid_channels: list[str] = field(default_factory=list)
    failed_channels: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def has_any_valid(self) -> bool:
        return bool(self.valid_channels)

    def to_dict(self) -> dict[str, Any]:
        return {
            "valid_channels": self.valid_channels,
            "failed_channels": self.failed_channels,
            "warnings": self.warnings,
        }


class CredentialValidator:
    """Validates credentials for each configured message channel before polling begins.

    Invalid channels are skipped — they never cause a full run failure.
    """

    def validate(self, message_source_types: list[str]) -> ValidationReport:
        report = ValidationReport()
        for channel in message_source_types:
            missing = self._missing_env_vars(channel)
            if missing:
                msg = f"Channel '{channel}' disabled — missing env vars: {', '.join(missing)}"
                logger.warning(msg)
                report.failed_channels.append(channel)
                report.warnings.append(msg)
            else:
                extra_warning = self._extra_check(channel)
                if extra_warning:
                    report.warnings.append(extra_warning)
                report.valid_channels.append(channel)
                logger.info("Channel '%s' credentials OK", channel)
        return report

    def _missing_env_vars(self, channel: str) -> list[str]:
        required = _CHANNEL_ENV_VARS.get(channel, [])
        return [var for var in required if not os.environ.get(var)]

    def _extra_check(self, channel: str) -> str | None:
        if channel == "gmail":
            path = os.environ.get("GMAIL_SERVICE_ACCOUNT_PATH", "")
            if path and not os.path.exists(path):
                return f"GMAIL_SERVICE_ACCOUNT_PATH '{path}' does not exist on disk"
        return None
