# BrightPath Creative Structured SOW

Client ID: demo-client
Client Name: BrightPath Creative
Currency: USD
Note: Additional requests outside the defined scope may be subject to additional billing upon review.

## Included Scope
- deliverable_id: ad-creatives
  name: Ad Creatives
  included_quantity: 4
  unit: creatives
  notes: Includes up to four ad creatives for the campaign.
- deliverable_id: landing-page
  name: Landing Page
  included_quantity: 1
  unit: page
  included_sections: 1
  notes: Includes one landing page with one base section.

## Limits
- limit_id: revision-rounds
  applies_to: ad-creatives, landing-page
  limit_type: revision_rounds
  included_quantity: 2
  unit: rounds
  notes: Includes up to two total revision rounds.

## Overage Pricing
- rule_id: extra-revisions
  trigger: extra_revision_round
  amount: 150
  unit: round
  notes: Extra revisions billed at 150 each.
- rule_id: extra-ad-creatives
  trigger: extra_ad_creative
  amount: 200
  unit: creative
  notes: Extra ad creatives billed at 200 each.
- rule_id: extra-landing-page-sections
  trigger: extra_landing_page_section
  amount: 300
  unit: section
  notes: Extra landing page sections billed at 300 each.
