from __future__ import annotations

import hashlib
import hmac
import time
from decimal import Decimal
from urllib.parse import urlencode

import httpx

from .domain import Candle, SymbolRules, decimal_text


class BinanceError(RuntimeError):
    pass


class UnknownOrderOutcome(BinanceError):
    """A mutation may have reached Binance. Query state before any new request."""


class BinanceFutures:
    def __init__(
        self,
        api_key: str,
        api_secret: str,
        base_url: str = "https://fapi.binance.com",
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.api_key = api_key
        self.api_secret = api_secret
        self.base_url = base_url.rstrip("/")
        self.http = httpx.Client(timeout=10.0, transport=transport)

    def close(self) -> None:
        self.http.close()

    @staticmethod
    def _render(value: object) -> str:
        if isinstance(value, Decimal):
            return decimal_text(value)
        if isinstance(value, bool):
            return "true" if value else "false"
        return str(value)

    def _request(self, method: str, path: str, params: dict | None = None, signed: bool = False) -> dict | list:
        mutation = method in ("POST", "DELETE", "PUT")
        request_params = {key: self._render(value) for key, value in (params or {}).items() if value is not None}
        headers = {}
        if signed:
            if not self.api_key or not self.api_secret:
                raise BinanceError("Binance credentials are required")
            request_params["recvWindow"] = "5000"
            request_params["timestamp"] = str(int(time.time() * 1000))
            query = urlencode(request_params)
            request_params["signature"] = hmac.new(self.api_secret.encode(), query.encode(), hashlib.sha256).hexdigest()
            headers["X-MBX-APIKEY"] = self.api_key
        try:
            response = self.http.request(method, self.base_url + path, params=request_params, headers=headers)
        except httpx.RequestError as exc:
            error = UnknownOrderOutcome if mutation else BinanceError
            raise error(f"Binance {method} transport failure") from exc
        if response.status_code >= 400:
            try:
                payload = response.json()
                code = payload.get("code", "unknown") if isinstance(payload, dict) else "unknown"
            except ValueError:
                code = "unknown"
            if mutation and (response.status_code >= 500 or response.status_code == 408 or code in (-1000, -1006, -1007)):
                raise UnknownOrderOutcome(f"Binance {method} {path}: HTTP {response.status_code}, code {code}")
            raise BinanceError(f"Binance {method} {path}: HTTP {response.status_code}, code {code}")
        try:
            return response.json()
        except ValueError as exc:
            error = UnknownOrderOutcome if mutation else BinanceError
            raise error(f"Binance {method} {path}: invalid JSON") from exc

    def server_time(self) -> int:
        return int(self._request("GET", "/fapi/v1/time")["serverTime"])

    def get_candles(self, symbol: str, interval: str, limit: int = 302) -> list[Candle]:
        payload = self._request("GET", "/fapi/v1/klines", {"symbol": symbol, "interval": interval, "limit": limit})
        return [Candle(int(row[0]), int(row[6]), *(Decimal(str(row[index])) for index in (1, 2, 3, 4, 5))) for row in payload]

    def get_book(self, symbol: str) -> tuple[Decimal, Decimal, int]:
        payload = self._request("GET", "/fapi/v1/ticker/bookTicker", {"symbol": symbol})
        received_ms = int(time.time() * 1000)
        return Decimal(payload["bidPrice"]), Decimal(payload["askPrice"]), received_ms

    def get_mark(self, symbol: str) -> dict:
        return self._request("GET", "/fapi/v1/premiumIndex", {"symbol": symbol})

    def get_account(self) -> dict:
        return self._request("GET", "/fapi/v3/account", signed=True)

    def get_account_config(self) -> dict:
        return self._request("GET", "/fapi/v1/accountConfig", signed=True)

    def get_income_history(self, start_ms: int, end_ms: int, page: int, limit: int, income_type: str | None = None) -> list[dict]:
        return self._request("GET", "/fapi/v1/income", {
            "incomeType": income_type, "startTime": start_ms, "endTime": end_ms,
            "page": page, "limit": limit,
        }, signed=True)

    def get_positions(self) -> list[dict]:
        return self._request("GET", "/fapi/v3/positionRisk", signed=True)

    def get_position_mode(self) -> dict:
        return self._request("GET", "/fapi/v1/positionSide/dual", signed=True)

    def get_multi_asset_mode(self) -> dict:
        return self._request("GET", "/fapi/v1/multiAssetsMargin", signed=True)

    def get_symbol_config(self, symbol: str) -> dict:
        payload = self._request("GET", "/fapi/v1/symbolConfig", {"symbol": symbol}, signed=True)
        return payload[0] if isinstance(payload, list) else payload

    def get_commission(self, symbol: str) -> dict:
        return self._request("GET", "/fapi/v1/commissionRate", {"symbol": symbol}, signed=True)

    def get_rules(self, symbol: str) -> SymbolRules:
        payload = self._request("GET", "/fapi/v1/exchangeInfo")
        selected = next((item for item in payload["symbols"] if item["symbol"] == symbol), None)
        if selected is None or selected["status"] != "TRADING" or selected["contractType"] != "PERPETUAL" or selected["quoteAsset"] != "USDT" or selected["marginAsset"] != "USDT":
            raise BinanceError(f"{symbol}: unavailable USDT perpetual")
        filters = {entry["filterType"]: entry for entry in selected["filters"]}
        lot = filters["LOT_SIZE"]
        market = filters.get("MARKET_LOT_SIZE", lot)
        notional = filters.get("MIN_NOTIONAL", {})
        return SymbolRules(
            symbol=symbol,
            tick_size=Decimal(filters["PRICE_FILTER"]["tickSize"]),
            step_size=Decimal(lot["stepSize"]),
            min_qty=Decimal(lot["minQty"]),
            min_notional=Decimal(notional.get("notional", "0")),
            max_qty=Decimal(lot["maxQty"]),
            market_step_size=Decimal(market["stepSize"]),
        )

    def open_orders(self, symbol: str) -> list[dict]:
        return self._request("GET", "/fapi/v1/openOrders", {"symbol": symbol}, signed=True)

    def open_algo_orders(self, symbol: str) -> list[dict]:
        return self._request("GET", "/fapi/v1/openAlgoOrders", {"symbol": symbol}, signed=True)

    def query_order(self, symbol: str, client_id: str) -> dict:
        return self._request("GET", "/fapi/v1/order", {"symbol": symbol, "origClientOrderId": client_id}, signed=True)

    def query_algo(self, client_id: str) -> dict:
        return self._request("GET", "/fapi/v1/algoOrder", {"clientAlgoId": client_id}, signed=True)

    def place_ioc(self, symbol: str, side: str, quantity: Decimal, price: Decimal, client_id: str) -> dict:
        return self._request("POST", "/fapi/v1/order", {
            "symbol": symbol, "side": side, "type": "LIMIT", "timeInForce": "IOC", "quantity": quantity,
            "price": price, "newClientOrderId": client_id, "newOrderRespType": "RESULT",
        }, signed=True)

    def place_close_algo(self, symbol: str, side: str, order_type: str, trigger_price: Decimal, client_id: str) -> dict:
        return self._request("POST", "/fapi/v1/algoOrder", {
            "algoType": "CONDITIONAL", "symbol": symbol, "side": side, "type": order_type,
            "triggerPrice": trigger_price, "closePosition": True, "workingType": "MARK_PRICE",
            "priceProtect": False, "clientAlgoId": client_id, "newOrderRespType": "RESULT",
        }, signed=True)

    def place_reduce_market(self, symbol: str, side: str, quantity: Decimal, client_id: str) -> dict:
        return self._request("POST", "/fapi/v1/order", {
            "symbol": symbol, "side": side, "type": "MARKET", "quantity": quantity,
            "reduceOnly": True, "newClientOrderId": client_id, "newOrderRespType": "RESULT",
        }, signed=True)

    def place_reduce_ioc(self, symbol: str, side: str, quantity: Decimal, price: Decimal, client_id: str) -> dict:
        return self._request("POST", "/fapi/v1/order", {
            "symbol": symbol, "side": side, "type": "LIMIT", "timeInForce": "IOC",
            "quantity": quantity, "price": price, "reduceOnly": True,
            "newClientOrderId": client_id, "newOrderRespType": "RESULT",
        }, signed=True)

    def cancel_order(self, symbol: str, client_id: str) -> dict:
        return self._request("DELETE", "/fapi/v1/order", {"symbol": symbol, "origClientOrderId": client_id}, signed=True)

    def cancel_algo(self, client_id: str) -> dict:
        return self._request("DELETE", "/fapi/v1/algoOrder", {"clientAlgoId": client_id}, signed=True)
