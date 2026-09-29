import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

from jevbot.domain import EntryPlan
from jevbot.paper import PaperFutures
from jevbot.runner import Settings, TradingRunner
from jevbot.store import Journal


class FakePublic:
    mark = Decimal("50000")

    def get_book(self, symbol):
        return Decimal("50000"), Decimal("50001"), 1000

    def get_mark(self, symbol):
        return {"markPrice": str(self.mark), "lastFundingRate": "0", "nextFundingTime": 9999999999999}


class PaperTests(unittest.TestCase):
    def test_paper_fill_and_account_survive_restart(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "paper.db"
            exchange = PaperFutures(FakePublic(), path, Decimal("1000"))
            entry = exchange.place_ioc("BTCUSDT", "BUY", Decimal("0.005"), Decimal("50010"), "jv-entry")
            self.assertEqual(entry["status"], "FILLED")
            self.assertEqual(exchange.get_positions()[0]["positionAmt"], "0.005")
            exchange.place_close_algo("BTCUSDT", "SELL", "STOP_MARKET", Decimal("49000"), "jv-stop")
            restored = PaperFutures(FakePublic(), path, Decimal("9999"))
            self.assertEqual(restored.get_positions()[0]["positionAmt"], "0.005")
            self.assertEqual(len(restored.open_algo_orders("BTCUSDT")), 1)
            restored.place_reduce_market("BTCUSDT", "SELL", Decimal("0.005"), "jv-exit")
            self.assertEqual(restored.get_positions(), [])
            self.assertLess(Decimal(restored.get_account()["totalMarginBalance"]), Decimal("1000"))

    def test_paper_stop_triggers_when_mark_crosses_price(self):
        with tempfile.TemporaryDirectory() as folder:
            public = FakePublic()
            exchange = PaperFutures(public, Path(folder) / "paper.db", Decimal("1000"))
            exchange.place_ioc("BTCUSDT", "BUY", Decimal("0.005"), Decimal("50010"), "jv-entry")
            exchange.place_close_algo("BTCUSDT", "SELL", "STOP_MARKET", Decimal("49000"), "jv-stop")
            public.mark = Decimal("48990")
            self.assertEqual(exchange.check_triggers(), "STOP_MARKET")
            self.assertEqual(exchange.get_positions(), [])
            self.assertLess(Decimal(exchange.get_account()["totalWalletBalance"]), Decimal("995"))

    def test_watch_loop_applies_paper_stop_before_next_strategy_slot(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "paper.db"
            public = FakePublic()
            exchange = PaperFutures(public, path, Decimal("1000"))
            journal = Journal(path)
            journal.initialize(Decimal("1000"), "2026-09-29")
            runner = TradingRunner(Settings("paper", "", "", "key", path), exchange, journal)
            plan = EntryPlan("LONG", Decimal("0.005"), Decimal("50010"), Decimal("49000"), Decimal("52000"), Decimal("5.4"), Decimal("0.0012"))
            self.assertEqual(runner.executor.enter("paper:v1:BTCUSDT:100:e", "BTCUSDT", plan), "PROTECTED")
            public.mark = Decimal("48990")
            runner.risk_tick()
            remaining = exchange.get_positions()
            journal.close()
            self.assertEqual(remaining, [])


if __name__ == "__main__":
    unittest.main()
