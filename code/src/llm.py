from __future__ import annotations

import os

Message = dict[str, str]


def llm_enabled() -> bool:
    """False when LLM_PROVIDER=none, letting nodes fall back to heuristics (e.g. a zero-secret hosted demo)."""
    return os.getenv("LLM_PROVIDER", "ollama").lower() != "none"


class _ChatAdapter:
    """Normalizes LangChain chat models to return plain text like OllamaLLM does."""

    def __init__(self, model):
        self._model = model

    def invoke(self, messages: list[Message]) -> str:
        result = self._model.invoke(messages)
        return getattr(result, "content", str(result))


def get_llm(model: str | None = None, temperature: float = 0.2, json_mode: bool = True):
    """Return an LLM client with a uniform `.invoke(messages) -> str` interface.

    Provider is selected via the LLM_PROVIDER env var (ollama, openai, anthropic),
    so the framework runs locally by default but can target a hosted API with no
    code changes.
    """
    provider = os.getenv("LLM_PROVIDER", "ollama").lower()

    if provider == "openai":
        from langchain_openai import ChatOpenAI

        kwargs: dict = {"model": model or os.getenv("LLM_MODEL", "gpt-4o-mini"), "temperature": temperature}
        if json_mode:
            kwargs["model_kwargs"] = {"response_format": {"type": "json_object"}}
        return _ChatAdapter(ChatOpenAI(**kwargs))

    if provider == "anthropic":
        from langchain_anthropic import ChatAnthropic

        return _ChatAdapter(
            ChatAnthropic(model=model or os.getenv("LLM_MODEL", "claude-3-5-sonnet-latest"), temperature=temperature)
        )

    from langchain_ollama import OllamaLLM

    return OllamaLLM(
        model=model or os.getenv("LLM_MODEL", "qwen2.5:14b"),
        temperature=temperature,
        format="json" if json_mode else "",
    )
