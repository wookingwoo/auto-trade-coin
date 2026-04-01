from app.clients.binance import BinanceFuturesClient


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
