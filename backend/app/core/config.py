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
    # `.pkl` is the original StyleGAN2-ADA path, still selectable.
    #
    # Defaults to the 150k-image run's final checkpoint (step 50,000). Scored
    # against a common 256-image reference set -- necessary because each run's
    # own FID is measured against its own training distribution, and a more
    # diverse target inflates the number regardless of model quality:
    #     shoes/model_28.pt      (25k imgs,  step 14,000)  FID 313.8
    #     shoes150k/model_18.pt  (150k imgs, step 45,000)  FID 278.2
    #     shoes150k/model_20.pt  (150k imgs, step 50,000)  FID 274.0  <- this
    # Unlike the 25k run, which peaked at step 14,000 and then degraded, the
    # 150k run was still improving at the end, so the last checkpoint is also
    # the best one.
    GAN_CHECKPOINT: str = str(_BACKEND_ROOT / "storage" / "fastgan" / "models" / "shoes150k" / "model_20.pt")

    # Variant generator backend.
    #   "gan"    -- FastGAN only (the measured baseline; default, needs no key).
    #   "hybrid" -- the GAN generates GAN_OVERSAMPLE x n rough concepts, the n
    #               closest to the uploaded product are kept, and a hosted
    #               diffusion API refines each one (img2img) into the final
    #               variant. The GAN explores; diffusion renders.
    GENERATOR_BACKEND: Literal["gan", "hybrid"] = "gan"

    # Hosted diffusion API used by the hybrid backend. The provider is not
    # chosen yet -- leave unset until an adapter exists in
    # app/ml/diffusion/provider.py; the hybrid backend refuses to start with
    # an actionable error rather than silently falling back.
    #   "gemini"     -- Gemini image models; IMAGE_API_KEY = Gemini key (billing required).
    #   "cloudflare" -- FLUX.2 Klein on Workers AI; IMAGE_API_KEY = Cloudflare API
    #                   token (Workers AI permission) + CLOUDFLARE_ACCOUNT_ID. Free daily allowance.
    IMAGE_PROVIDER: Optional[str] = None
    IMAGE_API_KEY: Optional[str] = None
    IMAGE_MODEL: Optional[str] = None
    CLOUDFLARE_ACCOUNT_ID: Optional[str] = None
    # Side length of rendered images. 1024 costs ~115 Workers AI neurons per
    # image (~85/day free); 512 costs ~37 (~270/day) and can be brought back up
    # to 1024 by the ESRGAN upscaler (SR_ENABLED), which works best on clean
    # photo-like input such as diffusion output.
    DIFFUSION_OUTPUT_SIZE: int = 1024
    # img2img denoise strength: 0 returns the init image untouched, 1 ignores
    # it. ~0.4-0.6 keeps the GAN concept's shape while fixing its rendering.
    DIFFUSION_STRENGTH: float = 0.55
    # "seed": init image is the GAN concept (the GAN shapes the result).
    # "product": init image is the uploaded photo (GAN seed is only used to
    # pick the colour/variation hints). Kept switchable so the comparison
    # decides, not an assumption.
    DIFFUSION_INIT: Literal["seed", "product"] = "seed"
    GAN_OVERSAMPLE: int = 3
    # Cost cap: API renders per simulation (across all rounds). Variants past
    # the cap keep their GAN concept image instead of calling the API.
    MAX_API_IMAGES_PER_SIMULATION: int = 24

    # ESRGAN upscaler (app/ml/sr), trained from scratch on the shoe corpus.
    # Applied to every generated variant when enabled: 256px -> 512px.
    # Off until a trained checkpoint exists and has been evaluated.
    SR_ENABLED: bool = False
    SR_CHECKPOINT: str = str(_BACKEND_ROOT / "storage" / "esrgan" / "models" / "shoes512" / "net_g_ema_050000.pt")
    # Final variants are upscaled (one 2x pass) only when their longest side
    # is below this. Diffusion APIs often return 1024px already; doubling
    # those to 2048px costs time and file size for no visible gain.
    SR_TARGET_SIZE: int = 1024
    # Hybrid backend: upscale the 256px GAN concept before it is sent to the
    # diffusion API as the img2img init image, so diffusion starts from a
    # sharp concept instead of stretching a blurry one itself.
    SR_UPSCALE_SEED: bool = True

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
    # Only for a hosted Ollama server (e.g. Ollama's cloud: OLLAMA_BASE_URL
    # pointed at it, plus its API key). Leave unset for a local server.
    OLLAMA_API_KEY: Optional[str] = None

    # Send each variant's image to the persona model so personas react to
    # what the shoe actually looks like, not only a text description.
    # Requires a vision-capable model (e.g. gemma3, qwen2.5vl, llama3.2-vision
    # on Ollama; any current Claude model). Off by default: llama3.1:8b is
    # text-only.
    LLM_VISION: bool = False

    # Ground persona reactions in real Amazon reviews of similar shoes
    # (app/ml/retrieval). Needs the index built by scripts/build_review_index.py;
    # if it is missing, personas run without grounding and a warning is logged.
    REVIEW_GROUNDING_ENABLED: bool = False
    REVIEW_INDEX_DIR: str = str(_BACKEND_ROOT / "storage" / "review_index")
    REVIEW_GROUNDING_K: int = 5

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]


settings = Settings()
