"""GeminiImageProvider and the provider factory. requests.post is mocked, so
these pin down the request this project sends and how responses and errors
are handled -- not what Gemini actually returns (see the live smoke test)."""

import base64
import io

import pytest
import requests
from PIL import Image

from app.core.config import settings
from app.ml.diffusion import provider as provider_module
from app.ml.diffusion.provider import (
    GEMINI_DEFAULT_MODEL,
    GeminiImageProvider,
    ImageConfigurationError,
    ImageProviderError,
    get_image_provider,
)


def _png_b64(color=(10, 20, 30), size=(8, 8)) -> str:
    buffer = io.BytesIO()
    Image.new("RGB", size, color).save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode()


class _Resp:
    def __init__(self, body=None, status=200, text=""):
        self._body, self.status_code, self.text = body or {}, status, text

    def json(self):
        return self._body


def _ok(camel=True):
    key = "inlineData" if camel else "inline_data"
    return _Resp({"candidates": [{"content": {"parts": [{"text": "here"}, {key: {"mime_type": "image/png", "data": _png_b64()}}]}}]})


@pytest.fixture()
def no_sleep(monkeypatch):
    monkeypatch.setattr(provider_module.time, "sleep", lambda s: None)


def _provider(**kw):
    return GeminiImageProvider("secret-key", "gemini-test", **kw)


def test_request_shape_and_returned_image(monkeypatch):
    sent = {}

    def fake_post(url, json=None, headers=None, timeout=None):
        sent.update(url=url, json=json, headers=headers, timeout=timeout)
        return _ok()

    monkeypatch.setattr(requests, "post", fake_post)
    init, ref = Image.new("RGB", (16, 16), (200, 0, 0)), Image.new("RGB", (16, 16), (0, 200, 0))
    out = _provider().render(init, "a red sneaker", strength=0.55, seed=42, reference_image=ref)

    assert sent["url"].endswith("/models/gemini-test:generateContent")
    assert sent["headers"] == {"x-goog-api-key": "secret-key"}  # header, never in the URL
    assert "secret-key" not in sent["url"]
    parts = sent["json"]["contents"][0]["parts"]
    assert "a red sneaker" in parts[0]["text"] and "second image is the real product" in parts[0]["text"]
    assert [("inline_data" in p) for p in parts] == [False, True, True]  # text, init, reference
    assert parts[1]["inline_data"]["mime_type"] == "image/jpeg"
    assert sent["json"]["generationConfig"] == {"responseModalities": ["IMAGE"], "seed": 42}
    assert out.mode == "RGB" and out.size == (8, 8)


def test_no_reference_image_sends_only_init(monkeypatch):
    sent = {}
    monkeypatch.setattr(requests, "post", lambda url, json=None, **kw: sent.update(json=json) or _ok())
    _provider().render(Image.new("RGB", (4, 4)), "p", 0.5, 1)
    parts = sent["json"]["contents"][0]["parts"]
    assert len(parts) == 2 and "second image" not in parts[0]["text"]


def test_strength_changes_the_instruction(monkeypatch):
    texts = []
    monkeypatch.setattr(requests, "post",
                        lambda url, json=None, **kw: texts.append(json["contents"][0]["parts"][0]["text"]) or _ok())
    for strength in (0.2, 0.5, 0.9):
        _provider().render(Image.new("RGB", (4, 4)), "p", strength, 1)
    assert "subtly" in texts[0] and "Keep the overall shape" in texts[1] and "loose guide" in texts[2]


def test_accepts_snake_case_inline_data(monkeypatch):
    monkeypatch.setattr(requests, "post", lambda *a, **k: _ok(camel=False))
    assert _provider().render(Image.new("RGB", (4, 4)), "p", 0.5, 1).size == (8, 8)


def test_seed_is_kept_in_int32_range(monkeypatch):
    sent = {}
    monkeypatch.setattr(requests, "post", lambda url, json=None, **kw: sent.update(json=json) or _ok())
    _provider().render(Image.new("RGB", (4, 4)), "p", 0.5, 2**40 + 5)
    assert 0 <= sent["json"]["generationConfig"]["seed"] < 2**31


@pytest.mark.parametrize("status,needle", [(403, "billing"), (404, "IMAGE_MODEL"), (400, "HTTP 400")])
def test_http_errors_become_actionable(monkeypatch, status, needle):
    monkeypatch.setattr(requests, "post", lambda *a, **k: _Resp(status=status, text="nope"))
    with pytest.raises(ImageProviderError, match=needle):
        _provider().render(Image.new("RGB", (4, 4)), "p", 0.5, 1)


def test_retries_once_on_rate_limit_then_succeeds(monkeypatch, no_sleep):
    calls = []
    monkeypatch.setattr(requests, "post", lambda *a, **k: calls.append(1) or (_Resp(status=429) if len(calls) == 1 else _ok()))
    assert _provider().render(Image.new("RGB", (4, 4)), "p", 0.5, 1).size == (8, 8)
    assert len(calls) == 2


def test_gives_up_after_max_attempts(monkeypatch, no_sleep):
    calls = []
    monkeypatch.setattr(requests, "post", lambda *a, **k: calls.append(1) or _Resp(status=503))
    with pytest.raises(ImageProviderError, match="503"):
        _provider().render(Image.new("RGB", (4, 4)), "p", 0.5, 1)
    assert len(calls) == 2


def test_zero_free_tier_quota_explains_billing_and_does_not_retry(monkeypatch, no_sleep):
    # Body shape as actually returned by Gemini for a key without billing.
    body = ("Quota exceeded for metric: generativelanguage.googleapis.com/"
            "generate_content_free_tier_requests, limit: 0, model: gemini-test")
    calls = []
    monkeypatch.setattr(requests, "post", lambda *a, **k: calls.append(1) or _Resp(status=429, text=body))
    with pytest.raises(ImageProviderError, match="billing enabled"):
        _provider().render(Image.new("RGB", (4, 4)), "p", 0.5, 1)
    assert len(calls) == 1


def test_connection_failure_is_a_provider_error(monkeypatch):
    def boom(*a, **k):
        raise requests.exceptions.ConnectionError("dns")

    monkeypatch.setattr(requests, "post", boom)
    with pytest.raises(ImageProviderError, match="Could not reach"):
        _provider().render(Image.new("RGB", (4, 4)), "p", 0.5, 1)


def test_text_only_or_blocked_response_has_a_reason(monkeypatch):
    blocked = _Resp({"candidates": [{"finishReason": "SAFETY", "content": {"parts": [{"text": "I can't"}]}}]})
    monkeypatch.setattr(requests, "post", lambda *a, **k: blocked)
    with pytest.raises(ImageProviderError, match="SAFETY"):
        _provider().render(Image.new("RGB", (4, 4)), "p", 0.5, 1)

    monkeypatch.setattr(requests, "post", lambda *a, **k: _Resp({"promptFeedback": {"blockReason": "OTHER"}}))
    with pytest.raises(ImageProviderError, match="OTHER"):
        _provider().render(Image.new("RGB", (4, 4)), "p", 0.5, 1)


def test_factory_builds_gemini_with_default_model(monkeypatch):
    monkeypatch.setattr(settings, "IMAGE_PROVIDER", "gemini")
    monkeypatch.setattr(settings, "IMAGE_API_KEY", "k")
    monkeypatch.setattr(settings, "IMAGE_MODEL", None)
    p = get_image_provider()
    assert isinstance(p, GeminiImageProvider) and p._model == GEMINI_DEFAULT_MODEL and p.supports_reference_image
    monkeypatch.setattr(settings, "IMAGE_MODEL", "gemini-3.1-flash-lite-image")
    assert get_image_provider()._model == "gemini-3.1-flash-lite-image"


# --- Cloudflare Workers AI (FLUX.2 Klein) -----------------------------------

from app.ml.diffusion.provider import CLOUDFLARE_DEFAULT_MODEL, CLOUDFLARE_MAX_INPUT, CloudflareImageProvider  # noqa: E402


def _cf_ok(wrapped=True):
    image = {"image": _png_b64(size=(16, 16))}
    return _Resp({"result": image, "success": True, "errors": []} if wrapped else image)


def _cf():
    return CloudflareImageProvider("acct-123", "cf-token", output_size=1024)


def test_cloudflare_request_is_multipart_with_images_and_auth(monkeypatch):
    sent = {}

    def fake_post(url, data=None, files=None, headers=None, timeout=None):
        sent.update(url=url, data=data, files=files, headers=headers)
        return _cf_ok()

    monkeypatch.setattr(requests, "post", fake_post)
    big = Image.new("RGB", (1024, 1024), (200, 0, 0))
    out = _cf().render(big, "a red sneaker", 0.55, 2**40, reference_image=Image.new("RGB", (256, 256)))

    assert sent["url"] == f"https://api.cloudflare.com/client/v4/accounts/acct-123/ai/run/{CLOUDFLARE_DEFAULT_MODEL}"
    assert sent["headers"] == {"Authorization": "Bearer cf-token"}
    assert "a red sneaker" in sent["data"]["prompt"] and "second image is the real product" in sent["data"]["prompt"]
    assert sent["data"]["width"] == sent["data"]["height"] == "1024"
    assert 0 <= int(sent["data"]["seed"]) < 2**31
    assert set(sent["files"]) == {"input_image_0", "input_image_1"}
    # Klein rejects inputs of 512px or more: a 1024px init must be downscaled.
    init_bytes = sent["files"]["input_image_0"][1]
    assert max(Image.open(io.BytesIO(init_bytes)).size) <= CLOUDFLARE_MAX_INPUT < 512
    assert out.size == (16, 16) and out.mode == "RGB"


def test_cloudflare_without_reference_sends_one_image(monkeypatch):
    sent = {}
    monkeypatch.setattr(requests, "post", lambda url, data=None, files=None, **k: sent.update(files=files) or _cf_ok())
    _cf().render(Image.new("RGB", (64, 64)), "p", 0.5, 1)
    assert list(sent["files"]) == ["input_image_0"]


def test_cloudflare_accepts_unwrapped_image(monkeypatch):
    monkeypatch.setattr(requests, "post", lambda *a, **k: _cf_ok(wrapped=False))
    assert _cf().render(Image.new("RGB", (64, 64)), "p", 0.5, 1).size == (16, 16)


def test_cloudflare_missing_image_is_an_error(monkeypatch):
    monkeypatch.setattr(requests, "post", lambda *a, **k: _Resp({"result": {}, "success": True}))
    with pytest.raises(ImageProviderError, match="no image"):
        _cf().render(Image.new("RGB", (64, 64)), "p", 0.5, 1)


def test_cloudflare_daily_limit_is_explained_and_not_retried(monkeypatch, no_sleep):
    calls = []
    body = '{"success":false,"errors":[{"code":4006,"message":"you have used up your daily free allocation of 10,000 neurons"}]}'
    monkeypatch.setattr(requests, "post", lambda *a, **k: calls.append(1) or _Resp(status=429, text=body))
    with pytest.raises(ImageProviderError, match="daily Workers AI allocation"):
        _cf().render(Image.new("RGB", (64, 64)), "p", 0.5, 1)
    assert len(calls) == 1


_FLAGGED = ('{"errors":[{"message":"AiError: AiError: Your output has been flagged. Please choose another '
            'prompt / input image combination (x)","code":3030}],"success":false,"result":{},"messages":[]}')


def test_cloudflare_retries_a_flagged_output_with_a_new_seed(monkeypatch):
    seeds = []

    def fake_post(url, data=None, **kw):
        seeds.append(data["seed"])
        return _Resp(status=400, text=_FLAGGED) if len(seeds) < 3 else _cf_ok()

    monkeypatch.setattr(requests, "post", fake_post)
    assert _cf().render(Image.new("RGB", (64, 64)), "p", 0.5, 100).size == (16, 16)
    assert len(seeds) == 3 and len(set(seeds)) == 3


def test_cloudflare_gives_up_after_flag_retries(monkeypatch):
    calls = []
    monkeypatch.setattr(requests, "post", lambda *a, **k: calls.append(1) or _Resp(status=400, text=_FLAGGED))
    provider = CloudflareImageProvider("a", "t", flag_retries=2)
    with pytest.raises(ImageProviderError, match="safety filter flagged all 3 attempts"):
        provider.render(Image.new("RGB", (64, 64)), "p", 0.5, 1)
    assert len(calls) == 3


def test_cloudflare_other_400s_are_not_retried(monkeypatch):
    calls = []
    monkeypatch.setattr(requests, "post", lambda *a, **k: calls.append(1) or _Resp(status=400, text='{"errors":[{"code":5006}]}'))
    with pytest.raises(ImageProviderError, match="HTTP 400"):
        _cf().render(Image.new("RGB", (64, 64)), "p", 0.5, 1)
    assert len(calls) == 1


def test_cloudflare_auth_error_names_the_settings(monkeypatch):
    monkeypatch.setattr(requests, "post", lambda *a, **k: _Resp(status=401, text="unauthorized"))
    with pytest.raises(ImageProviderError, match="CLOUDFLARE_ACCOUNT_ID"):
        _cf().render(Image.new("RGB", (64, 64)), "p", 0.5, 1)


def test_factory_builds_cloudflare(monkeypatch):
    monkeypatch.setattr(settings, "IMAGE_PROVIDER", "cloudflare")
    monkeypatch.setattr(settings, "IMAGE_API_KEY", "t")
    monkeypatch.setattr(settings, "IMAGE_MODEL", None)
    monkeypatch.setattr(settings, "CLOUDFLARE_ACCOUNT_ID", "a")
    monkeypatch.setattr(settings, "DIFFUSION_OUTPUT_SIZE", 512)
    p = get_image_provider()
    assert isinstance(p, CloudflareImageProvider) and p._model == CLOUDFLARE_DEFAULT_MODEL and p._output_size == 512


def test_factory_names_missing_cloudflare_settings(monkeypatch):
    monkeypatch.setattr(settings, "IMAGE_PROVIDER", "cloudflare")
    monkeypatch.setattr(settings, "IMAGE_API_KEY", None)
    monkeypatch.setattr(settings, "CLOUDFLARE_ACCOUNT_ID", None)
    with pytest.raises(ImageConfigurationError, match="IMAGE_API_KEY and CLOUDFLARE_ACCOUNT_ID"):
        get_image_provider()


def test_factory_requires_a_key_for_gemini(monkeypatch):
    monkeypatch.setattr(settings, "IMAGE_PROVIDER", "gemini")
    monkeypatch.setattr(settings, "IMAGE_API_KEY", None)
    with pytest.raises(ImageConfigurationError, match="IMAGE_API_KEY"):
        get_image_provider()
