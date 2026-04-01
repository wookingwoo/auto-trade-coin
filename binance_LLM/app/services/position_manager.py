from __future__ import annotations

from datetime import UTC, datetime

from app.clients.binance import BinanceFuturesClient
from app.config import Settings
from app.models.enums import PositionSide, TradingMode
from app.models.market import OrderSummary, PositionState
from app.repositories.trading_repository import TradingRepository


class PositionManager:
    """Load portfolio state for dry-run and live trading modes."""

    def __init__(
        self,
        settings: Settings,
        repository: TradingRepository,
        binance_client: BinanceFuturesClient,
    ) -> None:
        self.settings = settings
        self.repository = repository
        self.binance_client = binance_client

    def get_position_state(self, symbol: str, current_price: float) -> PositionState:
        if self.settings.trading_mode == TradingMode.DRY_RUN:
            return self._get_paper_position_state(symbol, current_price)
        return self._get_live_position_state(symbol)

    def build_performance_summary(self, symbol: str) -> dict:
        orders = self.repository.get_recent_orders(
            symbol=symbol,
            mode=self.settings.trading_mode.value,
            limit=20,
        )
        realized = [float(item.get("realized_pnl", 0.0) or 0.0) for item in orders if item.get("realized_pnl") is not None]
        profitable = len([value for value in realized if value > 0])
        losing = len([value for value in realized if value < 0])
        win_rate = (profitable / len(realized)) if realized else None
        return {
            "recent_win_rate": win_rate,
            "recent_realized_pnl": sum(realized),
            "profitable_trades": profitable,
            "losing_trades": losing,
            "decision_accuracy_hint": "has_history" if realized else "insufficient_history",
        }

    def _get_paper_position_state(self, symbol: str, current_price: float) -> PositionState:
        latest = self.repository.get_latest_position(symbol, TradingMode.DRY_RUN.value)
        recent_orders = self.repository.get_recent_orders(symbol, TradingMode.DRY_RUN.value, limit=5)
        summaries = [
            OrderSummary(
                order_id=str(order.get("exchange_order_id", order.get("client_order_id", "paper"))),
                side=order.get("side", "UNKNOWN"),
                status=order.get("status", "unknown"),
                quantity=float(order.get("quantity", 0.0)),
                average_price=float(order["average_price"]) if order.get("average_price") is not None else None,
                realized_pnl=float(order["realized_pnl"]) if order.get("realized_pnl") is not None else None,
                executed_at=order.get("executed_at", datetime.now(tz=UTC)),
            )
            for order in recent_orders
        ]

        consecutive_losses = 0
        for order in recent_orders:
            pnl = order.get("realized_pnl")
            if pnl is None:
                continue
            if pnl < 0:
                consecutive_losses += 1
                continue
            break

        if latest:
            quantity = float(latest["quantity"])
            entry_price = float(latest["entry_price"]) if latest.get("entry_price") is not None else None
            if quantity > 0:
                side = PositionSide.LONG
            elif quantity < 0:
                side = PositionSide.SHORT
            else:
                side = PositionSide.FLAT
            unrealized = 0.0
            if entry_price is not None and quantity != 0:
                unrealized = (current_price - entry_price) * quantity
            return PositionState(
                mode=TradingMode.DRY_RUN,
                symbol=symbol,
                captured_at=datetime.now(tz=UTC),
                available_balance=float(latest.get("available_balance", self.settings.paper_starting_balance)),
                wallet_balance=float(latest.get("wallet_balance", self.settings.paper_starting_balance)),
                leverage=int(latest.get("leverage", self.settings.default_leverage)),
                side=side,
                quantity=quantity,
                entry_price=entry_price,
                position_notional=abs(quantity) * current_price,
                unrealized_pnl=unrealized,
                recent_orders=summaries,
                consecutive_losses=consecutive_losses,
            )

        return PositionState(
            mode=TradingMode.DRY_RUN,
            symbol=symbol,
            captured_at=datetime.now(tz=UTC),
            available_balance=self.settings.paper_starting_balance,
            wallet_balance=self.settings.paper_starting_balance,
            leverage=self.settings.default_leverage,
            side=PositionSide.FLAT,
            quantity=0.0,
            entry_price=None,
            position_notional=0.0,
            unrealized_pnl=0.0,
            recent_orders=summaries,
            consecutive_losses=consecutive_losses,
        )

    def _get_live_position_state(self, symbol: str) -> PositionState:
        account = self.binance_client.get_account_information()
        positions = self.binance_client.get_position_risk(symbol)
        recent_orders = self.binance_client.get_all_orders(symbol, limit=5)
        target = next((item for item in positions if float(item["positionAmt"]) != 0), None)
        quantity = float(target["positionAmt"]) if target else 0.0

        if quantity > 0:
            side = PositionSide.LONG
        elif quantity < 0:
            side = PositionSide.SHORT
        else:
            side = PositionSide.FLAT

        summaries = [
            OrderSummary(
                order_id=str(item["orderId"]),
                side=item["side"],
                status=item["status"],
                quantity=float(item["origQty"]),
                average_price=float(item["avgPrice"]) if float(item["avgPrice"]) else None,
                executed_at=datetime.fromtimestamp(item["time"] / 1000, tz=UTC),
            )
            for item in recent_orders
        ]

        available_balance = float(account["availableBalance"])
        total_wallet_balance = float(account["totalWalletBalance"])
        leverage = int(target["initialMargin"] and round(abs(float(target["notional"])) / float(target["initialMargin"]))) if target and float(target["initialMargin"]) else self.settings.default_leverage

        return PositionState(
            mode=TradingMode.LIVE,
            symbol=symbol,
            captured_at=datetime.now(tz=UTC),
            available_balance=available_balance,
            wallet_balance=total_wallet_balance,
            leverage=leverage,
            side=side,
            quantity=quantity,
            entry_price=float(target["entryPrice"]) if target and float(target["entryPrice"]) else None,
            position_notional=abs(float(target["notional"])) if target else 0.0,
            unrealized_pnl=float(target["unRealizedProfit"]) if target else 0.0,
            recent_orders=summaries,
            consecutive_losses=0,
        )

