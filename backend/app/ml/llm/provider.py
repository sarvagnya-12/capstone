"""Provider-agnostic LLM interface for the persona simulation engine. The SRS
permits either an API or an open-source model (PRD Sec14; PROJECT_CONTEXT.md
explicitly notes this project allows external LLM API usage) -- this Protocol
keeps swapping providers a config change plus one small class, not a rewrite.
"""

from typing import Protocol

from app.core.config import settings


class LLMProvider(Protocol):
    def complete(self, prompt: str) -> str:
        """Returns the model's raw text completion for the given prompt."""
        ...


class LLMConfigurationError(Exception):
    pass


class AnthropicProvider:
    def __init__(self, api_key: str, model: str) -> None:
        from anthropic import Anthropic  # lazy import -- SDK only required when this provider is actually used

        self._client = Anthropic(api_key=api_key)
        self._model = model

    def complete(self, prompt: str) -> str:
        response = self._client.messages.create(
            model=self._model,
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text


def get_llm_provider() -> LLMProvider:
    if settings.LLM_PROVIDER == "anthropic":
        if not settings.ANTHROPIC_API_KEY:
            raise LLMConfigurationError("LLM_PROVIDER=anthropic but ANTHROPIC_API_KEY is not set in backend/.env")
        return AnthropicProvider(api_key=settings.ANTHROPIC_API_KEY, model=settings.ANTHROPIC_MODEL)
    raise LLMConfigurationError(f"Unknown LLM_PROVIDER: {settings.LLM_PROVIDER!r}")
