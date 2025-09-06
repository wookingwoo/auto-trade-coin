from __future__ import annotations

import hashlib
import hmac
import time
from typing import Any, Dict, List, Optional

import requests


BINANCE_API = "https://api.binance.com"
BINANCE_FAPI = "https://fapi.binance.com"


class SimpleBinance:
    def __init__(
        self,
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        futures: bool = False,
        session: Optional[requests.Session] = None,
    ) -> None:
        self.api_key = api_key
        self.api_secret = api_secret
        self.base = BINANCE_FAPI if futures else BINANCE_API
        self.session = session or requests.Session()
        if api_key:
            self.session.headers.update({"X-MBX-APIKEY": api_key})

    # Public endpoints
    def klines(self, symbol: str, interval: str, limit: int = 500) -> List[List[Any]]:
        url = f"{self.base}/fapi/v1/klines" if self.base == BINANCE_FAPI else f"{self.base}/api/v3/klines"
        params = {"symbol": symbol.upper(), "interval": interval, "limit": limit}
        r = self.session.get(url, params=params, timeout=10)
        r.raise_for_status()
        return r.json()

    def ticker_price(self, symbol: str) -> float:
        url = f"{self.base}/fapi/v1/ticker/price" if self.base == BINANCE_FAPI else f"{self.base}/api/v3/ticker/price"
        r = self.session.get(url, params={"symbol": symbol.upper()}, timeout=10)
        r.raise_for_status()
        return float(r.json()["price"])

    # Private endpoints - minimal sign helper
    def _sign(self, params: Dict[str, Any]) -> Dict[str, Any]:
        if not self.api_secret:
            raise RuntimeError("Private endpoint requires API secret")
        query = "&".join([f"{k}={params[k]}" for k in sorted(params)])
        sig = hmac.new(self.api_secret.encode(), query.encode(), hashlib.sha256).hexdigest()
        params["signature"] = sig
        return params

    def _ts(self):
        return int(time.time() * 1000)

    def account_info(self) -> Dict[str, Any]:
        path = "/fapi/v2/account" if self.base == BINANCE_FAPI else "/api/v3/account"
        url = f"{self.base}{path}"
        params = {"timestamp": self._ts()}
        r = self.session.get(url, params=self._sign(params), timeout=10)
        r.raise_for_status()
        return r.json()

    def order_market(self, symbol: str, side: str, quantity: float) -> Dict[str, Any]:
        side = side.upper()
        if self.base == BINANCE_FAPI:
            url = f"{self.base}/fapi/v1/order"
            params = {
                "symbol": symbol.upper(),
                "side": side,  # BUY or SELL
                "type": "MARKET",
                "quantity": quantity,
                "timestamp": self._ts(),
            }
        else:
            url = f"{self.base}/api/v3/order"
            params = {
                "symbol": symbol.upper(),
                "side": side,  # BUY or SELL
                "type": "MARKET",
                "quoteOrderQty": None,
                "quantity": quantity,
                "timestamp": self._ts(),
                "newOrderRespType": "RESULT",
            }
        r = self.session.post(url, data=self._sign({k: v for k, v in params.items() if v is not None}), timeout=10)
        r.raise_for_status()
        return r.json()

