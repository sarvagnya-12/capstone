"""Provider-agnostic interface to a hosted diffusion (img2img) API, used by the
hybrid generator backend (app/ml/diffusion/hybrid.py). Mirrors
app/ml/llm/provider.py deliberately: a Protocol rather than an ABC so a test
fake drops in structurally, and a factory that turns configuration mistakes
into one actionable error.

Providers implemented: Gemini (GeminiImageProvider, paid only) and Cloudflare
Workers AI FLUX.2 Klein (CloudflareImageProvider, free daily allowance). Adding another (e.g.
Replicate) is a single class with a `render()` method plus one branch in
get_image_provider(); nothing else in the app needs to change.
"""

import base64
import io
import time
from typing import Optional, Protocol

from PIL import Image

from app.core.config import settings


class ImageProvider(Protocol):
    # True if render() can take the uploaded product photo as an additional
    # reference image (e.g. an image-prompt / IP-Adapter style input). When
    # False, product identity has to come from the text prompt alone.
    supports_reference_image: bool

    def render(
        self,
        init_image: Image.Image,
        prompt: str,
        strength: float,
        seed: int,
        reference_image: Optional[Image.Image] = None,
    ) -> Image.Image:
        """img2img: returns a new RGB image derived from `init_image`.

        strength: 0 keeps init_image, 1 ignores it. Providers that expose no
        strength/seed knob may ignore those arguments.
        """
        ...


class ImageProviderError(Exception):
    """A single render call failed (network error, rejected request, ...).
    The hybrid backend catches this per variant and keeps the GAN concept."""


class ImageConfigurationError(Exception):
    """The image provider is not usable at all with the current settings."""


GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"
# Same price per 1K image as the other current Gemini image models, and the
# one Google's docs name as the recommended default. Override with IMAGE_MODEL.
GEMINI_DEFAULT_MODEL = "gemini-nano-banana-2.1"
# Statuses worth one more attempt: rate limiting and transient server trouble.
_RETRYABLE_STATUSES = {429, 500, 502, 503, 504}


def _jpeg_bytes(image: Image.Image) -> bytes:
    buffer = io.BytesIO()
    image.convert("RGB").save(buffer, format="JPEG", quality=95)
    return buffer.getvalue()


def _strength_instruction(strength: float) -> str:
    """Instruction-based image editors (Gemini, FLUX.2 Klein) have no numeric
    denoise strength, so the strength used elsewhere is translated into how
    closely the edit is told to follow the input image."""
    if strength < 0.35:
        return "Change the first image only subtly: keep its exact shape, proportions and composition."
    if strength < 0.7:
        return ("Keep the overall shape, silhouette and composition of the first image, but re-render it "
                "with realistic materials, clean construction and correct details.")
    return ("Use the first image only as a loose guide to composition and shape; redraw the product "
            "freely and realistically.")


def _edit_instruction(prompt: str, strength: float, has_reference: bool) -> str:
    """The full editing instruction shared by the instruction-based providers."""
    text = (f"Edit the first image into a professional studio product photograph. {prompt}. "
            f"{_strength_instruction(strength)} ")
    if has_reference:
        text += ("The second image is the real product this design is based on: match its "
                 "style, materials and any branding details. ")
    return text + "Output exactly one image, with no text or watermark added."


def _post_with_retries(send, max_attempts: int, give_up=lambda response: False):
    """send() -> response. Retries rate limits and transient server errors
    (with a short backoff), unless give_up(response) says retrying is futile."""
    response = None
    for attempt in range(1, max_attempts + 1):
        response = send()
        if response.status_code not in _RETRYABLE_STATUSES or attempt == max_attempts or give_up(response):
            break
        time.sleep(2.0 * attempt)
    return response


class GeminiImageProvider:
    """Google Gemini image models (Nano Banana family) via the generateContent
    REST API. Image-to-image is done by sending the init image with an
    instruction, so product identity can also come from a second, reference
    image (the uploaded photo) -- which is why supports_reference_image is True.

    Image output is billed per image (no free tier for these models as of
    this writing); the hybrid backend's MAX_API_IMAGES_PER_SIMULATION caps the
    spend per simulation.
    """

    supports_reference_image = True

    def __init__(self, api_key: str, model: str, timeout: float = 120.0, max_attempts: int = 2) -> None:
        self._api_key = api_key
        self._model = model
        self._timeout = timeout
        self._max_attempts = max_attempts

    def render(
        self,
        init_image: Image.Image,
        prompt: str,
        strength: float,
        seed: int,
        reference_image: Optional[Image.Image] = None,
    ) -> Image.Image:
        import requests  # lazy import, mirroring the LLM providers

        parts: list[dict] = [{"text": _edit_instruction(prompt, strength, reference_image is not None)},
                             self._image_part(init_image)]
        if reference_image is not None:
            parts.append(self._image_part(reference_image))

        payload = {
            "contents": [{"parts": parts}],
            "generationConfig": {"responseModalities": ["IMAGE"], "seed": int(seed) % (2**31)},
        }
        url = f"{GEMINI_BASE_URL}/models/{self._model}:generateContent"

        def send():
            try:
                return requests.post(url, json=payload, headers={"x-goog-api-key": self._api_key},
                                     timeout=self._timeout)
            except requests.exceptions.RequestException as e:
                raise ImageProviderError(f"Could not reach the Gemini API: {e}") from e

        response = _post_with_retries(send, self._max_attempts, give_up=self._is_zero_free_tier)
        if response.status_code != 200:
            raise ImageProviderError(self._http_error(response))
        return self._extract_image(response.json())

    @staticmethod
    def _image_part(image: Image.Image) -> dict:
        return {"inline_data": {"mime_type": "image/jpeg", "data": base64.b64encode(_jpeg_bytes(image)).decode("ascii")}}

    @staticmethod
    def _is_zero_free_tier(response) -> bool:
        """A key without billing gets a free-tier quota of 0 for image models.
        That 429 never clears on retry -- it needs billing enabled."""
        text = response.text or ""
        return response.status_code == 429 and "free_tier" in text and "limit: 0" in text

    def _http_error(self, response) -> str:
        detail = response.text[:300]
        hint = ""
        if self._is_zero_free_tier(response):
            hint = (f" The key is on Gemini's free tier, whose quota for {self._model!r} is 0: image models need "
                    "billing enabled on the key's Google Cloud project (https://aistudio.google.com/apikey).")
        elif response.status_code in (401, 403):
            hint = " Check IMAGE_API_KEY, and that billing is enabled for it (Gemini image models have no free tier)."
        elif response.status_code == 404:
            hint = f" Model {self._model!r} not found; set IMAGE_MODEL to one your key lists."
        elif response.status_code == 429:
            hint = " Rate limit or quota reached."
        return f"Gemini returned HTTP {response.status_code}.{hint} Body: {detail}"

    @staticmethod
    def _extract_image(body: dict) -> Image.Image:
        candidates = body.get("candidates") or []
        for candidate in candidates:
            for part in (candidate.get("content") or {}).get("parts") or []:
                inline = part.get("inlineData") or part.get("inline_data")
                if inline and inline.get("data"):
                    return Image.open(io.BytesIO(base64.b64decode(inline["data"]))).convert("RGB")
        # No image came back: usually a safety block or the model answered in text.
        reason = (candidates[0].get("finishReason") if candidates else None) or \
                 (body.get("promptFeedback") or {}).get("blockReason") or "no image in response"
        raise ImageProviderError(f"Gemini returned no image ({reason}).")


CLOUDFLARE_BASE_URL = "https://api.cloudflare.com/client/v4"
CLOUDFLARE_DEFAULT_MODEL = "@cf/black-forest-labs/flux-2-klein-4b"
# FLUX.2 Klein requires every input image to be under 512x512.
CLOUDFLARE_MAX_INPUT = 504


class CloudflareImageProvider:
    """FLUX.2 [klein] 4B on Cloudflare Workers AI. Fits in Workers AI's free
    daily allocation (10,000 neurons/day; ~115 neurons per 1024px edit with two
    512px inputs, so roughly 85 images/day free at current pricing).

    Request is multipart form data: `prompt`, `input_image_0..3`, `width`,
    `height`, `seed` (and `guidance`). The model runs a fixed 4 steps and has no
    denoise strength, so -- as with Gemini -- strength becomes instruction
    wording. Input images must be under 512x512 and are downscaled to fit.
    """

    supports_reference_image = True

    def __init__(self, account_id: str, api_token: str, model: str = CLOUDFLARE_DEFAULT_MODEL,
                 output_size: int = 1024, timeout: float = 120.0, max_attempts: int = 2,
                 flag_retries: int = 3) -> None:
        self._account_id = account_id
        self._api_token = api_token
        self._model = model
        self._output_size = output_size
        self._timeout = timeout
        self._max_attempts = max_attempts
        self._flag_retries = flag_retries

    @staticmethod
    def _is_flagged(response) -> bool:
        """Workers AI's output safety filter (error code 3030) misfires on
        plain shoe photos: measured on identical inputs, the same request
        passed at one output size and was flagged at another, ~half of calls
        overall. It is not deterministic, so a new seed usually passes."""
        return response.status_code == 400 and '"code":3030' in (response.text or "").replace(" ", "")

    @staticmethod
    def _fit_input(image: Image.Image) -> bytes:
        image = image.convert("RGB")
        if max(image.size) > CLOUDFLARE_MAX_INPUT:
            image = image.copy()
            image.thumbnail((CLOUDFLARE_MAX_INPUT, CLOUDFLARE_MAX_INPUT), Image.LANCZOS)
        return _jpeg_bytes(image)

    def render(
        self,
        init_image: Image.Image,
        prompt: str,
        strength: float,
        seed: int,
        reference_image: Optional[Image.Image] = None,
    ) -> Image.Image:
        import requests

        files = {"input_image_0": ("init.jpg", self._fit_input(init_image), "image/jpeg")}
        if reference_image is not None:
            files["input_image_1"] = ("reference.jpg", self._fit_input(reference_image), "image/jpeg")
        url = f"{CLOUDFLARE_BASE_URL}/accounts/{self._account_id}/ai/run/{self._model}"

        for flag_attempt in range(self._flag_retries + 1):
            fields = {
                "prompt": _edit_instruction(prompt, strength, reference_image is not None),
                "width": str(self._output_size),
                "height": str(self._output_size),
                # A flagged output is retried with a different seed: same inputs, new sample.
                "seed": str((int(seed) + flag_attempt * 7919) % (2**31)),
            }

            def send():
                try:
                    # requests builds the multipart body (and its boundary) from data= + files=.
                    return requests.post(url, data=fields, files=files, timeout=self._timeout,
                                         headers={"Authorization": f"Bearer {self._api_token}"})
                except requests.exceptions.RequestException as e:
                    raise ImageProviderError(f"Could not reach Cloudflare Workers AI: {e}") from e

            response = _post_with_retries(send, self._max_attempts, give_up=self._is_daily_limit)
            if not self._is_flagged(response):
                break
        if response.status_code != 200:
            raise ImageProviderError(self._http_error(response))
        try:
            body = response.json()
        except ValueError as e:
            raise ImageProviderError(f"Cloudflare returned non-JSON output: {response.text[:200]}") from e
        result = body.get("result") if isinstance(body.get("result"), dict) else body
        data = result.get("image") if isinstance(result, dict) else None
        if not data:
            raise ImageProviderError(f"Cloudflare returned no image: {str(body)[:300]}")
        return Image.open(io.BytesIO(base64.b64decode(data))).convert("RGB")

    @staticmethod
    def _is_daily_limit(response) -> bool:
        """Running out of the free daily neurons is a 429 that will not clear
        on a retry a few seconds later."""
        text = (response.text or "").lower()
        return response.status_code == 429 and ("daily" in text or "neuron" in text or "allocation" in text)

    def _http_error(self, response) -> str:
        detail = response.text[:300]
        hint = ""
        if self._is_flagged(response):
            hint = (f" The output safety filter flagged all {self._flag_retries + 1} attempts (different seeds); "
                    "this filter misfires on ordinary product photos.")
        elif self._is_daily_limit(response):
            hint = " The free daily Workers AI allocation (10,000 neurons) is used up; it resets daily (UTC)."
        elif response.status_code in (401, 403):
            hint = (" Check IMAGE_API_KEY is a Cloudflare API token with the Workers AI permission, and that "
                    "CLOUDFLARE_ACCOUNT_ID is the account it belongs to.")
        elif response.status_code == 404:
            hint = f" Model {self._model!r} or account {self._account_id!r} not found."
        elif response.status_code == 429:
            hint = " Rate limit reached."
        return f"Cloudflare Workers AI returned HTTP {response.status_code}.{hint} Body: {detail}"


def get_image_provider() -> ImageProvider:
    if not settings.IMAGE_PROVIDER:
        raise ImageConfigurationError(
            "GENERATOR_BACKEND=hybrid but IMAGE_PROVIDER is not set in backend/.env. "
            "Set GENERATOR_BACKEND=gan to use the GAN alone, or configure a provider."
        )
    if settings.IMAGE_PROVIDER == "gemini":
        if not settings.IMAGE_API_KEY:
            raise ImageConfigurationError("IMAGE_PROVIDER=gemini but IMAGE_API_KEY is not set in backend/.env")
        return GeminiImageProvider(api_key=settings.IMAGE_API_KEY, model=settings.IMAGE_MODEL or GEMINI_DEFAULT_MODEL)
    if settings.IMAGE_PROVIDER == "cloudflare":
        missing = [name for name, value in (("IMAGE_API_KEY", settings.IMAGE_API_KEY),
                                            ("CLOUDFLARE_ACCOUNT_ID", settings.CLOUDFLARE_ACCOUNT_ID)) if not value]
        if missing:
            raise ImageConfigurationError(
                f"IMAGE_PROVIDER=cloudflare but {' and '.join(missing)} not set in backend/.env "
                "(API token with the Workers AI permission, and the account ID from the Cloudflare dashboard)."
            )
        return CloudflareImageProvider(account_id=settings.CLOUDFLARE_ACCOUNT_ID, api_token=settings.IMAGE_API_KEY,
                                       model=settings.IMAGE_MODEL or CLOUDFLARE_DEFAULT_MODEL,
                                       output_size=settings.DIFFUSION_OUTPUT_SIZE)
    raise ImageConfigurationError(
        f"Unknown IMAGE_PROVIDER: {settings.IMAGE_PROVIDER!r}. Implemented: 'gemini', 'cloudflare'."
    )
