from __future__ import annotations

import hashlib
import hmac
import time
from decimal import Decimal
from datetime import UTC, datetime
from urllib.parse import urlencode

import httpx

from app.config import Settings
from app.exceptions import BinanceAPIError
from app.models.market import Candle, SymbolRules


class BinanceFuturesClient:
    """Minimal Binance USD-M futures REST client."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.base_url = settings.binance_base_url.rstrip("/")
        self._client = httpx.Client(timeout=15.0)

    def _request(
        self,
        method: str,
        path: str,
        params: dict | None = None,
        signed: bool = False,
    ) -> dict | list:
        params = self._normalize_params(params or {})
        headers: dict[str, str] = {}

        if signed:
            if not self.settings.binance_api_key or not self.settings.binance_api_secret:
                raise BinanceAPIError("Binance API credentials are required for signed endpoints.")
            params["timestamp"] = int(time.time() * 1000)
            query_string = urlencode(params, doseq=True)
            signature = hmac.new(
                self.settings.binance_api_secret.encode("utf-8"),
                query_string.encode("utf-8"),
                hashlib.sha256,
            ).hexdigest()
            params["signature"] = signature
            headers["X-MBX-APIKEY"] = self.settings.binance_api_key

        response = self._client.request(method, f"{self.base_url}{path}", params=params, headers=headers)
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise BinanceAPIError(
                f"Binance request failed: {response.status_code} {response.text}"
            ) from exc
        return response.json()

    @staticmethod
    def _normalize_params(params: dict) -> dict:
        normalized: dict = {}
        for key, value in params.items():
            if isinstance(value, float):
                normalized[key] = BinanceFuturesClient._format_decimal(value)
            else:
                normalized[key] = value
        return normalized

    @staticmethod
    def _format_decimal(value: float) -> str:
        decimal_value = Decimal(str(value))
        rendered = format(decimal_value, "f")
        rendered = rendered.rstrip("0").rstrip(".")
        return rendered if rendered else "0"

    def get_exchange_info(self, symbol: str) -> SymbolRules:
        payload = self._request("GET", "/fapi/v1/exchangeInfo")
        for item in payload["symbols"]:
            if item["symbol"] != symbol:
                continue

            filters = {entry["filterType"]: entry for entry in item["filters"]}
            return SymbolRules(
                symbol=symbol,
                tick_size=float(filters["PRICE_FILTER"]["tickSize"]),
                step_size=float(filters["LOT_SIZE"]["stepSize"]),
                min_qty=float(filters["LOT_SIZE"]["minQty"]),
                min_notional=float(filters["MIN_NOTIONAL"]["notional"]),
                price_precision=int(item["pricePrecision"]),
                quantity_precision=int(item["quantityPrecision"]),
            )
        raise BinanceAPIError(f"Symbol rules not found for {symbol}.")

    def get_klines(self, symbol: str, interval: str, limit: int = 120) -> list[Candle]:
        payload = self._request(
            "GET",
            "/fapi/v1/klines",
            params={"symbol": symbol, "interval": interval, "limit": limit},
        )
        candles: list[Candle] = []
        for row in payload:
            candles.append(
                Candle(
                    open_time=datetime.fromtimestamp(row[0] / 1000, tz=UTC),
                    open=float(row[1]),
                    high=float(row[2]),
                    low=float(row[3]),
                    close=float(row[4]),
                    volume=float(row[5]),
                    close_time=datetime.fromtimestamp(row[6] / 1000, tz=UTC),
                    quote_volume=float(row[7]),
                    trade_count=int(row[8]),
                )
            )
        return candles

    def get_mark_price(self, symbol: str) -> dict:
        payload = self._request("GET", "/fapi/v1/premiumIndex", params={"symbol": symbol})
        return {
            "mark_price": float(payload["markPrice"]),
            "last_funding_rate": float(payload["lastFundingRate"]),
            "next_funding_time": int(payload["nextFundingTime"]),
        }

    def get_funding_rate(self, symbol: str) -> float | None:
        payload = self._request(
            "GET",
            "/fapi/v1/fundingRate",
            params={"symbol": symbol, "limit": 1},
        )
        if not payload:
            return None
        return float(payload[-1]["fundingRate"])

    def get_open_interest(self, symbol: str) -> float | None:
        payload = self._request("GET", "/fapi/v1/openInterest", params={"symbol": symbol})
        value = payload.get("openInterest")
        return float(value) if value is not None else None

    def get_account_information(self) -> dict:
        return self._request("GET", "/fapi/v3/account", signed=True)

    def get_position_risk(self, symbol: str) -> list[dict]:
        payload = self._request(
            "GET",
            "/fapi/v3/positionRisk",
            params={"symbol": symbol},
            signed=True,
        )
        return list(payload)

    def get_all_orders(self, symbol: str, limit: int = 20) -> list[dict]:
        payload = self._request(
            "GET",
            "/fapi/v1/allOrders",
            params={"symbol": symbol, "limit": limit},
            signed=True,
        )
        return list(payload)

    def get_open_orders(self, symbol: str) -> list[dict]:
        payload = self._request(
            "GET",
            "/fapi/v1/openOrders",
            params={"symbol": symbol},
            signed=True,
        )
        return list(payload)

    def get_open_algo_orders(self, symbol: str) -> list[dict]:
        payload = self._request(
            "GET",
            "/fapi/v1/openAlgoOrders",
            params={"symbol": symbol},
            signed=True,
        )
        return list(payload)

    def change_leverage(self, symbol: str, leverage: int) -> dict:
        return self._request(
            "POST",
            "/fapi/v1/leverage",
            params={"symbol": symbol, "leverage": leverage},
            signed=True,
        )

    def cancel_all_open_orders(self, symbol: str) -> dict:
        return self._request(
            "DELETE",
            "/fapi/v1/allOpenOrders",
            params={"symbol": symbol},
            signed=True,
        )

    def cancel_all_algo_open_orders(self, symbol: str) -> dict:
        return self._request(
            "DELETE",
            "/fapi/v1/algoOpenOrders",
            params={"symbol": symbol},
            signed=True,
        )

    def cancel_algo_order(self, client_algo_id: str) -> dict:
        return self._request(
            "DELETE",
            "/fapi/v1/algoOrder",
            params={"clientAlgoId": client_algo_id},
            signed=True,
        )

    def create_market_order(
        self,
        symbol: str,
        side: str,
        quantity: float,
        client_order_id: str,
        reduce_only: bool = False,
    ) -> dict:
        params = {
            "symbol": symbol,
            "side": side,
            "type": "MARKET",
            "quantity": quantity,
            "newClientOrderId": client_order_id,
            "newOrderRespType": "RESULT",
        }
        if reduce_only:
            params["reduceOnly"] = "true"
        return self._request("POST", "/fapi/v1/order", params=params, signed=True)

    def create_trigger_close_order(
        self,
        symbol: str,
        side: str,
        order_type: str,
        stop_price: float,
        client_order_id: str,
        working_type: str = "MARK_PRICE",
    ) -> dict:
        params = {
            "algoType": "CONDITIONAL",
            "symbol": symbol,
            "side": side,
            "type": order_type,
            "triggerPrice": stop_price,
            "closePosition": "true",
            "workingType": working_type,
            "clientAlgoId": client_order_id,
            "newOrderRespType": "RESULT",
        }
        return self._request("POST", "/fapi/v1/algoOrder", params=params, signed=True)
