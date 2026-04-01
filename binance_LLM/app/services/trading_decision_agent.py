from __future__ import annotations

from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from langsmith import traceable

from app.config import Settings
from app.exceptions import LLMDecisionError
from app.prompts.trading import DEVELOPER_PROMPT, PROMPT_VERSION, SYSTEM_PROMPT, build_user_prompt
from app.schemas.context import TradingContext
from app.schemas.decision import LLMDecision


class TradingDecisionAgent:
    """LLM-based decision engine using LangChain structured output."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.prompt = ChatPromptTemplate.from_messages(
            [
                ("system", SYSTEM_PROMPT),
                ("system", DEVELOPER_PROMPT),
                ("human", "{context_json}"),
            ]
        )
        self.model = self._build_model()
        self.structured_model = self.model.with_structured_output(LLMDecision)

    def _build_model(self) -> ChatOpenAI:
        if self.settings.llm_provider != "openai":
            raise LLMDecisionError(f"Unsupported LLM provider: {self.settings.llm_provider}")
        if not self.settings.openai_api_key:
            raise LLMDecisionError("OPENAI_API_KEY is required for LLM decisions.")
        return ChatOpenAI(
            model=self.settings.llm_model,
            temperature=self.settings.llm_temperature,
            api_key=self.settings.openai_api_key,
        )

    @traceable(name="trading_decision", run_type="llm")
    def decide(self, context: TradingContext) -> LLMDecision:
        payload = build_user_prompt(context)
        last_error: Exception | None = None

        for attempt in range(1, self.settings.llm_max_retries + 1):
            try:
                messages = self.prompt.format_messages(context_json=payload)
                return self.structured_model.invoke(messages)
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                payload = (
                    f"{build_user_prompt(context)}\n\n"
                    f"Previous parsing error: {type(exc).__name__}. "
                    "Return a valid JSON object matching the schema exactly."
                )
                if attempt == self.settings.llm_max_retries:
                    break

        raise LLMDecisionError(f"Failed to obtain a structured LLM decision: {last_error}") from last_error

    @property
    def prompt_version(self) -> str:
        return PROMPT_VERSION

