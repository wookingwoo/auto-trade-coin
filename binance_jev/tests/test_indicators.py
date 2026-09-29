import unittest
from decimal import Decimal

from jevbot.domain import Candle
from jevbot.indicators import build_features


def candles(interval_ms, count=301):
    end_ms = 1_500_000_000_000
    return [
        Candle(end_ms - (count - i) * interval_ms, end_ms - (count - i - 1) * interval_ms - 1,
               Decimal(str(100 + i)), Decimal(str(102 + i)),
               Decimal(str(99 + i)), Decimal(str(101 + i)), Decimal("10"))
        for i in range(count)
    ]


class IndicatorTests(unittest.TestCase):
    def test_discards_open_candle_and_uses_only_closed_300(self):
        data = {"5m": candles(300_000), "15m": candles(900_000), "1h": candles(3_600_000)}
        now = 1_500_000_000_000 - 1
        data["5m"][-1] = Candle(data["5m"][-1].open_time_ms, data["5m"][-1].close_time_ms,
                                Decimal("1"), Decimal("10000"), Decimal("1"), Decimal("9999"), Decimal("99999"))
        features = build_features(data, now)
        self.assertEqual(features["5m"]["close"], 400.0)
        self.assertEqual(features["5m"]["volume_ratio"], 1.0)
        self.assertEqual(features["5m"]["rsi14"], 100.0)
        self.assertEqual(features["candle_close_ms"], data["5m"][-2].close_time_ms)

    def test_gap_in_candles_blocks_decision(self):
        data = {"5m": candles(300_000), "15m": candles(900_000), "1h": candles(3_600_000)}
        del data["15m"][30]
        with self.assertRaises(ValueError):
            build_features(data, 1_500_000_000_000 - 1)


if __name__ == "__main__":
    unittest.main()
