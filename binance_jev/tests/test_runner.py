import os
import tempfile
import time
import unittest
from decimal import Decimal
from pathlib import Path
from unittest.mock import Mock, patch

from jevbot.binance import BinanceError
from jevbot.domain import Candle, SymbolRules
from jevbot.jev import Decision
from jevbot.paper import PaperFutures
from jevbot.runner import Settings, TradingRunner, closed_slot, ioc_limit_price, verify_account_mode
from jevbot.store import Journal


D = Decimal


class FakePreflightExchange:
    def __init__(self, hedge=False, margin_type="ISOLATED"):
        self.hedge = hedge
        self.margin_type = margin_type

    def get_position_mode(self):
        return {"dualSidePosition": self.hedge}

    def get_multi_asset_mode(self):
        return {"multiAssetsMargin": False}

    def get_symbol_config(self, symbol):
        return {"marginType": self.margin_type, "leverage": 2}


class RunnerTests(unittest.TestCase):
    def test_5minute_slot_starts_after_candle_close(self):
        self.assertIsNone(closed_slot(300_000 + 1))
        self.assertEqual(closed_slot(300_000 + 2_000), 299_999)
        self.assertIsNone(closed_slot(300_000 + 31_000))

    def test_preflight_rejects_hedge_or_cross_mode(self):
        with self.assertRaises(BinanceError):
            verify_account_mode(FakePreflightExchange(hedge=True), ("BTCUSDT",))
        with self.assertRaises(BinanceError):
            verify_account_mode(FakePreflightExchange(margin_type="CROSSED"), ("BTCUSDT",))
        verify_account_mode(FakePreflightExchange(), ("BTCUSDT",))

    def test_ioc_price_never_exceeds_five_basis_points(self):
        rules = SymbolRules("BTCUSDT", D("0.1"), D("0.001"), D("0.001"), D("100"))
        self.assertEqual(ioc_limit_price("LONG", D("50000"), rules), D("50025"))
        self.assertEqual(ioc_limit_price("SHORT", D("50000"), rules), D("49975"))

    def test_live_mode_needs_explicit_activation(self):
        env = {"JEVBOT_MODE": "live", "BINANCE_API_KEY": "key", "BINANCE_API_SECRET": "secret", "TYPESAFE_API_KEY": "test"}
        with patch.dict(os.environ, env, clear=True):
            with self.assertRaises(ValueError):
                Settings.from_env()
        env["JEVBOT_LIVE_ENABLED"] = "YES"
        with patch.dict(os.environ, env, clear=True):
            self.assertEqual(Settings.from_env().mode, "live")

    def test_external_heartbeat_requires_https(self):
        env = {"JEVBOT_MODE": "paper", "TYPESAFE_API_KEY": "key", "JEVBOT_HEARTBEAT_URL": "http://example.com/ping"}
        with patch.dict(os.environ, env, clear=True):
            with self.assertRaises(ValueError):
                Settings.from_env()

    def test_external_heartbeat_sends_no_account_data(self):
        with tempfile.TemporaryDirectory() as folder:
            journal = Journal(Path(folder) / "state.db")
            settings = Settings("paper", "", "", "key", journal.path, heartbeat_url="https://monitor.example/ping")
            runner = TradingRunner(settings, object(), journal)
            response = Mock()
            with patch("jevbot.runner.httpx.get", return_value=response) as send:
                runner._send_heartbeat()
            send.assert_called_once_with("https://monitor.example/ping", timeout=5)
            journal.close()

    def test_risk_watcher_never_replaces_strategy_journal(self):
        with tempfile.TemporaryDirectory() as folder:
            primary = Journal(Path(folder) / "state.db")
            runner = TradingRunner(Settings("paper", "", "", "key", primary.path), object(), primary)
            observed = []

            def one_tick(watcher):
                observed.append(watcher is not runner and watcher.journal is not primary)
                runner.stop_event.set()

            with patch.object(TradingRunner, "risk_tick", one_tick):
                runner._watch()
            primary.close()
            self.assertEqual(observed, [True])
            self.assertIs(runner.journal, primary)

    def test_loss_halt_reason_is_not_overwritten_by_flatten_action(self):
        class LowEquityExchange:
            def get_account(self):
                return {"totalMarginBalance": "890", "availableBalance": "890"}

            def get_positions(self):
                return []

        with tempfile.TemporaryDirectory() as folder:
            journal = Journal(Path(folder) / "state.db")
            journal.initialize(D("1000"), "2026-09-29")
            runner = TradingRunner(Settings("paper", "", "", "key", journal.path), LowEquityExchange(), journal)
            runner.risk_tick()
            reason = journal.get("halt_reason")
            journal.close()
            self.assertEqual(reason, "loss_limit")

    def test_risk_watcher_reconciles_late_unknown_fill(self):
        from jevbot.execution import TradeExecutor
        from tests.test_execution import FakeExchange

        with tempfile.TemporaryDirectory() as folder:
            journal = Journal(Path(folder) / "state.db")
            journal.initialize(D("1000"), "2026-09-29")
            exchange = FakeExchange(unknown=True)
            exchange.get_account = lambda: {"totalMarginBalance": "1000"}
            runner = TradingRunner(Settings("paper", "", "", "key", journal.path), exchange, journal)
            slot = "paper:v1:BTCUSDT:100:e"
            from jevbot.domain import EntryPlan
            plan = EntryPlan("LONG", D("0.008"), D("50000"), D("49500"), D("51000"), D("4.48"), D("0.0012"))
            self.assertEqual(runner.executor.enter(slot, "BTCUSDT", plan), "UNKNOWN")
            exchange.quantity = D("0.008")
            runner.risk_tick()
            self.assertEqual(journal.get("open_slot"), slot)
            journal.close()

    def test_live_transfer_halts_before_new_entry(self):
        class TransferExchange:
            def get_income_history(self, start_ms, end_ms, page, limit, income_type):
                return [{"incomeType": "TRANSFER", "asset": "USDT", "income": "100", "time": start_ms + 1000, "tranId": 1}]

        with tempfile.TemporaryDirectory() as folder:
            journal = Journal(Path(folder) / "state.db")
            journal.bind_environment("live")
            journal.initialize(D("1000"), "2026-09-29")
            runner = TradingRunner(Settings("live", "key", "secret", "key", journal.path), TransferExchange(), journal)
            self.assertTrue(runner._check_transfers(int(time.time() * 1000), force=True))
            self.assertEqual(journal.get("halt_reason"), "external_transfer")
            journal.close()

    def test_unrecognized_income_also_halts_live_entry(self):
        class BonusExchange:
            def get_income_history(self, start_ms, end_ms, page, limit, income_type):
                return [{"incomeType": "WELCOME_BONUS", "asset": "USDT", "income": "10", "time": start_ms + 1, "tranId": 2}]

        with tempfile.TemporaryDirectory() as folder:
            journal = Journal(Path(folder) / "state.db")
            journal.bind_environment("live")
            journal.initialize(D("1000"), "2026-09-29")
            runner = TradingRunner(Settings("live", "key", "secret", "key", journal.path), BonusExchange(), journal)
            self.assertTrue(runner._check_transfers(int(time.time() * 1000), force=True))
            self.assertEqual(journal.get("halt_reason"), "unrecognized_income")
            journal.close()

    def test_owned_trading_income_does_not_halt_live_entry(self):
        class TradingIncomeExchange:
            def get_income_history(self, start_ms, end_ms, page, limit, income_type):
                return [{"incomeType": "COMMISSION", "symbol": "BTCUSDT", "asset": "USDT", "income": "-0.1", "time": start_ms + 1}]

        with tempfile.TemporaryDirectory() as folder:
            journal = Journal(Path(folder) / "state.db")
            journal.bind_environment("live")
            journal.initialize(D("1000"), "2026-09-29")
            runner = TradingRunner(Settings("live", "key", "secret", "key", journal.path), TradingIncomeExchange(), journal)
            self.assertFalse(runner._check_transfers(int(time.time() * 1000), force=True))
            self.assertIsNone(journal.get("halt_reason"))
            journal.close()

    def test_live_income_query_failure_blocks_entry(self):
        class FailedExchange:
            def get_income_history(self, *args):
                raise BinanceError("unavailable")

        with tempfile.TemporaryDirectory() as folder:
            journal = Journal(Path(folder) / "state.db")
            journal.bind_environment("live")
            journal.initialize(D("1000"), "2026-09-29")
            runner = TradingRunner(Settings("live", "key", "secret", "key", journal.path), FailedExchange(), journal)
            self.assertTrue(runner._check_transfers(int(time.time() * 1000), force=True))
            self.assertEqual(journal.get("halt_reason"), "transfer_check_error")
            journal.close()

    def test_shutdown_waits_for_risk_watcher_before_closing_resources(self):
        with tempfile.TemporaryDirectory() as folder:
            journal = Journal(Path(folder) / "state.db")
            runner = TradingRunner(Settings("paper", "", "", "key", journal.path), object(), journal)
            seen = []

            def finish_watch():
                time.sleep(.05)
                seen.append("watch_finished")

            runner.startup = lambda: "FLAT"
            runner.run_slot = lambda: runner.stop_event.set()
            runner._watch = finish_watch
            runner.run_forever()
            journal.close()
            self.assertEqual(seen, ["watch_finished"])

    def test_closed_slot_can_open_and_protect_paper_position(self):
        boundary = (int(time.time() * 1000) // 3_600_000 + 1) * 3_600_000
        now_ms = boundary + 2_000

        class PublicMarket:
            def server_time(self):
                return now_ms

            def get_candles(self, symbol, interval, limit):
                duration = {"5m": 300_000, "15m": 900_000, "1h": 3_600_000}[interval]
                return [Candle(boundary - (302 - i) * duration, boundary - (301 - i) * duration - 1,
                               D("50000"), D("50100"), D("49900"), D("50000"), D("10")) for i in range(302)]

            def get_book(self, symbol):
                return D("50000"), D("50001"), now_ms

            def get_mark(self, symbol):
                return {"markPrice": "50000", "lastFundingRate": "0", "nextFundingTime": now_ms + 10_000_000}

            def get_rules(self, symbol):
                return SymbolRules(symbol, D("0.1"), D("0.001"), D("0.001"), D("100"), D("100"))

        class LongDecider:
            def decide(self, state, held):
                return Decision("OPEN_LONG", {"OPEN_LONG": .7, "OPEN_SHORT": .1, "WAIT": .2}, .8)

        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "paper.db"
            exchange = PaperFutures(PublicMarket(), path, D("700"))
            journal = Journal(path)
            settings = Settings("paper", "", "", "key", path, symbols=("BTCUSDT",))
            runner = TradingRunner(settings, exchange, journal, LongDecider())
            with patch("jevbot.runner.time.time", return_value=now_ms / 1000):
                self.assertEqual(runner.startup(), "FLAT")
                result = runner.run_slot(now_ms)
            quantity = exchange.get_positions()[0]["positionAmt"] if exchange.get_positions() else None
            protections = exchange.open_algo_orders("BTCUSDT")
            journal.close()
            self.assertEqual(result, "PROTECTED")
            self.assertIsNotNone(quantity)
            self.assertEqual({item["orderType"] for item in protections}, {"STOP_MARKET", "TAKE_PROFIT_MARKET"})


if __name__ == "__main__":
    unittest.main()
