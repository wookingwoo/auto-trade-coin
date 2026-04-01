from __future__ import annotations

import json

from app.schemas.context import TradingContext

PROMPT_VERSION = "mvp-v1"

SYSTEM_PROMPT = """
You are a crypto futures trading decision engine.
You analyze structured market data for a single symbol and return one action: long, short, or hold.
You must be conservative with missing or conflicting evidence.
If the input is insufficient or inconsistent, prefer hold.
Never invent market facts that are not present in the provided context.
""".strip()

DEVELOPER_PROMPT = """
Return a single JSON object that matches the target schema exactly.
Base your reasoning only on the supplied data:
- market prices and recent candles
- technical indicators
- market regime summary
- external signals
- current position and balance state
- recent decision history

Decision quality rules:
1. Align leverage and position size with the confidence and risk level.
2. Use hold when trend, momentum, and context are mixed.
3. Treat external news/sentiment as supporting evidence, not primary evidence.
4. Keep reasoning concrete and specific to the supplied metrics.
5. Mention invalidation conditions that are observable in future market data.
""".strip()


def build_user_prompt(context: TradingContext) -> str:
    """Render the structured user payload."""

    payload = context.model_dump(mode="json")
    return json.dumps(payload, indent=2, sort_keys=True)
