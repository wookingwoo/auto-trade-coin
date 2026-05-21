from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field

from app.clients.binance import BinanceFuturesClient
from app.config import Settings
from app.exceptions import OrderExecutionError, PreflightCheckError
from app.models.enums import TradingMode
from app.services.preflight import validate_runtime_settings
from app.utils.decimal import round_to_step


class LiveSmokeOrderRequest(BaseModel):
    symbol: str
    side: Literal["BUY", "SELL"]
    max_notional: float = Field(gt=0)
    stop_loss_pct: float = Field(gt=0, le=1)
    take_profit_pct: float = Field(gt=0, le=1)
    cancel_existing_orders: bool = False


class LiveSmokeOrderResult(BaseModel):
    status: str
    symbol: str
    side: str
    quantity: float
    entry_price: float
    notional: float
    stop_loss_price: float
    take_profit_price: float
    client_order_id: str
    protective_client_order_ids: list[str]
    responses: list[dict]
    executed_at: datetime


class LiveSmokeOrderService:
    """Run one explicit live order smoke test outside the LLM trading loop."""

    def __init__(self, settings: Settings, binance_client: BinanceFuturesClient) -> None:
        self.settings = settings
        self.binance_client = binance_client

    def execute(self, request: LiveSmokeOrderRequest) -> LiveSmokeOrderResult:
        self._validate_settings()
        symbol = request.symbol.upper()
        account = self.binance_client.get_account_information()
        position = self._get_position(symbol)
        rules = self.binance_client.get_exchange_info(symbol)
        mark_price = float(self.binance_client.get_mark_price(symbol)["mark_price"])

        self._assert_flat_position(symbol, position)
        if not request.cancel_existing_orders:
            self._assert_no_open_orders(symbol)
        else:
            self.binance_client.cancel_all_open_orders(symbol)
            self.binance_client.cancel_all_algo_open_orders(symbol)

        available_balance = float(account["availableBalance"])
        if available_balance <= 0:
            raise OrderExecutionError("Available live futures balance is zero.")

        quantity = round_to_step(request.max_notional / mark_price, rules.step_size)
        notional = quantity * mark_price
        if quantity <= 0 or quantity < rules.min_qty or notional < rules.min_notional:
            raise OrderExecutionError(
                "Requested live smoke order is below Binance minimum filters "
                f"(quantity={quantity}, notional={notional:.4f}, "
                f"min_qty={rules.min_qty}, min_notional={rules.min_notional})."
            )
        if notional > request.max_notional:
            raise OrderExecutionError(
                f"Calculated order notional {notional:.4f} exceeds max_notional {request.max_notional:.4f}."
            )
        if notional > available_balance * self.settings.max_leverage:
            raise OrderExecutionError(
                f"Calculated order notional {notional:.4f} exceeds available leveraged capacity."
            )

        leverage = min(self.settings.max_leverage, 3)
        smoke_id = uuid4().hex[:8]
        entry_client_order_id = f"smoke-open-{smoke_id}"
        protective_ids: list[str] = []
        responses: list[dict] = []
        entry_opened = False

        try:
            self.binance_client.change_leverage(symbol, leverage)
            entry_response = self.binance_client.create_market_order(
                symbol=symbol,
                side=request.side,
                quantity=quantity,
                client_order_id=entry_client_order_id,
            )
            responses.append(entry_response)
            entry_opened = True
            entry_price = float(entry_response.get("avgPrice", 0) or 0) or mark_price
            close_side = "SELL" if request.side == "BUY" else "BUY"
            stop_price = self._compute_stop_price(entry_price, request.side, request.stop_loss_pct, rules.tick_size)
            take_profit_price = self._compute_take_profit_price(
                entry_price,
                request.side,
                request.take_profit_pct,
                rules.tick_size,
            )

            stop_client_order_id = f"smoke-sl-{smoke_id}"
            responses.append(
                self.binance_client.create_trigger_close_order(
                    symbol=symbol,
                    side=close_side,
                    order_type="STOP_MARKET",
                    stop_price=stop_price,
                    client_order_id=stop_client_order_id,
                    working_type=self.settings.protective_order_working_type,
                )
            )
            protective_ids.append(stop_client_order_id)

            take_profit_client_order_id = f"smoke-tp-{smoke_id}"
            responses.append(
                self.binance_client.create_trigger_close_order(
                    symbol=symbol,
                    side=close_side,
                    order_type="TAKE_PROFIT_MARKET",
                    stop_price=take_profit_price,
                    client_order_id=take_profit_client_order_id,
                    working_type=self.settings.protective_order_working_type,
                )
            )
            protective_ids.append(take_profit_client_order_id)
        except Exception as exc:  # noqa: BLE001
            rollback_errors = self._rollback_smoke_order(
                symbol=symbol,
                entry_side=request.side,
                quantity=quantity,
                entry_opened=entry_opened,
                protective_client_order_ids=protective_ids,
            )
            if rollback_errors:
                raise OrderExecutionError(
                    f"Live smoke order failed: {exc}. Rollback errors: {'; '.join(rollback_errors)}"
                ) from exc
            raise OrderExecutionError(f"Live smoke order failed: {exc}") from exc

        return LiveSmokeOrderResult(
            status="filled",
            symbol=symbol,
            side=request.side,
            quantity=quantity,
            entry_price=entry_price,
            notional=quantity * entry_price,
            stop_loss_price=stop_price,
            take_profit_price=take_profit_price,
            client_order_id=entry_client_order_id,
            protective_client_order_ids=protective_ids,
            responses=responses,
            executed_at=datetime.now(tz=UTC),
        )

    def _validate_settings(self) -> None:
        try:
            validate_runtime_settings(self.settings)
        except PreflightCheckError as exc:
            raise OrderExecutionError(str(exc)) from exc
        if self.settings.trading_mode != TradingMode.LIVE:
            raise OrderExecutionError("Live smoke order requires TRADING_MODE=live.")

    def _get_position(self, symbol: str) -> dict:
        positions = self.binance_client.get_position_risk(symbol)
        return next((item for item in positions if item.get("symbol") == symbol), {})

    def _assert_flat_position(self, symbol: str, position: dict) -> None:
        position_amt = float(position.get("positionAmt", 0) or 0)
        if position_amt != 0:
            raise OrderExecutionError(
                f"Existing {symbol} position is not flat; live smoke order will not modify it."
            )

    def _assert_no_open_orders(self, symbol: str) -> None:
        open_orders = self.binance_client.get_open_orders(symbol)
        open_algo_orders = self.binance_client.get_open_algo_orders(symbol)
        if open_orders or open_algo_orders:
            raise OrderExecutionError(
                f"Found existing {symbol} open orders; cancel_existing_orders=false will not touch them."
            )

    def _rollback_smoke_order(
        self,
        symbol: str,
        entry_side: str,
        quantity: float,
        entry_opened: bool,
        protective_client_order_ids: list[str],
    ) -> list[str]:
        errors: list[str] = []
        for client_algo_id in protective_client_order_ids:
            try:
                self.binance_client.cancel_algo_order(client_algo_id)
            except Exception as exc:  # noqa: BLE001
                errors.append(f"cancel_algo_order({client_algo_id}) failed: {exc}")

        if entry_opened:
            try:
                self.binance_client.create_market_order(
                    symbol=symbol,
                    side="SELL" if entry_side == "BUY" else "BUY",
                    quantity=quantity,
                    client_order_id=f"smoke-rollback-{uuid4().hex[:8]}",
                    reduce_only=True,
                )
            except Exception as exc:  # noqa: BLE001
                errors.append(f"reduce-only rollback failed: {exc}")
        return errors

    @staticmethod
    def _compute_stop_price(entry_price: float, side: str, stop_loss_pct: float, tick_size: float) -> float:
        if side == "BUY":
            return round_to_step(entry_price * (1 - stop_loss_pct), tick_size)
        return round_to_step(entry_price * (1 + stop_loss_pct), tick_size)

    @staticmethod
    def _compute_take_profit_price(entry_price: float, side: str, take_profit_pct: float, tick_size: float) -> float:
        if side == "BUY":
            return round_to_step(entry_price * (1 + take_profit_pct), tick_size)
        return round_to_step(entry_price * (1 - take_profit_pct), tick_size)
