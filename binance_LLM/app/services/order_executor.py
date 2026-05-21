from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from app.clients.binance import BinanceFuturesClient
from app.config import Settings
from app.exceptions import OrderExecutionError
from app.models.enums import DecisionType, OrderStatus, PositionSide, TradingMode
from app.models.execution import OrderExecutionResult, OrderRequest
from app.models.market import MarketSnapshot, PositionState
from app.schemas.decision import LLMDecision
from app.utils.decimal import clamp, round_to_step, round_up_to_step


class OrderExecutor:
    """Execute or simulate the LLM decision immediately after inference."""

    def __init__(self, settings: Settings, binance_client: BinanceFuturesClient) -> None:
        self.settings = settings
        self.binance_client = binance_client

    def execute(
        self,
        run_id: str,
        snapshot: MarketSnapshot,
        position_state: PositionState,
        decision: LLMDecision,
    ) -> OrderExecutionResult:
        target_side = (
            PositionSide.LONG
            if decision.decision == DecisionType.LONG
            else PositionSide.SHORT
            if decision.decision == DecisionType.SHORT
            else position_state.side
        )

        if decision.decision == DecisionType.HOLD:
            return self._skipped_result(
                run_id,
                snapshot,
                position_state,
                decision,
                message="Decision was hold. No order submitted.",
            )

        if decision.confidence < self.settings.min_decision_confidence:
            return self._skipped_result(
                run_id,
                snapshot,
                position_state,
                decision,
                message=(
                    "Decision confidence is below configured minimum "
                    f"({decision.confidence:.2f} < {self.settings.min_decision_confidence:.2f})."
                ),
            )

        if target_side == position_state.side and position_state.quantity != 0:
            return self._skipped_result(
                run_id,
                snapshot,
                position_state,
                decision,
                message="Current position already matches the decision side. Re-entry is skipped in MVP.",
            )

        if position_state.consecutive_losses >= self.settings.max_consecutive_losses:
            return self._skipped_result(
                run_id,
                snapshot,
                position_state,
                decision,
                message=(
                    "Current position state has reached the configured consecutive loss limit "
                    f"({position_state.consecutive_losses} >= {self.settings.max_consecutive_losses})."
                ),
            )

        if self.settings.require_protective_order_params and (
            decision.stop_loss_pct <= 0 or decision.take_profit_pct <= 0
        ):
            return self._skipped_result(
                run_id,
                snapshot,
                position_state,
                decision,
                message="Trade decision is missing required protective risk parameters.",
            )

        if decision.stop_loss_pct > self.settings.max_stop_loss_pct:
            return self._skipped_result(
                run_id,
                snapshot,
                position_state,
                decision,
                message=(
                    "Decision stop-loss percentage exceeds configured maximum "
                    f"({decision.stop_loss_pct:.4f} > {self.settings.max_stop_loss_pct:.4f})."
                ),
            )

        if decision.take_profit_pct > self.settings.max_take_profit_pct:
            return self._skipped_result(
                run_id,
                snapshot,
                position_state,
                decision,
                message=(
                    "Decision take-profit percentage exceeds configured maximum "
                    f"({decision.take_profit_pct:.4f} > {self.settings.max_take_profit_pct:.4f})."
                ),
            )

        leverage = min(max(decision.recommended_leverage, 1), self.settings.max_leverage)
        size_pct = clamp(decision.position_size_pct, 0.0, self.settings.max_position_size_pct)
        current_price = snapshot.current_price
        reference_price = snapshot.mark_price if self.settings.trading_mode == TradingMode.LIVE and snapshot.mark_price else current_price
        target_notional = position_state.available_balance * leverage * size_pct
        raw_quantity = target_notional / reference_price if reference_price > 0 else 0.0
        quantity = round_to_step(raw_quantity, snapshot.symbol_rules.step_size)
        effective_notional = quantity * reference_price

        if effective_notional < snapshot.symbol_rules.min_notional and target_notional >= snapshot.symbol_rules.min_notional:
            quantity = round_up_to_step(
                snapshot.symbol_rules.min_notional / reference_price,
                snapshot.symbol_rules.step_size,
            )
            effective_notional = quantity * reference_price

        if quantity < snapshot.symbol_rules.min_qty or effective_notional < snapshot.symbol_rules.min_notional:
            return self._skipped_result(
                run_id,
                snapshot,
                position_state,
                decision,
                message="Calculated order size is below Binance minimum filters.",
            )

        if self.settings.trading_mode == TradingMode.DRY_RUN:
            return self._simulate(run_id, snapshot, position_state, decision, quantity, leverage)
        return self._execute_live(run_id, snapshot, position_state, decision, quantity, leverage)

    def _skipped_result(
        self,
        run_id: str,
        snapshot: MarketSnapshot,
        position_state: PositionState,
        decision: LLMDecision,
        message: str,
    ) -> OrderExecutionResult:
        return OrderExecutionResult(
            run_id=run_id,
            symbol=snapshot.symbol,
            mode=self.settings.trading_mode,
            decision=decision.decision,
            status=OrderStatus.SKIPPED,
            executed_at=datetime.now(tz=UTC),
            message=message,
            resulting_side=position_state.side,
            resulting_quantity=position_state.quantity,
            resulting_entry_price=position_state.entry_price,
            paper_balance=position_state.available_balance if self.settings.trading_mode == TradingMode.DRY_RUN else None,
        )

    def _simulate(
        self,
        run_id: str,
        snapshot: MarketSnapshot,
        position_state: PositionState,
        decision: LLMDecision,
        quantity: float,
        leverage: int,
    ) -> OrderExecutionResult:
        requests: list[OrderRequest] = []
        realized_pnl = None
        balance = position_state.available_balance

        if position_state.side == PositionSide.LONG and decision.decision == DecisionType.SHORT:
            realized_pnl = (snapshot.current_price - (position_state.entry_price or snapshot.current_price)) * position_state.quantity
            balance += realized_pnl
        elif position_state.side == PositionSide.SHORT and decision.decision == DecisionType.LONG:
            realized_pnl = ((position_state.entry_price or snapshot.current_price) - snapshot.current_price) * abs(position_state.quantity)
            balance += realized_pnl
        elif position_state.side == PositionSide.LONG and decision.decision == DecisionType.LONG:
            return OrderExecutionResult(
                run_id=run_id,
                symbol=snapshot.symbol,
                mode=TradingMode.DRY_RUN,
                decision=decision.decision,
                status=OrderStatus.SKIPPED,
                executed_at=datetime.now(tz=UTC),
                message="Dry-run position already long. Rebalancing is intentionally skipped in MVP.",
                resulting_side=PositionSide.LONG,
                resulting_quantity=position_state.quantity,
                resulting_entry_price=position_state.entry_price,
                paper_balance=balance,
            )
        elif position_state.side == PositionSide.SHORT and decision.decision == DecisionType.SHORT:
            return OrderExecutionResult(
                run_id=run_id,
                symbol=snapshot.symbol,
                mode=TradingMode.DRY_RUN,
                decision=decision.decision,
                status=OrderStatus.SKIPPED,
                executed_at=datetime.now(tz=UTC),
                message="Dry-run position already short. Rebalancing is intentionally skipped in MVP.",
                resulting_side=PositionSide.SHORT,
                resulting_quantity=position_state.quantity,
                resulting_entry_price=position_state.entry_price,
                paper_balance=balance,
            )

        client_order_id = f"paper-{run_id[:8]}-{uuid4().hex[:8]}"
        requests.append(
            OrderRequest(
                symbol=snapshot.symbol,
                side="BUY" if decision.decision == DecisionType.LONG else "SELL",
                quantity=quantity,
                leverage=leverage,
                client_order_id=client_order_id,
                metadata={"mode": "paper"},
            )
        )
        resulting_side = PositionSide.LONG if decision.decision == DecisionType.LONG else PositionSide.SHORT
        signed_quantity = quantity if resulting_side == PositionSide.LONG else -quantity

        return OrderExecutionResult(
            run_id=run_id,
            symbol=snapshot.symbol,
            mode=TradingMode.DRY_RUN,
            decision=decision.decision,
            status=OrderStatus.SIMULATED,
            executed_at=datetime.now(tz=UTC),
            order_requests=requests,
            exchange_responses=[
                {
                    "simulated": True,
                    "fill_price": snapshot.current_price,
                }
            ],
            message="Paper trade simulated successfully.",
            resulting_side=resulting_side,
            resulting_quantity=signed_quantity,
            resulting_entry_price=snapshot.current_price,
            realized_pnl=realized_pnl,
            paper_balance=balance,
        )

    def _execute_live(
        self,
        run_id: str,
        snapshot: MarketSnapshot,
        position_state: PositionState,
        decision: LLMDecision,
        quantity: float,
        leverage: int,
    ) -> OrderExecutionResult:
        requests: list[OrderRequest] = []
        responses: list[dict] = []
        now = datetime.now(tz=UTC)
        target_side = PositionSide.LONG if decision.decision == DecisionType.LONG else PositionSide.SHORT
        opened_quantity = quantity if target_side == PositionSide.LONG else -quantity
        entry_price: float | None = None
        position_opened = False

        try:
            self.binance_client.cancel_all_open_orders(snapshot.symbol)
            self.binance_client.cancel_all_algo_open_orders(snapshot.symbol)
            self.binance_client.change_leverage(snapshot.symbol, leverage)

            if position_state.side == PositionSide.LONG and target_side == PositionSide.SHORT:
                close_qty = round_to_step(abs(position_state.quantity), snapshot.symbol_rules.step_size)
                if close_qty > 0:
                    close_request = OrderRequest(
                        symbol=snapshot.symbol,
                        side="SELL",
                        quantity=close_qty,
                        reduce_only=True,
                        leverage=leverage,
                        client_order_id=f"close-{run_id[:8]}",
                    )
                    requests.append(close_request)
                    responses.append(
                        self.binance_client.create_market_order(
                            symbol=snapshot.symbol,
                            side="SELL",
                            quantity=close_qty,
                            client_order_id=close_request.client_order_id,
                            reduce_only=True,
                        )
                    )
            elif position_state.side == PositionSide.SHORT and target_side == PositionSide.LONG:
                close_qty = round_to_step(abs(position_state.quantity), snapshot.symbol_rules.step_size)
                if close_qty > 0:
                    close_request = OrderRequest(
                        symbol=snapshot.symbol,
                        side="BUY",
                        quantity=close_qty,
                        reduce_only=True,
                        leverage=leverage,
                        client_order_id=f"close-{run_id[:8]}",
                    )
                    requests.append(close_request)
                    responses.append(
                        self.binance_client.create_market_order(
                            symbol=snapshot.symbol,
                            side="BUY",
                            quantity=close_qty,
                            client_order_id=close_request.client_order_id,
                            reduce_only=True,
                        )
                    )

            open_request = OrderRequest(
                symbol=snapshot.symbol,
                side="BUY" if target_side == PositionSide.LONG else "SELL",
                quantity=quantity,
                leverage=leverage,
                client_order_id=f"open-{run_id[:8]}",
            )
            requests.append(open_request)
            open_response = self.binance_client.create_market_order(
                symbol=snapshot.symbol,
                side=open_request.side,
                quantity=quantity,
                client_order_id=open_request.client_order_id,
            )
            responses.append(open_response)
            position_opened = True
            entry_price = float(open_response.get("avgPrice", 0) or 0) or snapshot.current_price
            if self.settings.enable_protective_orders:
                protective_requests = self._build_protective_requests(
                    run_id=run_id,
                    symbol=snapshot.symbol,
                    decision=decision,
                    side=target_side,
                    entry_price=entry_price,
                    leverage=leverage,
                    tick_size=snapshot.symbol_rules.tick_size,
                )
                for request in protective_requests:
                    requests.append(request)
                    responses.append(
                        self.binance_client.create_trigger_close_order(
                            symbol=request.symbol,
                            side=request.side,
                            order_type=request.order_type,
                            stop_price=request.stop_price or 0.0,
                            client_order_id=request.client_order_id,
                            working_type=request.working_type or self.settings.protective_order_working_type,
                        )
                    )
        except Exception as exc:  # noqa: BLE001
            rollback_error = None
            if position_opened:
                try:
                    self.binance_client.cancel_all_open_orders(snapshot.symbol)
                    self.binance_client.cancel_all_algo_open_orders(snapshot.symbol)
                    self.binance_client.create_market_order(
                        symbol=snapshot.symbol,
                        side="SELL" if target_side == PositionSide.LONG else "BUY",
                        quantity=quantity,
                        client_order_id=f"rollback-{run_id[:8]}",
                        reduce_only=True,
                    )
                except Exception as rollback_exc:  # noqa: BLE001
                    rollback_error = rollback_exc

            if rollback_error:
                raise OrderExecutionError(
                    f"Live order execution failed: {exc}. Rollback also failed: {rollback_error}"
                ) from exc
            raise OrderExecutionError(f"Live order execution failed: {exc}") from exc

        return OrderExecutionResult(
            run_id=run_id,
            symbol=snapshot.symbol,
            mode=TradingMode.LIVE,
            decision=decision.decision,
            status=OrderStatus.FILLED,
            executed_at=now,
            order_requests=requests,
            exchange_responses=responses,
            message="Live orders and protective orders submitted successfully." if self.settings.enable_protective_orders else "Live orders submitted successfully.",
            resulting_side=target_side,
            resulting_quantity=opened_quantity,
            resulting_entry_price=entry_price or snapshot.current_price,
        )

    def _build_protective_requests(
        self,
        run_id: str,
        symbol: str,
        decision: LLMDecision,
        side: PositionSide,
        entry_price: float,
        leverage: int,
        tick_size: float,
    ) -> list[OrderRequest]:
        requests: list[OrderRequest] = []

        if decision.stop_loss_pct > 0:
            stop_price = self._compute_stop_price(entry_price, side, decision.stop_loss_pct, tick_size)
            requests.append(
                OrderRequest(
                    symbol=symbol,
                    side="SELL" if side == PositionSide.LONG else "BUY",
                    quantity=0.0,
                    order_type="STOP_MARKET",
                    stop_price=stop_price,
                    close_position=True,
                    working_type=self.settings.protective_order_working_type,
                    leverage=leverage,
                    client_order_id=f"sl-{run_id[:8]}",
                    metadata={"category": "stop_loss"},
                )
            )

        if decision.take_profit_pct > 0:
            take_profit_price = self._compute_take_profit_price(entry_price, side, decision.take_profit_pct, tick_size)
            requests.append(
                OrderRequest(
                    symbol=symbol,
                    side="SELL" if side == PositionSide.LONG else "BUY",
                    quantity=0.0,
                    order_type="TAKE_PROFIT_MARKET",
                    stop_price=take_profit_price,
                    close_position=True,
                    working_type=self.settings.protective_order_working_type,
                    leverage=leverage,
                    client_order_id=f"tp-{run_id[:8]}",
                    metadata={"category": "take_profit"},
                )
            )

        return requests

    @staticmethod
    def _compute_stop_price(entry_price: float, side: PositionSide, stop_loss_pct: float, tick_size: float) -> float:
        if side == PositionSide.LONG:
            return round_to_step(entry_price * (1 - stop_loss_pct), tick_size)
        return round_to_step(entry_price * (1 + stop_loss_pct), tick_size)

    @staticmethod
    def _compute_take_profit_price(entry_price: float, side: PositionSide, take_profit_pct: float, tick_size: float) -> float:
        if side == PositionSide.LONG:
            return round_to_step(entry_price * (1 + take_profit_pct), tick_size)
        return round_to_step(entry_price * (1 - take_profit_pct), tick_size)
