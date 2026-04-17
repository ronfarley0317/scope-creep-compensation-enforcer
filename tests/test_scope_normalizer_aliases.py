import unittest

from app.services.scope_normalizer import ScopeNormalizer


class ScopeNormalizerAliasTest(unittest.TestCase):
    def test_different_field_names_produce_identical_normalized_output(self) -> None:
        client_config = {
            "client_id": "alias-client",
            "client_name": "Alias Client",
            "currency": "USD",
        }
        contract_rules = {
            "currency": "USD",
            "scope": {
                "deliverables": [
                    {
                        "id": "ad-creatives",
                        "name": "Ad Creatives",
                        "included_quantity": 4,
                        "unit": "creative",
                        "task_categories": ["ad_creative"],
                    }
                ],
                "limits": [],
                "billing_rules": [],
            },
            "assumptions": [],
            "interpretation": {},
        }
        field_mapping = {
            "field_aliases": {
                "deliverables": ["deliverable_hint", "deliverable_code", "deliverable"],
                "revisions": ["revision_number", "revision_count", "revisions_completed"],
                "hours": ["hours", "effort_hours", "logged_hours"],
                "assets": ["quantity", "delivered_units", "asset_count"],
            },
            "work_item_mapping": {
                "work_item_id": "id",
                "work_date": "performed_on",
                "task_category": "category",
                "deliverable_hint": "deliverables",
                "description": "description",
                "hours": "hours",
                "revision_count": "revisions",
            },
            "quantity_mapping": {
                "by_category": {
                    "ad_creative": {"field": "assets", "unit": "creative"},
                }
            },
            "normalization_rules": {
                "deliverable_aliases": {"ad-creatives": ["creative_pack"]},
                "category_aliases": {"ad_creative": ["ad_variant"]},
                "unit_aliases": {"creative": ["creatives"]},
                "quantity_defaults": {},
            },
        }
        normalizer = ScopeNormalizer(client_config, contract_rules, field_mapping)

        raw_work_log_a = {
            "work_items": [
                {
                    "id": "item-1",
                    "deliverable_hint": "creative_pack",
                    "category": "ad_variant",
                    "description": "Delivered six creatives",
                    "hours": 12,
                    "quantity": 6,
                    "revision_number": 3,
                    "performed_on": "2026-04-30",
                }
            ]
        }
        raw_work_log_b = {
            "work_items": [
                {
                    "id": "item-1",
                    "deliverable_code": "creative_pack",
                    "category": "ad_variant",
                    "description": "Delivered six creatives",
                    "effort_hours": 12,
                    "delivered_units": 6,
                    "revisions_completed": 3,
                    "performed_on": "2026-04-30",
                }
            ]
        }

        normalized_a = [item.to_dict() for item in normalizer.normalize_work_log(raw_work_log_a)]
        normalized_b = [item.to_dict() for item in normalizer.normalize_work_log(raw_work_log_b)]

        self.assertEqual(normalized_a, normalized_b)
        self.assertEqual(normalized_a[0]["deliverable_hint"], "ad-creatives")
        self.assertEqual(normalized_a[0]["quantity"], 6.0)
        self.assertEqual(normalized_a[0]["quantity_unit"], "creative")
        self.assertEqual(normalized_a[0]["revision_number"], 3)
        self.assertEqual(normalized_a[0]["hours"], 12.0)


if __name__ == "__main__":
    unittest.main()
