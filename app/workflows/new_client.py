from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

from app.services.config_loader import load_yaml

_CLIENT_YAML_TEMPLATE = """\
client_id: {client_id}
client_name: {client_name}
client_type: consulting_agency
currency: USD
industry: consulting
description: >
  {client_name} — edit this description to match the engagement.
contract_rules_path: contract_rules.yaml
field_mapping_path: field_mapping.yaml
sample_sow_path: ../inputs/sow.md
sample_work_log_path: ../inputs/work_log.csv
scope_source_type: local_fixture
# work_source_type options: local_fixture | asana | jira | linear | clickup
work_source_type: local_fixture
billing_source_type: manual
default_outputs:
  scope_creep_event_format: json
  compensation_draft_format: json
  audit_mode: strict
  compensation_enforcement_mode: recommend

# --- Jira work source (set work_source_type: jira to activate)
# jira:
#   host_env: JIRA_HOST
#   email_env: JIRA_EMAIL
#   api_token_env: JIRA_API_TOKEN
#   project_key: PROJ
#   completed_since: "2026-01-01"
#   page_size: 100

# --- Linear work source (set work_source_type: linear to activate)
# linear:
#   api_key_env: LINEAR_API_KEY
#   team_id: your-team-uuid
#   project_id: your-project-uuid
#   completed_since: "2026-01-01"

# --- ClickUp work source (set work_source_type: clickup to activate)
# clickup:
#   api_token_env: CLICKUP_API_TOKEN
#   list_id: "123456789"
#   completed_since: "2026-01-01"
#   page_size: 100

# Message channel monitoring — uncomment to enable
# message_source_types:
#   - slack
#   - gmail
#   - outlook
#   - asana_comment

# Internal alert — your team's Slack channel for scope-creep notifications
# internal_alert:
#   slack_bot_token_env: ALERT_SLACK_BOT_TOKEN
#   slack_channel_id: C0YOURTEAMCHANNEL

# Invoice delivery — auto-email approved invoices
# invoice_delivery:
#   method: email
#   email_to: client@example.com
#   email_from_env: INVOICE_FROM_EMAIL
#   smtp_host_env: SMTP_HOST
#   smtp_port: 587
#   smtp_user_env: SMTP_USER
#   smtp_password_env: SMTP_PASSWORD
"""

_CONTRACT_RULES_TEMPLATE = """\
client_id: {client_id}
contract_name: {client_name} Engagement
contract_version: 1
currency: USD
scope:
  deliverables:
    - id: deliverable-1
      name: Deliverable 1
      included_quantity: 1
      unit: unit
      task_categories:
        - deliverable_1
      notes: Describe what is included.
  limits:
    - id: revision-rounds
      applies_to:
        - deliverable-1
      type: revision_rounds
      included_quantity: 2
      unit: rounds
      notes: Includes up to two revision rounds.
  billing_rules:
    - id: extra-revisions
      applies_to:
        - deliverable-1
      trigger: extra_revision_round
      billing_type: flat_fee
      amount: 150
      unit: round
      notes: Extra revision rounds billed at 150 each.
assumptions:
  - Edit or replace these deliverables to match your contract.
  - Add billing_rules for each out-of-scope trigger.
interpretation:
  revision_limit_type: revision_rounds
  revision_billing_trigger: extra_revision_round
  quantity_trigger_by_unit:
    unit: extra_deliverable_quantity
  out_of_scope_trigger: out_of_scope
  compensation_labels:
    internal_summary: Scope-creep event(s) prepared for compensation handling.
    client_summary: We identified completed work that exceeded the agreed scope.
"""

_FIELD_MAPPING_TEMPLATE = """\
source_type: structured_documents
client_id: {client_id}
field_aliases:
  deliverables:
    - deliverable_hint
    - deliverable_code
    - deliverable
  revisions:
    - revision_number
    - revision_count
    - revisions_completed
  hours:
    - hours
    - effort_hours
    - logged_hours
  assets:
    - quantity
    - delivered_units
    - asset_count
sow_mapping:
  deliverables_section: included scope
  deliverable_fields:
    id:
      - deliverable_id
      - id
    extra_quantity_fields: {{}}
work_item_mapping:
  work_item_id: id
  work_date: performed_on
  task_category: category
  deliverable_hint: deliverables
  description: description
  hours: hours
  revision_count: revisions
quantity_mapping:
  by_category: {{}}
normalization_rules:
  deliverable_aliases:
    deliverable-1:
      - deliverable 1
      - deliverable-1
  category_aliases:
    deliverable_1:
      - deliverable_1
    revision:
      - revision
      - revisions
      - revision_round
  unit_aliases:
    unit:
      - units
    round:
      - rounds
  quantity_defaults: {{}}
audit_fields:
  - id
  - performed_on
  - category
  - deliverable_hint
  - description
  - hours
  - revision_number
"""

_ENV_EXAMPLE_TEMPLATE = """\
# Per-client credentials for {client_id}
# Copy this file to .env and fill in real values.
# This file is committed. .env is gitignored.

# Slack — bot token for this client's workspace
SLACK_BOT_TOKEN=xoxb-your-token-here

# Gmail — path to service account JSON for this client's Google Workspace
GMAIL_SERVICE_ACCOUNT_PATH=/path/to/{client_id}-gmail-service-account.json

# Outlook / Microsoft 365 — app registration for this client's tenant
OUTLOOK_CLIENT_ID=your-client-id
OUTLOOK_CLIENT_SECRET=your-client-secret
OUTLOOK_TENANT_ID=your-tenant-id

# Asana — personal access token scoped to this client's workspace
ASANA_ACCESS_TOKEN=your-asana-personal-access-token

# Jira — API token from id.atlassian.com/manage-profile/security/api-tokens
JIRA_HOST=yourco.atlassian.net
JIRA_EMAIL=you@yourco.com
JIRA_API_TOKEN=your-jira-api-token

# Linear — API key from linear.app/settings/api
LINEAR_API_KEY=lin_api_your-key-here

# ClickUp — API token from app.clickup.com/settings
CLICKUP_API_TOKEN=your-clickup-api-token

# Claude API — for hybrid message classification
ANTHROPIC_API_KEY=your-anthropic-api-key

# Webhook server — signing secrets for real-time event verification
SLACK_SIGNING_SECRET=your-slack-signing-secret
GMAIL_PUBSUB_TOKEN=your-pubsub-bearer-token
OUTLOOK_CLIENT_STATE=your-outlook-client-state-secret

# Internal alerts — Slack channel where YOUR team gets notified
ALERT_SLACK_BOT_TOKEN=xoxb-your-internal-alert-bot-token

# Invoice delivery — SMTP credentials
INVOICE_FROM_EMAIL=invoices@yourcompany.com
SMTP_HOST=smtp.gmail.com
SMTP_USER=invoices@yourcompany.com
SMTP_PASSWORD=your-app-password-here
"""

_SOW_TEMPLATE = """\
# Statement of Work — {client_name}

## Included Scope

| Deliverable ID | Name | Included Quantity | Unit | Notes |
|---|---|---|---|---|
| deliverable-1 | Deliverable 1 | 1 | unit | Describe what is included. |

## Revision Policy

Up to 2 revision rounds are included. Additional rounds are billed at $150/round.

## Out-of-Scope Work

Any work not listed above will be billed at the agreed overage rate.

---
*Edit this file to match your actual Statement of Work.*
"""

_WORK_LOG_HEADER = "id,performed_on,category,deliverable,description,hours,revisions_completed,delivered_units,section_count,source_type,source_reference,source_excerpt\n"


def scaffold_new_client(client_name: str, configs_root: Path) -> Path:
    """Create a new client directory scaffold under configs_root/<client_id>/."""
    client_id = _to_client_id(client_name)
    client_root = configs_root / client_id

    if client_root.exists():
        print(f"Client directory already exists: {client_root}", file=sys.stderr)
        sys.exit(1)

    config_dir = client_root / "config"
    inputs_dir = client_root / "inputs"
    config_dir.mkdir(parents=True)
    inputs_dir.mkdir(parents=True)

    ctx = {"client_id": client_id, "client_name": client_name}
    (config_dir / "client.yaml").write_text(_CLIENT_YAML_TEMPLATE.format(**ctx), encoding="utf-8")
    (config_dir / "contract_rules.yaml").write_text(_CONTRACT_RULES_TEMPLATE.format(**ctx), encoding="utf-8")
    (config_dir / "field_mapping.yaml").write_text(_FIELD_MAPPING_TEMPLATE.format(**ctx), encoding="utf-8")
    (client_root / ".env.example").write_text(_ENV_EXAMPLE_TEMPLATE.format(**ctx), encoding="utf-8")
    (inputs_dir / "sow.md").write_text(_SOW_TEMPLATE.format(**ctx), encoding="utf-8")
    (inputs_dir / "work_log.csv").write_text(_WORK_LOG_HEADER, encoding="utf-8")

    return client_root


def validate_client(client_key: str, configs_root: Path) -> int:
    """Validate client config files and required env vars. Returns exit code."""
    client_dir = configs_root / client_key / "config"
    if not client_dir.exists():
        print(f"Client not found: {configs_root / client_key}", file=sys.stderr)
        return 1

    errors: list[str] = []
    warnings: list[str] = []

    # --- Config files
    for filename in ("client.yaml", "contract_rules.yaml", "field_mapping.yaml"):
        path = client_dir / filename
        if not path.exists():
            errors.append(f"Missing config file: {path}")
            continue
        try:
            load_yaml(path)
        except Exception as exc:
            errors.append(f"Parse error in {filename}: {exc}")

    if errors:
        for e in errors:
            print(f"  ERROR  {e}", file=sys.stderr)
        return 1

    # --- Load client config
    try:
        cfg = load_yaml(client_dir / "client.yaml")
    except Exception:
        return 1

    # --- Env var checks
    client_root = configs_root / client_key
    _load_dotenv(client_root)

    work_source = cfg.get("work_source_type", "local_fixture")
    _check_work_source_env(work_source, cfg, warnings, errors)

    message_sources: list[str] = cfg.get("message_source_types", [])
    _check_message_source_env(message_sources, warnings)

    _check_optional_env(cfg, warnings)

    # --- Input files
    inputs_dir = client_root / "inputs"
    sow_path = cfg.get("sample_sow_path", "")
    work_log_path = cfg.get("sample_work_log_path", "")
    if work_source == "local_fixture":
        for rel, label in [(sow_path, "sample_sow_path"), (work_log_path, "sample_work_log_path")]:
            resolved = _resolve_input(client_dir, rel)
            if not resolved.exists():
                warnings.append(f"{label} not found: {resolved}")

    # --- Report
    ok = not errors
    status = "PASS" if ok else "FAIL"
    print(f"[{status}] {client_key}")
    if warnings:
        for w in warnings:
            print(f"  WARN   {w}")
    if errors:
        for e in errors:
            print(f"  ERROR  {e}", file=sys.stderr)
        return 1
    if not warnings:
        print("  All checks passed.")
    return 0


def _check_work_source_env(
    source: str, cfg: dict[str, Any], warnings: list[str], errors: list[str]
) -> None:
    required: dict[str, list[str]] = {
        "jira": ["JIRA_HOST", "JIRA_EMAIL", "JIRA_API_TOKEN"],
        "linear": ["LINEAR_API_KEY"],
        "clickup": ["CLICKUP_API_TOKEN"],
        "asana": ["ASANA_ACCESS_TOKEN"],
    }
    if source in required:
        for var in required[source]:
            if not os.environ.get(var):
                errors.append(f"Missing env var for work_source_type={source}: {var}")
        if source == "jira" and not cfg.get("jira", {}).get("project_key"):
            warnings.append("jira.project_key not set in client.yaml")
        if source == "linear" and not cfg.get("linear", {}).get("team_id"):
            errors.append("linear.team_id not set in client.yaml")
        if source == "clickup" and not cfg.get("clickup", {}).get("list_id"):
            errors.append("clickup.list_id not set in client.yaml")


def _check_message_source_env(sources: list[str], warnings: list[str]) -> None:
    required: dict[str, list[str]] = {
        "slack": ["SLACK_BOT_TOKEN"],
        "gmail": ["GMAIL_SERVICE_ACCOUNT_PATH"],
        "outlook": ["OUTLOOK_CLIENT_ID", "OUTLOOK_CLIENT_SECRET", "OUTLOOK_TENANT_ID"],
        "asana_comment": ["ASANA_ACCESS_TOKEN"],
    }
    for src in sources:
        for var in required.get(src, []):
            if not os.environ.get(var):
                warnings.append(f"Missing env var for message_source_type={src}: {var} (channel will be skipped)")


def _check_optional_env(cfg: dict[str, Any], warnings: list[str]) -> None:
    alert_cfg = cfg.get("internal_alert", {})
    if alert_cfg:
        token_env = alert_cfg.get("slack_bot_token_env", "ALERT_SLACK_BOT_TOKEN")
        if not os.environ.get(token_env):
            warnings.append(f"internal_alert configured but {token_env} not set — alerts disabled")
    delivery_cfg = cfg.get("invoice_delivery", {})
    if delivery_cfg and delivery_cfg.get("method") == "email":
        for env_key in ("email_from_env", "smtp_host_env", "smtp_user_env", "smtp_password_env"):
            var = delivery_cfg.get(env_key, "")
            if var and not os.environ.get(var):
                warnings.append(f"invoice_delivery configured but {var} not set — delivery disabled")


def _load_dotenv(client_root: Path) -> None:
    dotenv = client_root / ".env"
    if not dotenv.exists():
        return
    for line in dotenv.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        if key and key not in os.environ:
            os.environ[key] = val.strip()


def _resolve_input(config_dir: Path, rel: str) -> Path:
    if not rel:
        return Path("/nonexistent")
    p = Path(rel)
    if p.is_absolute():
        return p
    return (config_dir / p).resolve()


def _to_client_id(name: str) -> str:
    return name.lower().replace(" ", "-").replace("_", "-")
