from pathlib import Path
from typing import Literal, Optional

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/.env, resolved from this file's own location -- not the process's
# working directory, which varies (uvicorn runs from backend/, but scripts/
# and alembic can run from the repo root or elsewhere).
_BACKEND_ROOT = Path(__file__).resolve().parents[2]
_ENV_FILE = _BACKEND_ROOT / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=_ENV_FILE, env_file_encoding="utf-8", extra="ignore")

    DATABASE_URL: str

    @field_validator("DATABASE_URL")
    @classmethod
    def _require_psycopg_driver(cls, value: str) -> str:
        """Only psycopg (v3) is installed, not psycopg2 -- SQLAlchemy's
        bare `postgresql://` defaults to psycopg2 and would fail to find a
        driver. Every hand-written .env in this project already spells out
        `postgresql+psycopg://`, but a managed Postgres provider's
        auto-generated connection string (e.g. Render's `fromDatabase`
        wiring, Step 42) hands back the bare form -- normalize it here so
        that auto-wiring works without a manual edit-the-URL runbook step."""
        for bare_prefix in ("postgresql://", "postgres://"):
            if value.startswith(bare_prefix):
                return "postgresql+psycopg://" + value[len(bare_prefix):]
        return value

    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 60

    STORAGE_ROOT: str = str(_BACKEND_ROOT / "storage")

    # Generator checkpoint used for variant generation (Step 16/17).
    # A `.pt` is a FastGAN trained from scratch on real product photos; a
    # `.pkl` is the original StyleGAN2-ADA path, still selectable. Defaults to
    # the best-FID checkpoint of the shoes run (step 14,000, FID 287.7) rather
    # than the last one, because training was not monotonic -- FID rose again
    # to ~328 by step 18,000.
    GAN_CHECKPOINT: str = str(_BACKEND_ROOT / "storage" / "fastgan" / "models" / "shoes" / "model_28.pt")

    # Comma-separated list of frontend origins allowed to call this API.
    CORS_ORIGINS: str = "http://localhost:5173"

    ENVIRONMENT: Literal["dev", "prod"] = "dev"

    # LLM persona engine (Step 20+). Provider-agnostic by design -- the SRS
    # permits either an API or an open-source model; only the settings
    # matching the selected LLM_PROVIDER need to be set.
    #
    # Defaults to "ollama" because it runs locally with no API key and no
    # billing, so the persona engine works out of the box. "anthropic" needs a
    # console.anthropic.com key with its own billing (a Claude Pro/Max
    # subscription does not cover API usage).
    LLM_PROVIDER: Literal["anthropic", "ollama"] = "ollama"
    ANTHROPIC_API_KEY: Optional[str] = None
    ANTHROPIC_MODEL: str = "claude-sonnet-5"
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "llama3.1:8b"

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]


settings = Settings()
