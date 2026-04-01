from __future__ import annotations

from datetime import UTC, datetime

from app.clients.binance import BinanceFuturesClient
from app.exceptions import DataCollectionError
from app.models.market import MarketSnapshot


class BinanceMarketDataService:
    """Fetch Binance futures market data required by the decision pipeline."""

    def __init__(self, client: BinanceFuturesClient) -> None:
        self.client = client

    def fetch_market_snapshot(self, run_id: str, symbol: str) -> MarketSnapshot:
        try:
            candles_1h = self.client.get_klines(symbol, "1h", limit=120)
            candles_4h = self.client.get_klines(symbol, "4h", limit=120)
            candles_1d = self.client.get_klines(symbol, "1d", limit=120)
            mark_price = self.client.get_mark_price(symbol)
            funding_rate = self.client.get_funding_rate(symbol)
            open_interest = self.client.get_open_interest(symbol)
            symbol_rules = self.client.get_exchange_info(symbol)
        except Exception as exc:  # noqa: BLE001
            raise DataCollectionError(f"Failed to collect market data for {symbol}: {exc}") from exc

        if not candles_1h or not candles_4h or not candles_1d:
            raise DataCollectionError(f"Missing candles for {symbol}.")

        return MarketSnapshot(
            run_id=run_id,
            symbol=symbol,
            collected_at=datetime.now(tz=UTC),
            current_price=candles_1h[-1].close,
            mark_price=mark_price["mark_price"],
            funding_rate=funding_rate if funding_rate is not None else mark_price["last_funding_rate"],
            open_interest=open_interest,
            candles_1h=candles_1h,
            candles_4h=candles_4h,
            candles_1d=candles_1d,
            symbol_rules=symbol_rules,
        )

