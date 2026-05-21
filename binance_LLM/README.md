# Auto Trade Coin

An LLM-driven Binance USD-M futures trading MVP that collects market data every hour, builds a structured trading context, asks an LLM for a `long` / `short` / `hold` decision, executes the order immediately, and stores every step in MongoDB Atlas for replay and evaluation.

## What It Does

- Pulls market data from Binance Futures for one or more symbols.
- Computes technical indicators such as RSI, MACD, EMA, SMA, Bollinger Bands, ATR, and volume trend.
- Collects external signals through RSS headlines and a Fear & Greed sentiment feed.
- Builds a structured trading context for an LLM.
- Uses LangChain structured output to force a valid JSON decision object.
- Supports `dry_run` and `live` trading modes.
- Prevents duplicate execution within the same scheduler slot by using an idempotency key.
- Places live protective `STOP_MARKET` and `TAKE_PROFIT_MARKET` close-position orders after entry.
- Persists market snapshots, indicators, decisions, orders, positions, logs, and run metadata in MongoDB Atlas.
- Emits traces to LangSmith when tracing is enabled.

## MVP Scope

This repository intentionally keeps the decision pipeline simple:

1. Collect market data
2. Compute indicators
3. Collect external signals
4. Build trading context
5. Call the LLM
6. Execute immediately
7. Persist everything

The MVP does **not** include a separate risk gateway, advanced portfolio controls, or production-grade backtest coverage. Those are planned follow-up layers.

## Architecture

```text
Binance Market Data ─┐
Binance Account Data ├─> Context Builder ─> TradingDecisionAgent (LangChain) ─> OrderExecutor
External Signals ────┘             │                                │
TechnicalIndicatorService ─────────┘                                │
                                                                     ├─> Binance Live Order
                                                                     └─> Paper Trade Simulation

All stages ─────────────────────────────────────────────────────────────> MongoDB Atlas
LangChain / LangSmith tracing ─────────────────────────────────────────> LangSmith
```

## Project Structure

```text
app/
  clients/          # Binance and MongoDB client adapters
  models/           # Domain models and enums
  prompts/          # LLM prompt templates and prompt versioning
  repositories/     # MongoDB persistence logic
  schemas/          # Pydantic schemas for context and LLM output
  services/         # Market, indicator, news, decision, execution orchestration
  utils/            # Numeric helpers
  main.py           # One-shot entry point
  scheduler.py      # APScheduler entry point
docs/
  MVP_BLUEPRINT.md  # Expanded implementation blueprint
tests/
  test_indicators.py
  test_order_executor.py
```

## MongoDB Collections

- `market_snapshots`
- `technical_indicators`
- `llm_decisions`
- `trade_orders`
- `positions`
- `execution_logs`
- `strategy_runs`
- `news_signals`
- `system_configs`

## Environment Variables

Copy `.env.example` to `.env` and configure at least:

- `MONGODB_URI`
- `OPENAI_API_KEY`
- `TRADING_MODE`
- `TRADING_SYMBOLS`
- `BINANCE_API_KEY`
- `BINANCE_API_SECRET`
- `MAX_LEVERAGE`
- `MIN_DECISION_CONFIDENCE`
- `MAX_STOP_LOSS_PCT`
- `MAX_TAKE_PROFIT_PCT`
- `MAX_CONSECUTIVE_LOSSES`
- `LIVE_TRADING_ACK` must be `true` before `TRADING_MODE=live` can start
- `LANGSMITH_API_KEY` when tracing is enabled
- `ENABLE_PROTECTIVE_ORDERS`
- `PROTECTIVE_ORDER_WORKING_TYPE`
- `REQUIRE_PROTECTIVE_ORDER_PARAMS`

## Quick Start

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
python -m app.main --once
```

Run the in-process scheduler:

```bash
python -m app.scheduler
```

## Docker

Build and run:

```bash
docker build -t auto-trade-coin .
docker run --env-file .env auto-trade-coin
```

Or use:

```bash
docker compose up --build
```

## Trading Modes

- `dry_run`: simulates fills and maintains a paper position ledger in MongoDB.
- `live`: reads private Binance account data, submits real market orders, and then places protective close-position trigger orders.

## Testing

```bash
pytest
```

## Operational Notes

- If data collection fails, the run stops before order execution.
- If LLM parsing fails, the run stops before order execution.
- If a trade decision confidence is below `MIN_DECISION_CONFIDENCE`, the order is skipped.
- If a trade decision is missing stop-loss or take-profit percentages while `REQUIRE_PROTECTIVE_ORDER_PARAMS=true`, the order is skipped.
- If a trade decision exceeds `MAX_STOP_LOSS_PCT` or `MAX_TAKE_PROFIT_PCT`, the order is skipped.
- If the paper/live position state has reached `MAX_CONSECUTIVE_LOSSES`, new trade entries are skipped.
- In live mode, startup fails unless `LIVE_TRADING_ACK=true`, Binance credentials are present, and protective orders are enabled.
- If the same symbol is triggered twice in the same scheduler slot, the later run is skipped as a duplicate.
- If Binance order submission fails in live mode, the error is persisted in `execution_logs`.
- If protective order placement fails after a live entry, the executor attempts to flatten the newly opened position.
- Every major stage is recorded with a shared `run_id`.

See [docs/OPERATIONS.md](docs/OPERATIONS.md) before enabling live trading.

## Next Steps

- Add replay and backtest execution paths.
- Add trailing stops, partial exits, and post-fill protective order reconciliation.
- Add advanced risk controls and validation layers.
