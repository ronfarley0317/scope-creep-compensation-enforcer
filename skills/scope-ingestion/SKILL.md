---
name: scope-ingestion
description: Extract structured scope limits, deliverables, revision caps, hours, and billing rules from a contract, SOW, or structured project brief. Use when the task is to parse project scope from source documents into auditable structured data. Do not use for work-log comparison, invoice generation, or compensation drafting.
---

# Scope Ingestion

Extract structured scope information from the source document and return structured JSON only.

## Workflow

1. Read the source document closely.
2. Extract only information that is explicitly stated or is a narrow operational assumption required to normalize the output.
3. Preserve traceability by keeping short source snippets or section labels when available.
4. Separate facts from assumptions.
5. Mark uncertainty with confidence flags instead of guessing.

## Extraction Rules

- Prefer exact language from the document over paraphrased interpretation.
- Capture deliverables as discrete items, not one merged paragraph.
- Capture limits only when the document states a cap, exclusion, threshold, dependency, revision allowance, timeline restriction, or bounded quantity.
- Capture billing rules only when the document states pricing logic, overage handling, change-order conditions, hourly billing, flat fees, included rounds, or approval requirements.
- Put unstated but necessary normalization notes in `assumptions`.
- If a field is absent, return an empty array for that field rather than inventing content.
- If the document is ambiguous, include the candidate interpretation in `assumptions` and add a confidence flag.

## Field Guidance

### `deliverables`

Return one object per concrete contracted output.

Include when available:

- `id`
- `name`
- `description`
- `acceptance_criteria`
- `source_text`

### `limits`

Return one object per explicit scope boundary.

Common examples:

- revision caps
- included hours
- excluded work
- number of pages, screens, concepts, or rounds
- timeline or response-time bounds
- approval dependencies

Include when available:

- `id`
- `type`
- `value`
- `unit`
- `applies_to`
- `source_text`

### `billing_rules`

Return one object per explicit commercial rule.

Common examples:

- hourly rate
- flat fee
- overage billing
- out-of-scope handling
- change-order requirement
- rush fee

Include when available:

- `id`
- `rule_type`
- `trigger`
- `amount`
- `unit`
- `currency`
- `source_text`

### `assumptions`

Return one object per assumption required to make the structured output usable.

Use this field for:

- normalized naming
- inferred grouping of related clauses
- ambiguous clauses that need human review

Include when available:

- `id`
- `statement`
- `reason`
- `confidence`

### `confidence_flags`

Return one object per risk, ambiguity, or extraction concern.

Use this field for:

- ambiguous wording
- conflicting clauses
- missing commercial detail
- unclear deliverable boundaries
- weakly structured source text

Include when available:

- `id`
- `severity`
- `field`
- `issue`
- `source_text`

## Output Contract

Return JSON in this shape:

```json
{
  "deliverables": [
    {
      "id": "deliv_1",
      "name": "Landing page design",
      "description": "Design one desktop and one mobile landing page",
      "acceptance_criteria": "Client review and approval",
      "source_text": "Deliverables: one landing page design for desktop and mobile."
    }
  ],
  "limits": [
    {
      "id": "limit_1",
      "type": "revision_cap",
      "value": 2,
      "unit": "rounds",
      "applies_to": "Landing page design",
      "source_text": "Includes up to two rounds of revisions."
    }
  ],
  "billing_rules": [
    {
      "id": "bill_1",
      "rule_type": "out_of_scope_hourly",
      "trigger": "Work beyond included revisions",
      "amount": 150,
      "unit": "hour",
      "currency": "USD",
      "source_text": "Additional revisions are billed at $150/hour."
    }
  ],
  "assumptions": [
    {
      "id": "assumption_1",
      "statement": "The phrase 'homepage' is normalized to 'landing page design'.",
      "reason": "The document uses both terms for the same deliverable.",
      "confidence": "medium"
    }
  ],
  "confidence_flags": [
    {
      "id": "flag_1",
      "severity": "medium",
      "field": "billing_rules",
      "issue": "The document describes extra work as billable but does not state a rate.",
      "source_text": "Out-of-scope work will be billed separately."
    }
  ]
}
```

## Response Requirements

- Return JSON only.
- Do not wrap the JSON in Markdown.
- Do not add commentary before or after the JSON.
- Do not include keys outside the required output unless the user explicitly asks for them.
