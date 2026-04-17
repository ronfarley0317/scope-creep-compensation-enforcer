---
name: scope-comparison
description: Compare structured scope data against structured work log data to determine whether delivered work exceeds agreed scope. Use when both scope data and work log data are already available in structured form and the goal is to classify work as in-scope, out-of-scope, or limit-exceeding. Do not use for initial scope extraction or final client messaging.
---

# Scope Comparison

Compare agreed scope against completed work and return structured JSON only.

## Workflow

1. Read the structured scope data first.
2. Read the structured work log data second.
3. Match work items to explicit deliverables, limits, exclusions, and billing rules.
4. Classify each work item deterministically.
5. Estimate revenue impact only from explicit billing rules or clearly stated rates.
6. Record traceable creep events for anything out of scope or beyond limits.

## Comparison Rules

- Prefer exact structured matches over semantic interpretation.
- Treat a work item as in scope only when it maps to an allowed deliverable or allowed task category and does not violate a limit or exclusion.
- Treat a work item as out of scope when it has no valid scope match, is explicitly excluded, or clearly falls outside the agreed deliverables.
- Treat a work item as an exceeded limit when the work is related to an in-scope deliverable but surpasses an explicit cap such as revision rounds, hours, units, or frequency.
- Do not invent revenue values. If the pricing basis is absent, record the gap in `revenue_impact_estimate` and `creep_events`.
- Preserve references to source IDs whenever they exist.

## Matching Order

Apply checks in this order:

1. Explicit exclusion
2. Explicit deliverable or category match
3. Limit validation
4. Billing rule lookup
5. Revenue impact estimation

If a work item fails an earlier check, keep that reason as the primary explanation.

## Field Guidance

### `in_scope_items`

Return one object per work item that fits agreed scope without exceeding a limit.

Include when available:

- `work_item_id`
- `matched_scope_id`
- `matched_deliverable`
- `reason`
- `source_hours`

### `out_of_scope_items`

Return one object per work item that does not fit agreed scope.

Use this field for:

- missing deliverable match
- excluded task
- clearly new work not covered by the SOW

Include when available:

- `work_item_id`
- `reason_code`
- `reason`
- `source_hours`
- `suggested_billable_basis`

### `exceeded_limits`

Return one object per work item or grouped work set that exceeds an explicit contractual limit.

Common examples:

- revisions beyond cap
- hours beyond included amount
- quantity beyond included units

Include when available:

- `work_item_id`
- `limit_id`
- `limit_type`
- `allowed_value`
- `actual_value`
- `unit`
- `reason`

### `revenue_impact_estimate`

Return a single object summarizing the commercial effect of the flagged work.

Include:

- `currency`
- `estimated_amount`
- `pricing_basis`
- `pricing_confidence`
- `notes`

Use:

- numeric `estimated_amount` when the rate is explicit and arithmetic is deterministic
- `null` for `estimated_amount` when the contract says work is billable but gives no usable rate

### `creep_events`

Return one object per auditable scope-creep incident.

Each event should map to either:

- an out-of-scope item
- an exceeded limit

Include when available:

- `event_id`
- `work_item_id`
- `scope_reference_id`
- `event_type`
- `trigger_reason`
- `billable`
- `estimated_amount`
- `currency`
- `source_excerpt`

## Revenue Estimation Rules

- Use only explicit rates or pricing rules from the structured scope data.
- Multiply hours by hourly rate only when both values are present and the rule clearly applies.
- Use fixed overage or per-unit pricing only when the contract states it directly.
- If multiple pricing rules could apply, choose the narrowest explicit rule and note the ambiguity in `creep_events`.
- If no deterministic pricing rule exists, keep `estimated_amount` as `null`.

## Output Contract

Return JSON in this shape:

```json
{
  "in_scope_items": [
    {
      "work_item_id": "work_1",
      "matched_scope_id": "deliv_1",
      "matched_deliverable": "Landing page design",
      "reason": "Matches a contracted deliverable and remains within revision limits.",
      "source_hours": 3
    }
  ],
  "out_of_scope_items": [
    {
      "work_item_id": "work_3",
      "reason_code": "no_scope_match",
      "reason": "CRM migration work does not map to any agreed deliverable or allowed task category.",
      "source_hours": 4,
      "suggested_billable_basis": "hourly_if_approved"
    }
  ],
  "exceeded_limits": [
    {
      "work_item_id": "work_2",
      "limit_id": "limit_1",
      "limit_type": "revision_cap",
      "allowed_value": 2,
      "actual_value": 3,
      "unit": "rounds",
      "reason": "Third revision round exceeds the included revision cap."
    }
  ],
  "revenue_impact_estimate": {
    "currency": "USD",
    "estimated_amount": 750,
    "pricing_basis": "3 excess hours at 150 USD/hour plus 2 additional hours of out-of-scope work at 150 USD/hour",
    "pricing_confidence": "high",
    "notes": "Estimate based on explicit out-of-scope hourly billing rule."
  },
  "creep_events": [
    {
      "event_id": "creep_1",
      "work_item_id": "work_2",
      "scope_reference_id": "limit_1",
      "event_type": "limit_exceeded",
      "trigger_reason": "Revision work exceeded the included cap.",
      "billable": true,
      "estimated_amount": 150,
      "currency": "USD",
      "source_excerpt": "Includes up to two rounds of revisions."
    },
    {
      "event_id": "creep_2",
      "work_item_id": "work_3",
      "scope_reference_id": null,
      "event_type": "out_of_scope",
      "trigger_reason": "No matching scope item or allowed category.",
      "billable": true,
      "estimated_amount": 600,
      "currency": "USD",
      "source_excerpt": "Additional work outside scope is billed at $150/hour."
    }
  ]
}
```

## Response Requirements

- Return JSON only.
- Do not wrap the JSON in Markdown.
- Do not add commentary before or after the JSON.
- Do not include keys outside the required output unless the user explicitly asks for them.
