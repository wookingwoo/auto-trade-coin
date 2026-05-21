# Operations Guide

This project can automate Binance USD-M futures orders. Treat live mode as high risk and keep `dry_run` as the default until dependency checks, paper results, and monitoring are in place.

## Preflight

Run dependency checks before starting the scheduler:

```bash
python -m app.main --preflight --symbol BTCUSDT
```

The preflight validates MongoDB connectivity, Binance public data, the LLM provider, and live-only private Binance access when `TRADING_MODE=live`.

## Live Mode Gate

Live mode is intentionally blocked unless all of these are true:

- `TRADING_MODE=live`
- `LIVE_TRADING_ACK=true`
- `BINANCE_API_KEY` and `BINANCE_API_SECRET` are configured
- `ENABLE_PROTECTIVE_ORDERS=true`
- `REQUIRE_PROTECTIVE_ORDER_PARAMS=true`

Keep `MAX_LEVERAGE` low. The default is `3`, and `OrderExecutor` clamps LLM leverage recommendations to this value.

## Live Smoke Order

Use `--live-smoke-order` for an explicit real-order test that bypasses the LLM trading loop. The safe default is `--cancel-existing-orders false`; in that mode the command aborts if the symbol already has a position or open orders.

BTCUSDT currently requires roughly `0.001 BTC` minimum order size. At a BTC mark price near `77,000 USDT`, use `--max-notional 80` or higher and keep enough futures wallet balance for margin and fees.

Example:

```bash
TRADING_MODE=live \
LIVE_TRADING_ACK=true \
ENABLE_PROTECTIVE_ORDERS=true \
REQUIRE_PROTECTIVE_ORDER_PARAMS=true \
python -m app.main \
  --live-smoke-order \
  --symbol BTCUSDT \
  --side BUY \
  --max-notional 80 \
  --stop-loss-pct 0.01 \
  --take-profit-pct 0.02 \
  --cancel-existing-orders false
```

The smoke command submits one market entry and then close-position `STOP_MARKET` and `TAKE_PROFIT_MARKET` orders. If protective order placement fails, it cancels only protective algo orders created by that smoke run and attempts a reduce-only rollback market order.

## Decision Guardrails

The executor skips trade decisions that do not satisfy these runtime rules:

- `confidence >= MIN_DECISION_CONFIDENCE`
- `stop_loss_pct > 0` when `REQUIRE_PROTECTIVE_ORDER_PARAMS=true`
- `take_profit_pct > 0` when `REQUIRE_PROTECTIVE_ORDER_PARAMS=true`
- `stop_loss_pct <= MAX_STOP_LOSS_PCT`
- `take_profit_pct <= MAX_TAKE_PROFIT_PCT`
- `consecutive_losses < MAX_CONSECUTIVE_LOSSES`
- calculated order size meets Binance symbol filters
- current position is not already on the requested side

Skipped decisions are still persisted through the normal execution log path so they can be reviewed.

## Dry-Run Burn-In

Before live trading, run at least one full scheduler interval in `dry_run`:

```bash
TRADING_MODE=dry_run python -m app.scheduler
```

Review these MongoDB collections after the burn-in:

- `strategy_runs` for failures and duplicate-slot skips
- `llm_decisions` for low-confidence or inconsistent recommendations
- `trade_orders` for simulated quantity and notional sanity
- `positions` for paper PnL and side transitions
- `execution_logs` for context and error payloads

## Runtime Monitoring

Monitor structured logs for these event names:

- `strategy_run_completed`
- `strategy_run_failed`
- `strategy_run_skipped_duplicate`

Enable LangSmith tracing only after confirming the project and API key are configured:

```bash
LANGSMITH_TRACING=true
LANGSMITH_PROJECT=auto-trade-coin
```

## Read-Only Dashboard

The dashboard is a separate FastAPI process and does not submit, cancel, or modify orders. It reads MongoDB collections for recent strategy runs, LLM decisions, orders, positions, execution logs, and runtime config.

Required settings:

- `DASHBOARD_ENABLED=true`
- `DASHBOARD_USERNAME=<operator name>`
- `DASHBOARD_PASSWORD=<strong password>`
- `DASHBOARD_HOST=0.0.0.0`
- `DASHBOARD_PORT=8080`

Run locally:

```bash
python -m app.dashboard.main
```

Run with Docker Compose:

```bash
docker compose --profile dashboard up --build dashboard
```

Open `http://localhost:8080/dashboard`. Keep the dashboard behind a private network, VPN, or reverse proxy with TLS; Basic Auth is an access gate, not a full perimeter security layer.

## Failure Behavior

The pipeline stops before order execution if market data collection, indicator calculation, context building, or LLM parsing fails. If live entry succeeds but protective order placement fails, the executor cancels open orders and attempts a reduce-only rollback market order.
