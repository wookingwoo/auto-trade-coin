import json
import unittest
from decimal import Decimal
from urllib.parse import parse_qs

import httpx

from jevbot.binance import BinanceFutures, UnknownOrderOutcome


class BinanceTests(unittest.TestCase):
    def make_client(self, handler):
        return BinanceFutures("key", "secret", transport=httpx.MockTransport(handler))

    def test_signed_ioc_order_uses_decimal_strings_and_signature(self):
        seen = []

        def handler(request):
            seen.append(request)
            return httpx.Response(200, json={"status": "FILLED", "executedQty": "0.001", "avgPrice": "50000"})

        client = self.make_client(handler)
        client.place_ioc("BTCUSDT", "BUY", Decimal("0.001"), Decimal("50000.10"), "jv-test-entry")
        request = seen[0]
        params = parse_qs(request.url.query.decode())
        self.assertEqual(request.url.path, "/fapi/v1/order")
        self.assertEqual(params["quantity"], ["0.001"])
        self.assertEqual(params["price"], ["50000.10"])
        self.assertEqual(params["timeInForce"], ["IOC"])
        self.assertEqual(params["type"], ["LIMIT"])
        self.assertIn("signature", params)
        self.assertEqual(request.headers["X-MBX-APIKEY"], "key")

    def test_conditional_close_omits_quantity_and_reduce_only(self):
        seen = []

        def handler(request):
            seen.append(request)
            return httpx.Response(200, json={"algoId": 1})

        self.make_client(handler).place_close_algo("BTCUSDT", "SELL", "STOP_MARKET", Decimal("49000"), "jv-stop")
        params = parse_qs(seen[0].url.query.decode())
        self.assertEqual(seen[0].url.path, "/fapi/v1/algoOrder")
        self.assertEqual(params["closePosition"], ["true"])
        self.assertEqual(params["workingType"], ["MARK_PRICE"])
        self.assertNotIn("quantity", params)
        self.assertNotIn("reduceOnly", params)

    def test_order_503_has_unknown_outcome_not_retriable_rejection(self):
        def handler(request):
            return httpx.Response(503, json={"code": -1008, "msg": "busy"})

        with self.assertRaises(UnknownOrderOutcome):
            self.make_client(handler).place_ioc("BTCUSDT", "BUY", Decimal("0.001"), Decimal("50000"), "jv-test")

    def test_market_exit_is_reduce_only(self):
        seen = []

        def handler(request):
            seen.append(request)
            return httpx.Response(200, json={"status": "FILLED"})

        self.make_client(handler).place_reduce_market("BTCUSDT", "SELL", Decimal("0.002"), "jv-exit")
        params = parse_qs(seen[0].url.query.decode())
        self.assertEqual(params["reduceOnly"], ["true"])
        self.assertEqual(params["type"], ["MARKET"])

    def test_limit_ioc_fallback_exit_is_reduce_only(self):
        seen = []

        def handler(request):
            seen.append(request)
            return httpx.Response(200, json={"status": "FILLED"})

        self.make_client(handler).place_reduce_ioc("BTCUSDT", "SELL", Decimal("0.003"), Decimal("49750"), "jv-exit-ioc")
        params = parse_qs(seen[0].url.query.decode())
        self.assertEqual(params["reduceOnly"], ["true"])
        self.assertEqual(params["type"], ["LIMIT"])
        self.assertEqual(params["timeInForce"], ["IOC"])

    def test_account_config_reads_trading_permission_separately_from_v3_balance(self):
        seen = []

        def handler(request):
            seen.append(request.url.path)
            if request.url.path == "/fapi/v1/accountConfig":
                return httpx.Response(200, json={"canTrade": True})
            if request.url.path == "/fapi/v3/account":
                return httpx.Response(200, json={"totalMarginBalance": "1000"})
            raise AssertionError(request.url.path)

        client = self.make_client(handler)
        self.assertTrue(client.get_account_config()["canTrade"])
        self.assertEqual(client.get_account()["totalMarginBalance"], "1000")
        self.assertEqual(seen, ["/fapi/v1/accountConfig", "/fapi/v3/account"])

    def test_transfer_income_request_is_signed_and_bounded(self):
        seen = []

        def handler(request):
            seen.append(request)
            return httpx.Response(200, json=[])

        self.make_client(handler).get_income_history(1000, 2000, 1, 1000, "TRANSFER")
        params = parse_qs(seen[0].url.query.decode())
        self.assertEqual(seen[0].url.path, "/fapi/v1/income")
        self.assertEqual(params["incomeType"], ["TRANSFER"])
        self.assertEqual(params["startTime"], ["1000"])
        self.assertEqual(params["endTime"], ["2000"])
        self.assertIn("signature", params)


if __name__ == "__main__":
    unittest.main()
