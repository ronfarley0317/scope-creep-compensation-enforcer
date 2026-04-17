import unittest
from pathlib import Path

from app.services.contract_parser import ContractParser


class ContractParserTest(unittest.TestCase):
    def test_parse_demo_contract(self) -> None:
        contract = ContractParser().parse_file(
            Path("configs/clients/demo-client/contract.md")
        )

        self.assertEqual(contract.client_id, "demo-client")
        self.assertEqual(contract.currency, "USD")
        self.assertEqual(len(contract.deliverables), 2)
        self.assertEqual(contract.deliverables[0].id, "landing-page")
        self.assertEqual(contract.deliverables[0].included_revisions, 2)
        self.assertEqual(contract.billing_rules[0].rate, 150.0)
        self.assertIn("development", contract.exclusions)


if __name__ == "__main__":
    unittest.main()
