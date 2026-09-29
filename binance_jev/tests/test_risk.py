import unittest
from decimal import Decimal

from jevbot.domain import SymbolRules
from jevbot.risk import loss_halt, size_entry


D = Decimal


class RiskTests(unittest.TestCase):
    def setUp(self):
        self.rules = SymbolRules("BTCUSDT", D("0.1"), D("0.001"), D("0.001"), D("100"))

    def test_size_limited_by_loss_budget_after_step_rounding(self):
        plan = size_entry(D("1000"), D("50000"), D("333.333333"), D("0.0012"), self.rules, D("1000"), "LONG")
        self.assertIsNotNone(plan)
        self.assertEqual(plan.quantity, D("0.008"))
        self.assertLessEqual(plan.worst_loss, D("5"))
        self.assertLessEqual(plan.quantity * plan.entry_price, D("500"))

    def test_minimum_notional_does_not_increase_risk_quantity(self):
        rules = SymbolRules("BTCUSDT", D("0.1"), D("0.001"), D("0.001"), D("1000"))
        self.assertIsNone(size_entry(D("1000"), D("50000"), D("333.333333"), D("0.0012"), rules, D("1000"), "LONG"))

    def test_stop_too_close_to_cost_skips_entry(self):
        self.assertIsNone(size_entry(D("1000"), D("50000"), D("100"), D("0.002"), self.rules, D("1000"), "SHORT"))

    def test_size_respects_market_exit_step_as_well_as_limit_entry_step(self):
        rules = SymbolRules("BTCUSDT", D("0.1"), D("0.003"), D("0.003"), D("100"), market_step_size=D("0.002"))
        plan = size_entry(D("1000"), D("50000"), D("333.333333"), D("0.0012"), rules, D("1000"), "LONG")
        self.assertIsNotNone(plan)
        self.assertEqual(plan.quantity % D("0.003"), D("0"))
        self.assertEqual(plan.quantity % D("0.002"), D("0"))

    def test_loss_halt_includes_daily_and_cumulative_boundaries(self):
        self.assertFalse(loss_halt(D("1000"), D("990"), D("980.21")))
        self.assertTrue(loss_halt(D("1000"), D("990"), D("970.2")))
        self.assertTrue(loss_halt(D("1000"), D("1000"), D("900")))


if __name__ == "__main__":
    unittest.main()
