# Scope Creep Enforcer - Agent Guide

## Mission

Build a small Python system that detects out-of-scope work by comparing a structured statement of work (SOW) against structured work logs, then generates auditable compensation artifacts.

This repository is for a focused MVP, not a broad platform.

## Product Summary

Scope Creep Enforcer identifies work performed outside the contracted scope and turns that finding into a compensation event draft such as:

- an invoice line item draft
- a change-order draft
- a billable event record

The system should prefer deterministic, explainable business rules over vague model-driven judgment.

## Non-Negotiable Project Rules

- Python only
- Keep architecture simple and modular
- Build only MVP components first
- Do not add unnecessary integrations
- Prefer deterministic business rules over vague AI reasoning
- Every major service needs tests
- Outputs must be auditable and structured JSON where possible

## MVP Scope

Implement only these capabilities first:

1. Scope ingestion from a structured SOW text file
2. Scope comparison against structured work log input
3. Compensation trigger that creates a billable event draft

Anything outside this list is out of scope unless explicitly requested.

## Definition Of Done

The MVP is done only when all of the following are true:

1. Code runs locally
2. Tests pass
3. `README.md` explains how to run one sample client
4. The agent can output:
   - one example scope-creep event
   - one example compensation draft

## Engineering Priorities

When making decisions, optimize in this order:

1. Correctness and auditability
2. Simplicity of implementation
3. Deterministic repeatability
4. Clear test coverage
5. Extensibility after the MVP

Do not optimize for speculative scale, multi-tenant complexity, or enterprise workflow breadth.

## Architectural Guidance

Keep the code modular, but avoid unnecessary layering.

Preferred MVP structure:

- `app/main.py`
  Entry point or small CLI for running one sample case locally.
- `app/config.py`
  Minimal runtime config only if needed.
- `app/models/`
  Typed domain models for SOW scope items, work logs, scope-creep findings, and compensation drafts.
- `app/services/`
  Focused services with explicit inputs and outputs:
  - SOW ingestion
  - scope comparison
  - compensation trigger
- `app/rules/`
  Deterministic business rules or match logic if the comparison logic starts to grow.
- `tests/`
  Unit tests for every major service plus one integration-style happy-path test.
- `configs/` or `examples/`
  Sample SOW and sample work log fixtures used by local runs and tests.

If the current repo does not yet contain all of these directories, create only what is necessary for the MVP.

## Functional Expectations

### 1. Scope Ingestion

The first implementation should ingest a structured SOW text file with fields that are easy to parse deterministically.

Preferred characteristics:

- clearly delimited sections
- stable labels
- explicit scope items
- optional exclusions
- optional rate or pricing hints

Avoid OCR, PDFs, or fuzzy parsing in the MVP unless the input is already converted into a predictable text structure.

### 2. Scope Comparison

Comparison logic should operate on structured work log input.

At minimum, support comparing work entries against:

- allowed deliverables
- allowed task categories
- explicit exclusions
- effort or frequency constraints, if present

A finding should explain why work was flagged. Example reasons:

- task category missing from contracted scope
- deliverable exceeds stated scope
- work explicitly listed as excluded
- work volume exceeds a contractual threshold

### 3. Compensation Trigger

When out-of-scope work is found, generate a billable event draft.

This should be a structured record, not freeform prose only.

The draft should include enough information for a human to review:

- client identifier
- source work log reference
- matching scope reference when relevant
- reason for flag
- suggested compensation type
- quantity or effort
- rate or pricing basis if available
- status such as `draft`

## Output Requirements

Prefer structured JSON outputs for all major artifacts.

At minimum, define stable JSON shapes for:

- parsed scope data
- normalized work log entries
- scope-creep events
- compensation drafts

Every flagged event should be auditable. Include references back to:

- source SOW section or scope item ID
- source work log entry ID
- rule or condition that caused the flag
- timestamp or run identifier if useful

## AI Usage Policy

If AI-assisted logic is introduced later, it must remain optional and secondary.

For the MVP:

- deterministic rules should be the default path
- no opaque scoring systems
- no vague classification without explanation
- no dependency on remote AI services for core business decisions

## Testing Requirements

Every major service needs tests.

Minimum expected coverage:

- SOW ingestion tests
- scope comparison tests
- compensation trigger tests
- one end-to-end sample flow test

Tests should verify both expected success paths and obvious edge cases, especially:

- exact in-scope match
- clearly out-of-scope work
- excluded work
- missing or malformed input
- compensation draft creation from a flagged event

## Repository Boundaries

Do not add these during the MVP unless explicitly required:

- databases
- background jobs
- web frontends
- authentication
- external billing integrations
- OCR pipelines
- vector databases
- agent swarms
- generic workflow orchestration

Local files and in-memory processing are sufficient for the first version.

## Documentation Expectations

`README.md` should eventually explain:

- project purpose
- expected input file formats
- how to run the sample locally
- how to run tests
- one example of a scope-creep event
- one example of a compensation draft

Keep the README practical and short.

## Agent Behavior

When working in this repo:

- implement the smallest complete MVP slice first
- keep interfaces explicit and typed where practical
- return structured outputs over prose
- add tests alongside every major service
- avoid adding dependencies without clear need
- prefer standard library solutions when reasonable
- make business rules inspectable in code

If a requested change expands beyond the MVP, call that out clearly and separate MVP work from post-MVP ideas.

## Suggested MVP Data Flow

The intended flow is:

1. Read a structured SOW text file
2. Parse it into normalized scope data
3. Read structured work log input
4. Compare work log entries against scope rules
5. Emit one or more scope-creep events
6. Convert flagged events into compensation drafts
7. Print or save structured JSON examples for review

## Acceptance Artifacts

Before considering a task complete, make sure the repo can produce:

- one sample parsed SOW
- one sample work log comparison result
- one example scope-creep event JSON
- one example compensation draft JSON
- passing automated tests

## Decision Standard

If a design choice is unclear, choose the option that is:

- easier to explain
- easier to test
- easier to audit
- easier to run locally

That is the standard for this project.
