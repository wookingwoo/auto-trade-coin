from app.clients.binance import BinanceFuturesClient
from app.config import Settings


def test_binance_client_formats_small_floats_without_scientific_notation() -> None:
    normalized = BinanceFuturesClient._normalize_params(
        {
            "stopPrice": 2.72e-05,
            "quantity": 181819.0,
            "symbol": "DOGSUSDT",
        }
    )

    assert normalized["stopPrice"] == "0.0000272"
    assert normalized["quantity"] == "181819"
    assert normalized["symbol"] == "DOGSUSDT"


class RecordingBinanceClient(BinanceFuturesClient):
    def __init__(self) -> None:
        super().__init__(
            Settings(
                mongodb_uri="mongodb://localhost:27017",
                openai_api_key="test-key",
                binance_api_key="binance-key",
                binance_api_secret="binance-secret",
            )
        )
        self.calls: list[tuple[str, str, dict | None, bool]] = []

    def _request(self, method: str, path: str, params: dict | None = None, signed: bool = False) -> dict | list:
        self.calls.append((method, path, params, signed))
        return []


def test_binance_client_queries_current_open_orders() -> None:
    client = RecordingBinanceClient()

    assert client.get_open_orders("BTCUSDT") == []
    assert client.get_open_algo_orders("BTCUSDT") == []

    assert client.calls == [
        ("GET", "/fapi/v1/openOrders", {"symbol": "BTCUSDT"}, True),
        ("GET", "/fapi/v1/openAlgoOrders", {"symbol": "BTCUSDT"}, True),
    ]


def test_binance_client_cancels_one_algo_order_by_client_algo_id() -> None:
    client = RecordingBinanceClient()

    client.cancel_algo_order("tp-test")

    assert client.calls == [
        ("DELETE", "/fapi/v1/algoOrder", {"clientAlgoId": "tp-test"}, True),
    ]
