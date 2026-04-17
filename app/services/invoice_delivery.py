from __future__ import annotations

import logging
import os
import smtplib
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class InvoiceDelivery:
    """Send an approved invoice to the client via email.

    Reads config from client_config['invoice_delivery']:
        invoice_delivery:
          method: email
          email_to: client@example.com
          email_from_env: INVOICE_FROM_EMAIL
          smtp_host_env: SMTP_HOST        # e.g. smtp.gmail.com
          smtp_port: 587                  # optional, default 587
          smtp_user_env: SMTP_USER
          smtp_password_env: SMTP_PASSWORD
    """

    def send(
        self,
        client_config: dict[str, Any],
        entry: dict[str, Any],
        store: Any | None = None,
    ) -> None:
        """Send invoice email and record delivery outcome back to the approval entry."""
        delivery_cfg = client_config.get("invoice_delivery", {})
        method = delivery_cfg.get("method", "")

        if method != "email":
            logger.info("Invoice delivery skipped — method %r not configured", method or "(none)")
            return

        email_to = delivery_cfg.get("email_to", "")
        email_from = os.environ.get(delivery_cfg.get("email_from_env", "INVOICE_FROM_EMAIL"), "")
        smtp_host = os.environ.get(delivery_cfg.get("smtp_host_env", "SMTP_HOST"), "")
        smtp_port = int(delivery_cfg.get("smtp_port", 587))
        smtp_user = os.environ.get(delivery_cfg.get("smtp_user_env", "SMTP_USER"), "")
        smtp_password = os.environ.get(delivery_cfg.get("smtp_password_env", "SMTP_PASSWORD"), "")

        missing = [k for k, v in {"email_to": email_to, "email_from": email_from,
                                   "smtp_host": smtp_host, "smtp_user": smtp_user,
                                   "smtp_password": smtp_password}.items() if not v]
        if missing:
            logger.warning("Invoice delivery skipped — missing config/env: %s", missing)
            return

        invoice_text = _read_invoice(entry)
        if not invoice_text:
            logger.warning("Invoice delivery skipped — could not read invoice artifact for run %s", entry.get("run_id"))
            return

        client_name = client_config.get("client_name", client_config.get("client_id", "Client"))
        subject = f"Invoice: {client_name} — Scope Change Compensation"
        msg = _build_email(email_from, email_to, subject, invoice_text)

        try:
            _send_smtp(smtp_host, smtp_port, smtp_user, smtp_password, email_from, email_to, msg)
            logger.info("Invoice sent: run=%s to=%s", entry.get("run_id"), email_to)
            delivery = _make_delivery_record(method="email", sent_to=email_to, status="sent", error=None)
        except Exception as exc:
            logger.error("Invoice delivery failed for run %s: %s", entry.get("run_id"), exc)
            delivery = _make_delivery_record(method="email", sent_to=email_to, status="failed", error=str(exc))

        entry["delivery"] = delivery
        if store is not None:
            store.record_delivery(entry["run_id"], delivery)


# ---------------------------------------------------------------------------
# Helpers

def _read_invoice(entry: dict[str, Any]) -> str:
    paths = entry.get("artifact_paths", {})
    invoice_path = paths.get("run_invoice_markdown") or paths.get("invoice_markdown", "")
    if not invoice_path:
        return ""
    path = Path(invoice_path)
    if not path.exists():
        logger.warning("Invoice file not found: %s", invoice_path)
        return ""
    return path.read_text(encoding="utf-8")


def _build_email(
    email_from: str,
    email_to: str,
    subject: str,
    invoice_text: str,
) -> MIMEMultipart:
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = email_from
    msg["To"] = email_to

    msg.attach(MIMEText(invoice_text, "plain", "utf-8"))
    msg.attach(MIMEText(_markdown_to_html(invoice_text), "html", "utf-8"))
    return msg


def _markdown_to_html(text: str) -> str:
    escaped = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return (
        "<!DOCTYPE html><html><body>"
        "<pre style='font-family:monospace;white-space:pre-wrap;max-width:700px'>"
        f"{escaped}"
        "</pre></body></html>"
    )


def _send_smtp(
    host: str,
    port: int,
    user: str,
    password: str,
    email_from: str,
    email_to: str,
    msg: MIMEMultipart,
) -> None:
    with smtplib.SMTP(host, port, timeout=30) as server:
        server.ehlo()
        server.starttls()
        server.ehlo()
        server.login(user, password)
        server.sendmail(email_from, [email_to], msg.as_string())


def _make_delivery_record(method: str, sent_to: str, status: str, error: str | None) -> dict[str, Any]:
    return {
        "method": method,
        "sent_to": sent_to,
        "sent_at": datetime.now(tz=timezone.utc).isoformat(timespec="seconds"),
        "status": status,
        "error": error,
    }
