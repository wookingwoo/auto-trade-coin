from __future__ import annotations

from datetime import UTC, datetime

from app.models.enums import MarketRegime
from app.models.market import MarketSnapshot, NewsSignal, PositionState, TechnicalIndicators
from app.schemas.context import PerformanceSummary, PreviousDecisionSummary, TradingContext, TrendSummary


class TradingContextBuilder:
    """Build the structured payload passed to the LLM."""

    def build(
        self,
        snapshot: MarketSnapshot,
        indicators: TechnicalIndicators,
        news_signals: list[NewsSignal],
        position_state: PositionState,
        recent_decisions: list[dict],
        performance_summary: dict,
    ) -> TradingContext:
        trend_summary = TrendSummary(
            short_term_trend=self._describe_trend(snapshot.current_price, indicators.h1.ema_fast, indicators.h1.ema_slow),
            medium_term_trend=self._describe_trend(snapshot.current_price, indicators.h4.ema_fast, indicators.h4.ema_slow),
            long_term_trend=self._describe_trend(snapshot.current_price, indicators.d1.ema_fast, indicators.d1.ema_slow),
            volatility_state=self._describe_volatility(snapshot.current_price, indicators.h1.atr),
            market_regime=self._describe_regime(indicators),
            change_since_last_decision=self._describe_change(snapshot, recent_decisions),
        )

        previous = []
        for item in recent_decisions[:5]:
            previous.append(
                PreviousDecisionSummary(
                    timestamp=item["created_at"],
                    decision=item["decision"],
                    confidence=float(item["confidence"]),
                    reasoning=item["reasoning"],
                    outcome=item.get("outcome"),
                ).model_dump(mode="json")
            )

        headlines = [
            {
                "source": signal.source,
                "title": signal.title,
                "summary": signal.summary,
                "sentiment_label": signal.sentiment_label,
                "sentiment_score": signal.sentiment_score,
            }
            for signal in news_signals[:10]
        ]

        return TradingContext(
            run_id=snapshot.run_id,
            generated_at=datetime.now(tz=UTC),
            symbol=snapshot.symbol,
            mode=position_state.mode,
            market={
                "current_price": snapshot.current_price,
                "mark_price": snapshot.mark_price,
                "funding_rate": snapshot.funding_rate,
                "open_interest": snapshot.open_interest,
                "candles_1h": self._serialize_candles(snapshot.candles_1h[-12:]),
                "candles_4h": self._serialize_candles(snapshot.candles_4h[-12:]),
                "candles_1d": self._serialize_candles(snapshot.candles_1d[-7:]),
            },
            indicators={
                "h1": indicators.h1.model_dump(mode="json"),
                "h4": indicators.h4.model_dump(mode="json"),
                "d1": indicators.d1.model_dump(mode="json"),
            },
            market_context=trend_summary,
            external_signals={
                "headlines": headlines,
            },
            account_state={
                "available_balance": position_state.available_balance,
                "wallet_balance": position_state.wallet_balance,
                "current_position": {
                    "side": position_state.side.value,
                    "quantity": position_state.quantity,
                    "entry_price": position_state.entry_price,
                    "unrealized_pnl": position_state.unrealized_pnl,
                    "position_notional": position_state.position_notional,
                    "leverage": position_state.leverage,
                },
                "recent_orders": [item.model_dump(mode="json") for item in position_state.recent_orders],
                "consecutive_losses": position_state.consecutive_losses,
            },
            history={
                "recent_decisions": previous,
                "performance_summary": PerformanceSummary(**performance_summary).model_dump(mode="json"),
            },
        )

    @staticmethod
    def _serialize_candles(candles: list) -> list[dict]:
        return [
            {
                "open_time": candle.open_time.isoformat(),
                "open": candle.open,
                "high": candle.high,
                "low": candle.low,
                "close": candle.close,
                "volume": candle.volume,
            }
            for candle in candles
        ]

    @staticmethod
    def _describe_trend(price: float, ema_fast: float | None, ema_slow: float | None) -> str:
        if ema_fast is None or ema_slow is None:
            return "unknown"
        if price > ema_fast > ema_slow:
            return "bullish"
        if price < ema_fast < ema_slow:
            return "bearish"
        return "mixed"

    @staticmethod
    def _describe_volatility(price: float, atr: float | None) -> str:
        if atr is None or price <= 0:
            return "unknown"
        atr_pct = atr / price
        if atr_pct >= 0.03:
            return "high"
        if atr_pct >= 0.015:
            return "medium"
        return "low"

    def _describe_regime(self, indicators: TechnicalIndicators) -> str:
        if (
            indicators.h1.atr is not None
            and indicators.h1.rsi is not None
            and indicators.h1.bollinger_mid is not None
        ):
            if indicators.h1.atr > indicators.h1.bollinger_mid * 0.03:
                return MarketRegime.VOLATILE.value
            if 45 <= indicators.h1.rsi <= 55:
                return MarketRegime.RANGING.value
            return MarketRegime.TRENDING.value
        return MarketRegime.UNKNOWN.value

    @staticmethod
    def _describe_change(snapshot: MarketSnapshot, recent_decisions: list[dict]) -> str:
        if not recent_decisions:
            return "no previous decision"
        last_decision = recent_decisions[0]
        last_price = last_decision.get("market_price")
        if not last_price:
            return "previous decision exists but market delta is unavailable"
        delta_pct = ((snapshot.current_price - float(last_price)) / float(last_price)) * 100
        return f"price changed {delta_pct:.2f}% since the last decision"
