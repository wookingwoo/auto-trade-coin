# MVP Blueprint

## One-Line Description

An hourly LLM-driven Binance futures trading system that turns structured market context into immediate `long`, `short`, or `hold` execution while storing every artifact for replay, evaluation, and future risk-layer expansion.

## Recommended Stack

- Python
- LangChain for prompt orchestration and structured output
- LangSmith for tracing
- Binance USD-M Futures REST API
- MongoDB Atlas for persistence
- APScheduler or cron-friendly one-shot execution
- Docker for deployment
- `.env` for runtime configuration
- `structlog` for structured logging

## Core Flow

```text
Collect market data
  -> Calculate indicators
  -> Collect headlines and sentiment
  -> Build trading context
  -> Request structured LLM decision
  -> Check idempotency slot
  -> Execute immediately
  -> Place protective orders in live mode
  -> Persist snapshots, decisions, orders, positions, logs, and run metadata
```

## Immediate Post-MVP Hardening Added

- scheduler-slot idempotency to avoid duplicate hourly runs
- live protective stop-loss and take-profit close-position orders
- rollback attempt if live entry succeeds but protective order placement fails

## Why LangChain Over LangGraph For MVP

LangChain is enough because the pipeline is a linear chain with a single decision step and no branching workflow state machine yet. LangGraph becomes more attractive after adding:

- review / retry subgraphs
- risk validation nodes
- approval gates
- asynchronous tool branches
- replay / simulation branches

Start with LangChain now, migrate to LangGraph when the workflow becomes multi-step and stateful.

## MongoDB Schemas

### `market_snapshots`

```json
{
  "run_id": "uuid",
  "symbol": "BTCUSDT",
  "collected_at": "2026-04-01T00:00:00Z",
  "current_price": 68000.0,
  "mark_price": 67995.1,
  "funding_rate": 0.0001,
  "open_interest": 123456.7,
  "candles_1h": [],
  "candles_4h": [],
  "candles_1d": [],
  "symbol_rules": {}
}
```

### `technical_indicators`

```json
{
  "run_id": "uuid",
  "symbol": "BTCUSDT",
  "calculated_at": "2026-04-01T00:00:10Z",
  "h1": { "rsi": 58.1, "macd": 120.3, "atr": 510.2 },
  "h4": { "rsi": 61.0, "macd": 220.8, "atr": 950.4 },
  "d1": { "rsi": 63.3, "macd": 430.4, "atr": 1800.2 }
}
```

### `llm_decisions`

```json
{
  "run_id": "uuid",
  "symbol": "BTCUSDT",
  "mode": "dry_run",
  "model_name": "gpt-4.1-mini",
  "prompt_version": "mvp-v1",
  "market_price": 68000.0,
  "decision": "long",
  "confidence": 0.72,
  "reasoning": "Momentum and multi-timeframe trend are aligned.",
  "risk_level": "medium",
  "recommended_leverage": 2,
  "position_size_pct": 0.08,
  "stop_loss_pct": 0.01,
  "take_profit_pct": 0.025,
  "invalidate_if": ["1h trend flips bearish"],
  "signals_used": {}
}
```

### `trade_orders`

```json
{
  "run_id": "uuid",
  "symbol": "BTCUSDT",
  "mode": "dry_run",
  "client_order_id": "paper-123",
  "side": "BUY",
  "quantity": 0.01,
  "status": "simulated",
  "average_price": 68000.0,
  "realized_pnl": null,
  "executed_at": "2026-04-01T00:00:15Z",
  "raw_response": []
}
```

### `positions`

```json
{
  "mode": "dry_run",
  "symbol": "BTCUSDT",
  "captured_at": "2026-04-01T00:00:15Z",
  "available_balance": 10000.0,
  "wallet_balance": 10000.0,
  "leverage": 2,
  "side": "long",
  "quantity": 0.01,
  "entry_price": 68000.0,
  "position_notional": 680.0,
  "unrealized_pnl": 0.0
}
```

### `execution_logs`

```json
{
  "run_id": "uuid",
  "symbol": "BTCUSDT",
  "stage": "llm_decision",
  "payload": {},
  "created_at": "2026-04-01T00:00:12Z"
}
```

### `strategy_runs`

```json
{
  "run_id": "uuid",
  "symbol": "BTCUSDT",
  "mode": "dry_run",
  "status": "completed",
  "started_at": "2026-04-01T00:00:00Z",
  "finished_at": "2026-04-01T00:00:16Z",
  "metadata": {
    "decision": "long",
    "execution_status": "simulated"
  }
}
```

### `news_signals`

```json
{
  "run_id": "uuid",
  "symbol": "BTCUSDT",
  "signal_type": "headline",
  "source": "CoinDesk",
  "title": "Bitcoin headline",
  "summary": "Short summary",
  "url": "https://example.com"
}
```

### `system_configs`

```json
{
  "config_key": "runtime_settings",
  "app_env": "development",
  "trading_mode": "dry_run",
  "trading_symbols": ["BTCUSDT"],
  "llm_model": "gpt-4.1-mini",
  "updated_at": "2026-04-01T00:00:00Z"
}
```

## Prompt Design

Use three layers:

1. `system` prompt for role and safety posture
2. second `system` prompt for output contract and decision rules
3. `human` prompt for the structured trading context JSON

The model must:

- use only provided facts
- prefer `hold` on ambiguity
- return strict JSON only
- express confidence, leverage, size, stop, take-profit, invalidation, and signal usage

## Extension Points

- stop-loss and take-profit placement
- replay and backtest runners
- sentiment and macro data providers
- validation and risk layers
- multi-symbol execution queues
- LangGraph migration when the workflow becomes stateful
