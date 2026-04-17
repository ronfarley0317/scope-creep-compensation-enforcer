# BrightPath Creative Campaign SOW

Client ID: demo-client
Client Name: BrightPath Creative
Currency: USD
Note: Additional requests outside the defined scope may be subject to additional billing upon review.

## Included Scope
- deliverable_id: ad-creatives
  name: Ad Creatives
  included_quantity: 4
  unit: creatives
  notes: Includes four paid social ad creatives for the monthly campaign package.
- deliverable_id: landing-page
  name: Landing Page
  included_quantity: 1
  unit: page
  included_sections: 1
  notes: Includes one landing page with one core hero/content section.

## Limits
- limit_id: revision-rounds
  applies_to: ad-creatives, landing-page
  limit_type: revision_rounds
  included_quantity: 2
  unit: rounds
  notes: Includes two combined revision rounds across all in-scope deliverables.

## Overage Pricing
- rule_id: extra-revisions
  trigger: extra_revision_round
  amount: 150
  unit: round
  notes: Additional revision rounds are billed at 150 each.
- rule_id: extra-ad-creatives
  trigger: extra_ad_creative
  amount: 200
  unit: creative
  notes: Additional ad creatives are billed at 200 each.
- rule_id: extra-landing-page-sections
  trigger: extra_landing_page_section
  amount: 300
  unit: section
  notes: Additional landing page sections are billed at 300 each.
