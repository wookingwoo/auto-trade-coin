import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

from jevbot.binance import BinanceError, UnknownOrderOutcome
from jevbot.domain import EntryPlan, SymbolRules
from jevbot.execution import TradeExecutor, order_id
from jevbot.store import Journal


D = Decimal


class FakeExchange:
    def __init__(self, unknown=False, fail_stop=False, unknown_exit=False):
        self.calls = []
        self.quantity = D("0")
        self.algos = []
        self.unknown = unknown
        self.fail_stop = fail_stop
        self.unknown_exit = unknown_exit

    def get_positions(self):
        return [{"symbol": "BTCUSDT", "positionAmt": str(self.quantity), "entryPrice": "50000", "positionSide": "BOTH"}]

    def open_orders(self, symbol):
        return []

    def open_algo_orders(self, symbol):
        return list(self.algos)

    def place_ioc(self, symbol, side, quantity, price, client_id):
        self.calls.append("entry")
        if self.unknown:
            raise UnknownOrderOutcome("503")
        self.quantity = quantity if side == "BUY" else -quantity
        return {"status": "FILLED", "executedQty": str(quantity), "avgPrice": str(price), "clientOrderId": client_id}

    def query_order(self, symbol, client_id):
        if self.unknown or (self.unknown_exit and client_id.startswith("jvx")):
            raise BinanceError("not found yet")
        return {"status": "FILLED", "executedQty": str(abs(self.quantity)), "avgPrice": "50000"}

    def place_close_algo(self, symbol, side, order_type, trigger_price, client_id):
        self.calls.append(order_type)
        if self.fail_stop and order_type == "STOP_MARKET":
            raise BinanceError("rejected")
        self.algos.append({"clientAlgoId": client_id, "orderType": order_type, "symbol": symbol})
        return {"algoId": len(self.algos), "clientAlgoId": client_id}

    def query_algo(self, client_id):
        return next(order for order in self.algos if order["clientAlgoId"] == client_id)

    def place_reduce_market(self, symbol, side, quantity, client_id):
        self.calls.append("reduce")
        if self.unknown_exit:
            raise UnknownOrderOutcome("503")
        self.quantity = D("0")
        return {"status": "FILLED", "executedQty": str(quantity)}

    def cancel_algo(self, client_id):
        self.algos = [order for order in self.algos if order["clientAlgoId"] != client_id]
        return {}


class ExecutorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.journal = Journal(Path(self.temp.name) / "state.db")
        self.plan = EntryPlan("LONG", D("0.008"), D("50000"), D("49500"), D("51000"), D("4.48"), D("0.0012"))

    def tearDown(self):
        self.journal.close()
        self.temp.cleanup()

    def test_filled_entry_gets_stop_before_take_profit(self):
        exchange = FakeExchange()
        result = TradeExecutor(exchange, self.journal).enter("live:v1:BTCUSDT:100:e", "BTCUSDT", self.plan)
        self.assertEqual(result, "PROTECTED")
        self.assertEqual(exchange.calls, ["entry", "STOP_MARKET", "TAKE_PROFIT_MARKET"])

    def test_unknown_entry_response_never_resends_same_slot(self):
        exchange = FakeExchange(unknown=True)
        executor = TradeExecutor(exchange, self.journal)
        self.assertEqual(executor.enter("live:v1:BTCUSDT:100:e", "BTCUSDT", self.plan), "UNKNOWN")
        self.assertEqual(executor.enter("live:v1:BTCUSDT:100:e", "BTCUSDT", self.plan), "DUPLICATE")
        self.assertEqual(exchange.calls, ["entry"])

    def test_late_fill_after_unknown_response_is_protected_by_recovery(self):
        exchange = FakeExchange(unknown=True)
        executor = TradeExecutor(exchange, self.journal)
        slot = "live:v1:BTCUSDT:100:e"
        self.assertEqual(executor.enter(slot, "BTCUSDT", self.plan), "UNKNOWN")
        exchange.quantity = self.plan.quantity
        self.assertEqual(executor.recover(), "PROTECTED")
        self.assertEqual(self.journal.get("open_slot"), slot)
        self.assertEqual({item["orderType"] for item in exchange.algos}, {"STOP_MARKET", "TAKE_PROFIT_MARKET"})

    def test_unknown_entry_with_nonterminal_order_is_not_marked_no_fill(self):
        class PendingExchange(FakeExchange):
            def query_order(self, symbol, client_id):
                return {"status": "NEW", "executedQty": "0"}

        exchange = PendingExchange(unknown=True)
        executor = TradeExecutor(exchange, self.journal)
        slot = "live:v1:BTCUSDT:100:e"
        self.assertEqual(executor.enter(slot, "BTCUSDT", self.plan), "UNKNOWN")
        self.assertEqual(self.journal.intent(slot)["status"], "UNKNOWN")
        exchange.quantity = self.plan.quantity
        self.assertEqual(executor.recover(), "PROTECTED")

    def test_failed_position_query_after_fill_attempts_emergency_exit(self):
        exchange = FakeExchange()
        executor = TradeExecutor(exchange, self.journal)
        original = executor.current_position
        calls = 0

        def one_failed_query():
            nonlocal calls
            calls += 1
            if calls == 2:
                raise BinanceError("temporary")
            return original()

        executor.current_position = one_failed_query
        self.assertEqual(executor.enter("live:v1:BTCUSDT:100:e", "BTCUSDT", self.plan), "HALTED")
        self.assertEqual(exchange.quantity, D("0"))

    def test_stop_rejection_attempts_reduce_only_exit(self):
        exchange = FakeExchange(fail_stop=True)
        result = TradeExecutor(exchange, self.journal).enter("live:v1:BTCUSDT:100:e", "BTCUSDT", self.plan)
        self.assertEqual(result, "HALTED")
        self.assertEqual(exchange.calls, ["entry", "STOP_MARKET", "reduce"])
        self.assertEqual(exchange.quantity, D("0"))
        self.assertIsNotNone(self.journal.get("halt_reason"))

    def test_recovery_cleans_owned_take_profit_after_position_closed(self):
        exchange = FakeExchange()
        executor = TradeExecutor(exchange, self.journal)
        slot = "live:v1:BTCUSDT:100:e"
        self.assertEqual(executor.enter(slot, "BTCUSDT", self.plan), "PROTECTED")
        exchange.quantity = D("0")
        self.assertEqual(executor.recover(), "FLAT")
        self.assertEqual(exchange.algos, [])

    def test_unresolved_exit_is_not_sent_again(self):
        exchange = FakeExchange(unknown_exit=True)
        executor = TradeExecutor(exchange, self.journal)
        slot = "live:v1:BTCUSDT:100:e"
        exchange.quantity = D("0.008")
        self.journal.begin_intent(slot, "jv-entry", "BTCUSDT", "LONG", "0.008", "49500", "51000")
        self.assertEqual(executor.exit(slot, "BTCUSDT"), "UNKNOWN")
        self.assertEqual(executor.exit(slot, "BTCUSDT"), "UNKNOWN")
        self.assertEqual(exchange.calls, ["reduce"])

    def test_partial_fill_incompatible_with_market_step_uses_reduce_only_ioc(self):
        class OddFillExchange(FakeExchange):
            def get_rules(self, symbol):
                return SymbolRules(symbol, D("0.1"), D("0.001"), D("0.001"), D("100"), market_step_size=D("0.01"))

            def get_book(self, symbol):
                return D("50000"), D("50001"), 0

            def place_reduce_ioc(self, symbol, side, quantity, price, client_id):
                self.calls.append("reduce_ioc")
                self.quantity = D("0")
                return {"status": "FILLED", "executedQty": str(quantity)}

        exchange = OddFillExchange()
        exchange.quantity = D("0.003")
        slot = "live:v1:BTCUSDT:100:e"
        self.journal.begin_intent(slot, "jv-entry", "BTCUSDT", "LONG", "0.01", "49500", "51000")
        self.assertEqual(TradeExecutor(exchange, self.journal).exit(slot, "BTCUSDT"), "CLOSED")
        self.assertEqual(exchange.calls, ["reduce_ioc"])

    def test_partial_ioc_exit_retries_residual_with_new_client_id(self):
        class PartialExitExchange(FakeExchange):
            def __init__(self):
                super().__init__()
                self.orders = {}
                self.exit_quantities = []
                self.exit_ids = []

            def get_rules(self, symbol):
                return SymbolRules(symbol, D("0.1"), D("0.001"), D("0.001"), D("100"), market_step_size=D("0.01"))

            def get_book(self, symbol):
                return D("50000"), D("50001"), 0

            def place_reduce_ioc(self, symbol, side, quantity, price, client_id):
                self.exit_quantities.append(quantity)
                self.exit_ids.append(client_id)
                filled = D("0.001") if len(self.exit_ids) == 1 else quantity
                self.quantity -= filled
                self.orders[client_id] = {"status": "EXPIRED" if filled < quantity else "FILLED", "executedQty": str(filled)}
                return self.orders[client_id]

            def query_order(self, symbol, client_id):
                return self.orders[client_id]

        exchange = PartialExitExchange()
        exchange.quantity = D("0.003")
        slot = "live:v1:BTCUSDT:100:e"
        self.journal.begin_intent(slot, "jv-entry", "BTCUSDT", "LONG", "0.003", "49500", "51000")
        executor = TradeExecutor(exchange, self.journal)
        self.assertEqual(executor.exit(slot, "BTCUSDT"), "EXITING")
        path = self.journal.path
        self.journal.close()
        self.journal = Journal(path)
        executor = TradeExecutor(exchange, self.journal)
        self.assertEqual(executor.recover(), "PROTECTED")
        self.assertEqual(self.journal.intent(slot)["status"], "EXITING")
        self.assertEqual(executor.exit(slot, "BTCUSDT"), "CLOSED")
        self.assertEqual(exchange.exit_quantities, [D("0.003"), D("0.002")])
        self.assertEqual(len(set(exchange.exit_ids)), 2)
        self.assertEqual(exchange.quantity, D("0"))

    def test_terminal_exit_retries_are_bounded(self):
        class UnfilledExitExchange(FakeExchange):
            def __init__(self):
                super().__init__()
                self.exit_ids = []

            def place_reduce_market(self, symbol, side, quantity, client_id):
                self.exit_ids.append(client_id)
                return {"status": "EXPIRED", "executedQty": "0"}

            def query_order(self, symbol, client_id):
                return {"status": "EXPIRED", "executedQty": "0"}

        exchange = UnfilledExitExchange()
        exchange.quantity = D("0.008")
        slot = "live:v1:BTCUSDT:100:e"
        self.journal.begin_intent(slot, "jv-entry", "BTCUSDT", "LONG", "0.008", "49500", "51000")
        executor = TradeExecutor(exchange, self.journal)
        self.assertEqual([executor.exit(slot, "BTCUSDT") for _ in range(4)],
                         ["EXITING", "EXITING", "EXITING", "HALTED"])
        self.assertEqual(len(set(exchange.exit_ids)), 3)
        self.assertEqual(self.journal.get("halt_reason"), "exit_retry_exhausted")

    def test_reported_full_exit_with_residual_waits_for_reconciliation(self):
        exchange = FakeExchange()
        exchange.quantity = D("0.008")
        slot = "live:v1:BTCUSDT:100:e"
        self.journal.begin_intent(slot, "jv-entry", "BTCUSDT", "LONG", "0.008", "49500", "51000")
        self.journal.update_intent(slot, "EXITING")
        self.journal.set(f"exit_client_id:{slot}", order_id(slot, "x"))
        self.assertEqual(TradeExecutor(exchange, self.journal).exit(slot, "BTCUSDT"), "HALTED")
        self.assertEqual(exchange.calls, [])
        self.assertEqual(self.journal.get("halt_reason"), "exit_fill_position_mismatch")

    def test_recovery_keeps_exit_state_for_residual_position(self):
        exchange = FakeExchange()
        exchange.quantity = D("0.008")
        slot = "live:v1:BTCUSDT:100:e"
        self.journal.begin_intent(slot, "jv-entry", "BTCUSDT", "LONG", "0.008", "49500", "51000")
        self.journal.update_intent(slot, "EXITING")
        self.journal.set("open_slot", slot)
        self.journal.set(f"exit_client_id:{slot}", order_id(slot, "x"))
        transitions = []
        original = self.journal.update_intent

        def record_transition(key, status):
            transitions.append(status)
            original(key, status)

        self.journal.update_intent = record_transition
        self.assertEqual(TradeExecutor(exchange, self.journal).recover(), "PROTECTED")
        self.assertEqual(self.journal.intent(slot)["status"], "EXITING")
        self.assertEqual(transitions, [])

    def test_persisted_ioc_exit_id_can_resume_before_order_submission(self):
        class OddFillExchange(FakeExchange):
            def get_rules(self, symbol):
                return SymbolRules(symbol, D("0.1"), D("0.001"), D("0.001"), D("100"), market_step_size=D("0.01"))

            def get_book(self, symbol):
                return D("50000"), D("50001"), 0

            def place_reduce_ioc(self, symbol, side, quantity, price, client_id):
                self.quantity = D("0")
                return {"status": "FILLED", "executedQty": str(quantity)}

        exchange = OddFillExchange()
        exchange.quantity = D("0.003")
        slot = "live:v1:BTCUSDT:100:e"
        self.journal.begin_intent(slot, "jv-entry", "BTCUSDT", "LONG", "0.01", "49500", "51000")
        self.journal.set(f"exit_client_id:{slot}", order_id(slot, "l"))
        self.assertEqual(TradeExecutor(exchange, self.journal).exit(slot, "BTCUSDT"), "CLOSED")

    def test_journal_failure_after_fill_attempts_emergency_exit(self):
        exchange = FakeExchange()
        executor = TradeExecutor(exchange, self.journal)
        original = self.journal.update_intent

        def fail_protect(slot, status):
            if status == "PROTECTING":
                raise OSError("disk full")
            return original(slot, status)

        self.journal.update_intent = fail_protect
        self.assertEqual(executor.enter("live:v1:BTCUSDT:100:e", "BTCUSDT", self.plan), "HALTED")
        self.assertEqual(exchange.quantity, D("0"))


if __name__ == "__main__":
    unittest.main()
