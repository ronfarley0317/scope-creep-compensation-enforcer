import unittest
from pathlib import Path

from app.workflows.run_single_client import run_single_client


class RevenueLeakageProjectionTest(unittest.TestCase):
    def test_demo_projection_uses_observation_window_and_events(self) -> None:
        result = run_single_client(Path("configs/clients/demo-client"))
        projection = result["revenue_leakage_projection"]

        self.assertEqual(projection["event_count"], 3)
        self.assertEqual(projection["observation_span_days"], 30)
        self.assertEqual(projection["projection_cadence"], "weekly")
        self.assertEqual(projection["projected_monthly_leakage"], 1013.83)
        self.assertEqual(projection["confidence_level"], "high")
        self.assertEqual(projection["recovery_opportunity_min"], 861.76)
        self.assertEqual(projection["recovery_opportunity_max"], 1013.83)
        self.assertIn("3 scope-creep event(s) across 30 days", projection["methodology_explanation"])
        self.assertIn("weekly leakage rate", projection["methodology_explanation"])


if __name__ == "__main__":
    unittest.main()
