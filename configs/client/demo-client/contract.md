# Demo Client Statement Of Work

Client ID: demo-client
Client Name: Demo Client
Currency: USD
Note: Additional requests outside the defined scope may be subject to additional billing upon review.

## Deliverables
- id: landing-page
  name: Landing Page Design
  task_categories: design, revision
  included_hours: 10
  included_revisions: 2
  notes: One responsive landing page design.
- id: email-sequence
  name: Email Sequence
  task_categories: copywriting
  included_hours: 4
  included_revisions: 1
  notes: Three launch emails.

## Limits
- id: landing-page-hours
  type: included_hours
  deliverable_id: landing-page
  value: 10
  unit: hours
  description: Landing page work is capped at 10 included hours.
- id: landing-page-revisions
  type: included_revisions
  deliverable_id: landing-page
  value: 2
  unit: rounds
  description: Landing page work includes up to 2 revision rounds.

## Billing Rules
- id: bill-out-of-scope
  rule_type: out_of_scope_hourly
  trigger: Work outside contracted deliverables
  rate: 150
  unit: hour
  currency: USD
  description: Out-of-scope work is billable at 150 USD per hour.
- id: bill-revision-overage
  rule_type: revision_overage_hourly
  trigger: Revision rounds beyond included cap
  rate: 125
  unit: hour
  currency: USD
  description: Revision overages are billable at 125 USD per hour.

## Exclusions
- development
- CRM migration

## Assumptions
- Work logs provide hours and task category for each work item.
- Billing occurs only when an explicit rate exists in the contract.
