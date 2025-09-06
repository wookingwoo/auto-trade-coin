from __future__ import annotations

import json
from typing import Dict, Optional

import pandas as pd

from .features import add_indicators, fallback_rule_based
from .config import get_settings


LLM_PROMPT = (
    "You are a crypto trading assistant. Given recent OHLCV and indicators, "
    "decide among LONG, SHORT, BUY, SELL, or HOLD for symbol {symbol} on {interval}. "
    "Provide JSON with fields: action(one of LONG|SHORT|BUY|SELL|HOLD), confidence(0..1), reason, size_usdt (number). "
    "Rules: prefer HOLD unless confidence>0.55; be conservative; size_usdt <= risk budget provided."
)


def _format_rows(df: pd.DataFrame, n: int = 60) -> str:
    cols = ["open_time", "open", "high", "low", "close", "volume", "ema9", "ema21", "rsi", "atr"]
    return df.tail(n)[cols].to_csv(index=False)


def llm_decide(df: pd.DataFrame, risk_budget_usdt: float, llm_provider: str = "openai") -> Dict:
    settings = get_settings()
    df = add_indicators(df)

    # Fallback if no API for LLM
    if not settings.openai_api_key:
        action, reason = fallback_rule_based(df)
        return {
            "action": action,
            "confidence": 0.6 if action != "HOLD" else 0.5,
            "reason": f"Fallback rule-based: {reason}",
            "size_usdt": risk_budget_usdt if action != "HOLD" else 0.0,
        }

    try:
        # Lazy import to avoid hard dep errors when no key
        from langchain_openai import ChatOpenAI
        from langchain_core.prompts import ChatPromptTemplate
        from langchain_core.output_parsers import JsonOutputParser

        prompt = ChatPromptTemplate.from_messages([
            ("system", LLM_PROMPT.format(symbol=settings.symbol, interval=settings.interval)),
            (
                "user",
                "Risk budget (USDT): {risk_budget}. Recent rows CSV (tail):\n{rows}\nReturn JSON only.",
            ),
        ])
        model = ChatOpenAI(model="gpt-4o-mini", temperature=0.2)
        chain = prompt | model | JsonOutputParser()
        out = chain.invoke({"risk_budget": risk_budget_usdt, "rows": _format_rows(df)})
        # Ensure required fields
        return {
            "action": str(out.get("action", "HOLD")).upper(),
            "confidence": float(out.get("confidence", 0.5)),
            "reason": str(out.get("reason", "")),
            "size_usdt": float(out.get("size_usdt", 0.0)),
        }
    except Exception as e:
        # Fail safe
        action, reason = fallback_rule_based(df)
        return {
            "action": action,
            "confidence": 0.55 if action != "HOLD" else 0.5,
            "reason": f"LLM error fallback: {e}",
            "size_usdt": risk_budget_usdt if action != "HOLD" else 0.0,
        }

