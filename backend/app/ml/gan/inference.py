"""Generates N controlled variants of a product using the pretrained GAN
(Step 15). Read this before changing the attribute-control logic below.

Real, disentangled attribute control (a clean "color axis" independent from a
"layout axis" in latent space) is NOT available from a generic pretrained
checkpoint out of the box -- reliable, labeled attribute directions normally
require supervised direction-finding against labeled data, or a fine-tuned
domain-specific model (Step 17, explicitly deferred). Per this step's own
plan text ("fall back to documented, coarser controls ... do not silently
claim finer control than the model actually provides"), this is implemented
as:

- color: a real, working HSV hue-shift applied as post-processing on the raw
  GAN output. Not GAN-native, but genuinely controllable and reproducible.
- layout / texture: latent-space perturbation -- small offsets from a shared
  per-product anchor point in Z-space. This produces real, visually distinct
  structural variation (confirmed in Step 15's sample outputs), but it is
  *undifferentiated* -- one perturbation moves overall structure/pose/texture
  together, there is no separate "layout-only" or "texture-only" axis.
- branding_style: the coarsest of the four. A further seed offset with no
  claimed semantic meaning -- a generic pretrained checkpoint has no notion
  of "branding" at all. Recorded plainly as such in `attributes`.

Base-image-conditioned GAN inversion (projecting an uploaded product photo
into this generator's latent space) is deliberately NOT implemented: this
checkpoint's domain (AFHQ cats) is unrelated to uploaded product photos, so
an optimization-based projection would converge to a meaningless "closest
cat" approximation rather than a useful starting point, while adding real
per-request latency (typically hundreds of optimizer steps) for no benefit
until Step 17 provides a domain-appropriate checkpoint. Each product instead
gets a stable per-product anchor seed (deterministic hash of the product id),
so repeated calls for the same product are reproducible without inversion.
"""

import hashlib
from dataclasses import dataclass
from typing import Optional

import numpy as np
import torch
from PIL import Image

from app.ml.gan.model import generate_image_from_latent, load_generator

# Perturbation radius around the per-product anchor latent. Empirically chosen
# (small enough to stay recognizably related, large enough to be visibly
# distinct) -- not derived from any labeled attribute data.
_PERTURBATION_RADIUS = 0.4

_generator_cache: Optional[torch.nn.Module] = None


def _get_generator() -> torch.nn.Module:
    global _generator_cache
    if _generator_cache is None:
        _generator_cache = load_generator()
    return _generator_cache


def _anchor_seed(product_id: str) -> int:
    """Deterministic per-product seed so repeated calls are reproducible."""
    digest = hashlib.sha256(product_id.encode()).hexdigest()
    return int(digest[:8], 16) % (2**31)


def _apply_hue_shift(img_tensor: torch.Tensor, hue_shift_degrees: float) -> Image.Image:
    """img_tensor: (3, H, W) float in [0, 1]. Real, working color control via HSV."""
    array = (img_tensor.permute(1, 2, 0).numpy() * 255).astype(np.uint8)
    pil_img = Image.fromarray(array, mode="RGB").convert("HSV")
    h, s, v = pil_img.split()
    h_array = (np.array(h, dtype=np.int32) + int(hue_shift_degrees / 360 * 255)) % 255
    h = Image.fromarray(h_array.astype(np.uint8), mode="L")
    return Image.merge("HSV", (h, s, v)).convert("RGB")


@dataclass
class VariantResult:
    image: Image.Image
    attributes: dict


def generate_variants(product_id: str, n: int, attribute_hints: Optional[dict] = None) -> list[VariantResult]:
    """Produces n variant images for a product: each is a distinct nearby
    latent-space perturbation (layout/texture proxy) of a shared anchor, plus
    a hue-shift (color) spread across the batch.

    attribute_hints (added Step 25, optional): lets Step 25's optimization
    engine "nudge" the next generation round toward a prior best-scoring
    variant's neighborhood, per the plan's own "latent-space nudging"
    language -- without this hook, propose_next_attributes() would have
    nothing downstream able to consume it. Recognized keys (all optional,
    each independently falls back to the Step 16 default if absent):
      - "anchor_seed": int -- replaces the default per-product hash anchor.
      - "perturbation_radius": float -- replaces _PERTURBATION_RADIUS,
        typically narrower to converge the search around a known-good point.
      - "hue_shift_center_degrees": float -- center the per-variant hue
        spread here instead of sweeping the full 0-360 range.
    """
    hints = attribute_hints or {}
    generator = _get_generator()
    base_seed = hints.get("anchor_seed", _anchor_seed(product_id))
    perturbation_radius = hints.get("perturbation_radius", _PERTURBATION_RADIUS)
    hue_center = hints.get("hue_shift_center_degrees")

    z_anchor = torch.from_numpy(np.random.RandomState(base_seed).randn(1, generator.z_dim).astype("float32"))

    variants = []
    for i in range(n):
        perturbation_rng = np.random.RandomState(base_seed + i + 1)
        z_variant = z_anchor + perturbation_radius * torch.from_numpy(
            perturbation_rng.randn(1, generator.z_dim).astype("float32")
        )
        if hue_center is None:
            hue_shift = (i * 360 / max(n, 1)) % 360
        else:
            # Narrow spread (+/-15deg) around the proposed center, rather than
            # the full 0-360 sweep used when there's no prior result to nudge toward.
            hue_shift = (hue_center + (i - n / 2) * (30 / max(n, 1))) % 360

        img_tensor = generate_image_from_latent(generator, z_variant)
        image = _apply_hue_shift(img_tensor, hue_shift)

        variants.append(
            VariantResult(
                image=image,
                attributes={
                    "generation_method": "gan_latent_variation",
                    "anchor_seed": base_seed,
                    "perturbation_index": i,
                    "perturbation_radius": perturbation_radius,
                    "color_hue_shift_degrees": hue_shift,
                    "branding_seed_offset": i,
                    "nudged_from_prior_round": bool(hints),
                    "note": (
                        "layout/texture varied via nearby latent-space perturbation "
                        "(undifferentiated structural variation, not a disentangled "
                        "single-axis control); color varied via real HSV hue-shift "
                        "post-processing; branding_style carries no semantic meaning "
                        "on this generic pretrained checkpoint"
                    ),
                },
            )
        )

    return variants
