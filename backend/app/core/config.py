from pathlib import Path
from typing import Literal, Optional

from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/.env, resolved from this file's own location -- not the process's
# working directory, which varies (uvicorn runs from backend/, but scripts/
# and alembic can run from the repo root or elsewhere).
_BACKEND_ROOT = Path(__file__).resolve().parents[2]
_ENV_FILE = _BACKEND_ROOT / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=_ENV_FILE, env_file_encoding="utf-8", extra="ignore")

    DATABASE_URL: str

    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 60

    STORAGE_ROOT: str = str(_BACKEND_ROOT / "storage")

    # Comma-separated list of frontend origins allowed to call this API.
    CORS_ORIGINS: str = "http://localhost:5173"

    ENVIRONMENT: Literal["dev", "prod"] = "dev"

    # LLM persona engine (Step 20+). Provider-agnostic by design -- the SRS
    # permits either an API or an open-source model; only the API key
    # variable matching LLM_PROVIDER needs to be set.
    LLM_PROVIDER: Literal["anthropic"] = "anthropic"
    ANTHROPIC_API_KEY: Optional[str] = None
    ANTHROPIC_MODEL: str = "claude-sonnet-5"

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]


settings = Settings()
