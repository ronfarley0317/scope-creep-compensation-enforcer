# Scope Creep Compensation Enforcer

Scope Creep Compensation Enforcer is a private MVP for detecting work delivered beyond contract scope and generating structured compensation artifacts. It is designed to help service teams identify recoverable revenue from scope creep before that work is lost or absorbed informally.

## Problem

Many client teams over-deliver without a clear, repeatable way to trace extra requests back to contract terms, calculate the financial impact, and prepare billing or review artifacts. This system creates an auditable path from source inputs to compensation recommendations.

## High-Level Architecture

The system is organized as a config-driven pipeline:

- Source adapters fetch or load scope inputs and work activity inputs.
- Normalization converts those inputs into a standard internal schema.
- The comparison engine evaluates delivered work against configured scope rules.
- The compensation layer turns validated scope-creep events into invoice and review artifacts.
- The delivery and history layers package outputs and record each run.

The business logic is deterministic and keeps the comparison and compensation engines source-agnostic.

## Current MVP Capabilities

- Parse structured SOW inputs into normalized scope data.
- Normalize structured work activity inputs from local fixtures and an initial Asana work adapter.
- Detect exceeded scope, exceeded limits, and billable overages.
- Generate compensation drafts, invoice drafts, billing review packages, delivery bundles, and run history.
- Run one client or all configured clients from a single CLI entrypoint.

## Run

Run one client:

```bash
python -m app.main --client demo-client
```

Run all clients:

```bash
python -m app.main --all-clients
```

If no client is provided, the CLI defaults to `demo-client`:

```bash
python -m app.main
```

## Outputs

Single-client runs write outputs under:

```bash
outputs/<client-id>/
```

Related artifacts are also written to:

- `outputs/run_history/`
- `outputs/invoices/`
- `outputs/billing/`
- `outputs/delivery/`
- `outputs/reports/`

Batch runs write outputs under:

```bash
outputs/batches/
```

## Current Status

- Private MVP
- Not yet production-hardened
- Designed for revenue recovery and scope creep enforcement

## Next Planned Enhancements

- Additional real source adapters for scope documents, task systems, and messaging systems
- Stronger production controls around authentication, retries, and operational monitoring
- Provider-specific billing/export adapters for finance systems
- More robust validation, reconciliation, and human approval workflows
- Broader support for mixed-source client configurations across scope, work, and billing lanes

## Notes

This repository intentionally avoids secrets, private tokens, and real client data. All included datasets and examples are demo fixtures only.
