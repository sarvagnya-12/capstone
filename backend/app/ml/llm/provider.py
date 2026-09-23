"""Provider-agnostic LLM interface for the persona simulation engine. The SRS
permits either an API or an open-source model (PRD Sec14; PROJECT_CONTEXT.md
explicitly notes this project allows external LLM API usage) -- this Protocol
keeps swapping providers a config change plus one small class, not a rewrite.
"""

from typing import Optional, Protocol

from app.core.config import settings
from app.ml.llm.prompt_templates import PERSONA_REACTION_SCHEMA


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


class OllamaProvider:
    """Locally-hosted open-source model via Ollama -- no API key, no per-token
    billing. The SRS explicitly permits an open-source model in place of an API
    (PRD Sec14), so this is a first-class option, not a fallback.

    `response_schema`, when given, is passed to Ollama's `format` parameter,
    which constrains decoding so the model can only emit JSON matching that
    schema. That is a stronger guarantee than AnthropicProvider gets: there the
    output format is merely requested in the prompt and repaired afterwards by
    parse_persona_reaction()'s code-fence handling. The schema is injected by
    get_llm_provider() rather than hardcoded here, so this class stays generic.
    """

    def __init__(self, base_url: str, model: str, response_schema: Optional[dict] = None) -> None:
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._response_schema = response_schema

    def complete(self, prompt: str) -> str:
        import requests  # lazy import, mirroring AnthropicProvider's SDK import

        payload: dict = {"model": self._model, "prompt": prompt, "stream": False}
        if self._response_schema is not None:
            payload["format"] = self._response_schema

        try:
            # Generous timeout: the first call after a cold start pays for
            # loading the model into VRAM (measured ~49s for llama3.1:8b on an
            # RTX 4050), versus ~3s once it is resident.
            response = requests.post(f"{self._base_url}/api/generate", json=payload, timeout=300)
            response.raise_for_status()
        except requests.exceptions.ConnectionError as e:
            raise LLMConfigurationError(
                f"Could not reach Ollama at {self._base_url}. Is it running? "
                "Install from https://ollama.com/download, then `ollama pull "
                f"{self._model}`."
            ) from e
        except requests.exceptions.HTTPError as e:
            # A 404 here almost always means the model was never pulled, which
            # is worth saying outright instead of surfacing a bare status code.
            raise LLMConfigurationError(
                f"Ollama returned {response.status_code} for model {self._model!r}. "
                f"If this is a 404, run `ollama pull {self._model}`. Body: {response.text[:200]}"
            ) from e

        return response.json()["response"]


def get_llm_provider() -> LLMProvider:
    if settings.LLM_PROVIDER == "anthropic":
        if not settings.ANTHROPIC_API_KEY:
            raise LLMConfigurationError("LLM_PROVIDER=anthropic but ANTHROPIC_API_KEY is not set in backend/.env")
        return AnthropicProvider(api_key=settings.ANTHROPIC_API_KEY, model=settings.ANTHROPIC_MODEL)
    if settings.LLM_PROVIDER == "ollama":
        return OllamaProvider(
            base_url=settings.OLLAMA_BASE_URL,
            model=settings.OLLAMA_MODEL,
            response_schema=PERSONA_REACTION_SCHEMA,
        )
    raise LLMConfigurationError(f"Unknown LLM_PROVIDER: {settings.LLM_PROVIDER!r}")
