from __future__ import annotations

import math
import time
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Decision:
    action: str
    probabilities: dict[str, float] = field(default_factory=dict)
    confidence: float | None = None
    model: str | None = None
    request_id: str | None = None
    duration_ms: int = 0
    error: str | None = None


def gate_decision(decision: Decision, held: bool) -> str:
    safe = "KEEP" if held else "WAIT"
    expected = {"KEEP", "CLOSE"} if held else {"WAIT", "OPEN_LONG", "OPEN_SHORT"}
    probabilities = decision.probabilities
    if set(probabilities) != expected or decision.action not in expected:
        return safe
    if not all(math.isfinite(value) and 0 <= value <= 1 for value in probabilities.values()):
        return safe
    if abs(sum(probabilities.values()) - 1) > 0.02:
        return safe
    selected = probabilities[decision.action]
    if selected < max(probabilities.values()):
        return safe
    if held:
        return "CLOSE" if decision.action == "CLOSE" and selected >= 0.60 else "KEEP"
    if decision.action == "WAIT":
        return "WAIT"
    runner_up = max(value for action, value in probabilities.items() if action != decision.action)
    return decision.action if selected >= 0.65 and selected - runner_up >= 0.20 else "WAIT"


class JevDecider:
    def __init__(self, client: Any = None, model: str = "jev-1.13.0") -> None:
        self.client = client
        self.model = model

    def _client(self) -> Any:
        if self.client is None:
            from typesafe_sdk import RetryPolicy, TypeSafeClient

            self.client = TypeSafeClient(model=self.model, retry=RetryPolicy(max_retries=1, timeout=10.0))
        return self.client

    def decide(self, state: dict, held: bool) -> Decision:
        started = time.monotonic()
        safe = "KEEP" if held else "WAIT"
        criteria = (
            {"KEEP": "Continue holding only if the current position remains justified.",
             "CLOSE": "Close the current position because its trading case has weakened."}
            if held else
            {"OPEN_LONG": "Open a long for a holding period of tens of minutes to hours.",
             "OPEN_SHORT": "Open a short for a holding period of tens of minutes to hours.",
             "WAIT": "Neither direction has a sufficiently clear opportunity."}
        )
        question = {"action": {"type": "choice", "instructions": "Choose the single action supported by the closed-candle state, current position and trading costs. Choose WAIT/KEEP when evidence is ambiguous. Do not perform arithmetic.", "criteria": criteria}}
        try:
            result = self._client().system_one(state=state, questions=question, model=self.model)
            answer = result.choices["action"]
            decision = Decision(
                action=str(answer.choice),
                probabilities={str(key): float(value) for key, value in answer.probabilities.items()},
                confidence=float(answer.confidence),
                model=getattr(result, "model", self.model),
                request_id=getattr(result, "request_id", None),
                duration_ms=int((time.monotonic() - started) * 1000),
            )
            if gate_decision(decision, held) == safe and decision.action != safe:
                return Decision(safe, decision.probabilities, decision.confidence, decision.model, decision.request_id, decision.duration_ms, "rejected_distribution")
            return decision
        except Exception as exc:
            return Decision(safe, model=self.model, duration_ms=int((time.monotonic() - started) * 1000), error=type(exc).__name__)
