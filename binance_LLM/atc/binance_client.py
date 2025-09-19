from __future__ import annotations

import hashlib
import hmac
import time
from typing import Any, Dict, List, Optional

import requests
from urllib.parse import urlencode
from decimal import Decimal, ROUND_DOWN


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

    # Private endpoints - signing helpers (preserve param order)
    def _sign_items(self, items: List[tuple[str, Any]]) -> List[tuple[str, Any]]:
        if not self.api_secret:
            raise RuntimeError("Private endpoint requires API secret")
        query = urlencode(items)
        sig = hmac.new(self.api_secret.encode(), query.encode(), hashlib.sha256).hexdigest()
        return items + [("signature", sig)]

    def _ts(self):
        return int(time.time() * 1000)

    def account_info(self) -> Dict[str, Any]:
        path = "/fapi/v2/account" if self.base == BINANCE_FAPI else "/api/v3/account"
        url = f"{self.base}{path}"
        items: List[tuple[str, Any]] = [("timestamp", self._ts())]
        signed = self._sign_items(items)
        r = self.session.get(url, params=signed, timeout=10)
        r.raise_for_status()
        return r.json()

    # Exchange info: symbol metadata (base/quote, filters)
    def exchange_info(self, symbol: str) -> Dict[str, Any]:
        if self.base == BINANCE_FAPI:
            url = f"{self.base}/fapi/v1/exchangeInfo"
        else:
            url = f"{self.base}/api/v3/exchangeInfo"
        r = self.session.get(url, params={"symbol": symbol.upper()}, timeout=10)
        r.raise_for_status()
        return r.json()

    def symbol_assets(self, symbol: str) -> tuple[str, str]:
        info = self.exchange_info(symbol)
        syms = info.get("symbols") or []
        if not syms:
            raise RuntimeError(f"No symbol metadata for {symbol}")
        s = syms[0]
        return s.get("baseAsset"), s.get("quoteAsset")

    def quote_precision(self, symbol: str) -> Optional[int]:
        info = self.exchange_info(symbol)
        syms = info.get("symbols") or []
        if not syms:
            return None
        s = syms[0]
        # Spot symbols expose quotePrecision
        return int(s.get("quotePrecision")) if s.get("quotePrecision") is not None else None

    @staticmethod
    def round_down(value: float, decimals: int) -> float:
        if decimals is None or decimals < 0:
            return float(value)
        q = Decimal(10) ** -decimals
        return float(Decimal(str(value)).quantize(q, rounding=ROUND_DOWN))

    def min_notional(self, symbol: str) -> Optional[float]:
        info = self.exchange_info(symbol)
        syms = info.get("symbols") or []
        if not syms:
            return None
        filters = syms[0].get("filters", [])
        # Spot typically uses MIN_NOTIONAL; futures may use NOTIONAL
        for f in filters:
            if f.get("filterType") in ("MIN_NOTIONAL", "NOTIONAL"):
                mn = f.get("minNotional") or f.get("notional")
                try:
                    return float(mn)
                except Exception:
                    return None
        return None

    def spot_free_balance(self, asset: str) -> float:
        if self.base != BINANCE_API:
            raise RuntimeError("spot_free_balance called on futures client")
        acct = self.account_info()
        bals = acct.get("balances", [])
        for b in bals:
            if b.get("asset") == asset.upper():
                try:
                    return float(b.get("free", 0))
                except Exception:
                    return 0.0
        return 0.0

    def order_market(
        self,
        symbol: str,
        side: str,
        quantity: Optional[float] = None,
        quote_order_qty: Optional[float] = None,
        recv_window: int = 5000,
    ) -> Dict[str, Any]:
        side = side.upper()
        if self.base == BINANCE_FAPI:
            url = f"{self.base}/fapi/v1/order"
            items: List[tuple[str, Any]] = [
                ("symbol", symbol.upper()),
                ("side", side),
                ("type", "MARKET"),
                ("quantity", quantity),
                ("timestamp", self._ts()),
                ("recvWindow", recv_window),
            ]
        else:
            url = f"{self.base}/api/v3/order"
            items = [
                ("symbol", symbol.upper()),
                ("side", side),
                ("type", "MARKET"),
                # For spot, prefer quoteOrderQty if provided to avoid LOT_SIZE issues
                ("quoteOrderQty", quote_order_qty if quote_order_qty is not None else None),
                ("quantity", None if quote_order_qty is not None else quantity),
                ("timestamp", self._ts()),
                ("newOrderRespType", "RESULT"),
                ("recvWindow", recv_window),
            ]
        print(f"[Binance] POST {url}")
        print(f"[Binance] params (pre-sign): {dict((k, v) for k, v in items if v is not None)}")

        signed_items = self._sign_items([(k, v) for k, v in items if v is not None])
        r = self.session.post(url, data=signed_items, timeout=10)
        print(f"[Binance] response status={r.status_code}")
        # Print a short snippet of the response body for diagnostics
        body = r.text
        print(f"[Binance] response body: {body[:500]}")
        r.raise_for_status()
        return r.json()

