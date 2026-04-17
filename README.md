# Scope Creep Enforcer

Scope Creep Enforcer parses a structured SOW, compares it against structured work logs, and generates draft compensation artifacts for validated scope-creep events.

## Prerequisites

- Python 3.11+ recommended
- Terminal access

## Project Setup

From the project root, create a virtual environment:

```bash
python3 -m venv .venv
```

Activate the virtual environment:

```bash
source .venv/bin/activate
```

Upgrade `pip`:

```bash
python -m pip install --upgrade pip
```

Install project requirements:

```bash
pip install -r requirements.txt
```

Note: the current MVP uses only the Python standard library, so `requirements.txt` may be empty right now. Running the install command is still the correct setup step.

## Run Tests

Run the full test suite:

```bash
python -m unittest discover -s tests -v
```

## Run One Client

Run the demo client workflow explicitly:

```bash
python -m app.main --client demo-client
```

This will:

- load the demo client config from `configs/clients/demo-client/client.yaml`
- parse the sample SOW from `configs/clients/demo-client/structured_sow.md`
- parse the sample work log from `configs/clients/demo-client/structured_work_log.json`
- generate scope-creep events
- generate compensation draft artifacts
- print a readable summary in the terminal

You can also omit `--client demo-client` and the CLI will default to `demo-client`:

```bash
python -m app.main
```

## Run All Clients

Run every client found under `configs/clients/`:

```bash
python -m app.main --all-clients
```

This will:

- discover each client folder containing `client.yaml`
- run each client independently using the same single-client workflow
- continue even if one client fails
- write a batch summary to `outputs/batches/`
- print a concise batch summary in the terminal

## Asana Work Source

The first production-ready external source adapter is an Asana work adapter. It fetches tasks from an Asana project and converts them into the existing `WorkActivityInput` structure, so the comparison and compensation engines do not change.

Required configuration in a client's `client.yaml`:

```yaml
work_source_type: asana
asana:
  access_token_env: ASANA_ACCESS_TOKEN
  project_gid: "1234567890"
  completed_since: "2026-04-01T00:00:00Z"
```

Required environment variable:

```bash
export ASANA_ACCESS_TOKEN=your_asana_personal_access_token
```

The adapter uses Asana project tasks plus task custom fields. Your `field_mapping.yaml` should map the flattened Asana task fields you want to normalize, for example:

```yaml
field_aliases:
  deliverables:
    - deliverable
  revisions:
    - revision_rounds
  hours:
    - tracked_hours
  assets:
    - assets_delivered
```

Asana custom fields are flattened into snake_case keys such as `tracked_hours`, `deliverable`, `task_category`, and also emitted as stable `custom_field_<gid>` keys.

## Demo Client Files

The demo client lives in `configs/clients/demo-client` and includes:

- `client.yaml`
- `contract_rules.yaml`
- `field_mapping.yaml`
- `structured_sow.md`
- `structured_work_log.json`
- `expected_scope_creep_output.json`

## Output Files

When you run the demo workflow, output files are written here:

```bash
outputs/demo-client/
```

The workflow writes:

- `outputs/demo-client/comparison.json`
- `outputs/demo-client/compensation.json`
- `outputs/demo-client/run_summary.json`
- `outputs/run_history/<run_id>.json`
- `outputs/invoices/demo-client-invoice.json`
- `outputs/invoices/demo-client-invoice.md`
- `outputs/billing/demo-client-billing-package.json`
- `outputs/billing/demo-client-billing-cover.md`
- `outputs/delivery/demo-client-delivery-package.json`
- `outputs/delivery/demo-client-delivery-summary.md`

When you run all clients, batch output files are written here:

```bash
outputs/batches/
```

The batch workflow writes:

- `outputs/batches/<batch_id>-summary.json`
- `outputs/batches/<batch_id>-summary.md`

## What You Should See

The terminal summary should show:

- the client name and ID
- the number of scope-creep events found
- the estimated billable amount
- the number of draft invoice items created
- the output folder path
