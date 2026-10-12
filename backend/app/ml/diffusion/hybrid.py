"""Hybrid variant generation: the GAN explores, a hosted diffusion model renders.

1. The FastGAN generates GAN_OVERSAMPLE x n rough design concepts around the
   product's anchor latent (optimiser hints still steer this, exactly as in the
   GAN-only path).
2. The n concepts whose silhouette is closest to the uploaded product photo are
   kept, with a penalty for near-duplicates so the n stay distinct.
3. Each kept concept is refined by the diffusion API (img2img) using a prompt
   built from the product's own name/description plus the colour the GAN
   variant was assigned.

Failures are isolated per variant: if a render fails, or the per-simulation
API budget is used up, that variant keeps its GAN concept image and is marked
generation_method="gan", so a flaky or exhausted API never aborts a simulation.
"""

import logging
from typing import Callable, Optional

import numpy as np
import torch
from PIL import Image

from app.core.config import settings
from app.ml.diffusion.provider import ImageProvider
from app.ml.gan.inference import VariantResult, _apply_hue_shift, generate_variants
from app.ml.llm.prompt_templates import _HUE_NAMES

logger = logging.getLogger(__name__)

HYBRID_METHOD = "gan+diffusion"
GAN_FALLBACK_METHOD = "gan"

# Silhouette comparison resolution. Small on purpose: this compares overall
# shape against the uploaded photo, not detail.
_THUMB = (32, 32)
# Weight of the near-duplicate penalty in greedy seed selection.
_DIVERSITY_WEIGHT = 0.5
_DESCRIPTION_CHARS = 200


def _silhouette(img: Image.Image) -> np.ndarray:
    return np.asarray(img.convert("L").resize(_THUMB), dtype=np.float32).ravel() / 255.0


def select_seeds(candidates: list[VariantResult], product_image: Image.Image, n: int) -> list[VariantResult]:
    """Greedy, deterministic pick of n candidates: close to the product's
    silhouette, far from already-picked ones. A cheap heuristic (no new
    dependency), not a learned similarity -- its job is only to drop the
    GAN's malformed or off-shape samples before paying for a render."""
    target = _silhouette(product_image)
    vectors = [_silhouette(c.image) for c in candidates]
    distance_to_product = [float(np.linalg.norm(v - target)) for v in vectors]

    selected: list[int] = []
    remaining = list(range(len(candidates)))
    while remaining and len(selected) < n:
        def cost(i: int) -> float:
            if not selected:
                return distance_to_product[i]
            nearest = min(float(np.linalg.norm(vectors[i] - vectors[j])) for j in selected)
            return distance_to_product[i] - _DIVERSITY_WEIGHT * nearest

        best = min(remaining, key=lambda i: (cost(i), i))
        selected.append(best)
        remaining.remove(best)
    return [candidates[i] for i in selected]


def colour_phrase(hue_degrees: Optional[float]) -> str:
    if hue_degrees is None:
        return "the original colourway"
    hue = float(hue_degrees) % 360
    closest = min(_HUE_NAMES, key=lambda pair: min(abs(hue - pair[0]), 360 - abs(hue - pair[0])))
    return closest[1]


def build_render_prompt(name: str, category: str, description: Optional[str], brand: Optional[str],
                        hue_degrees: Optional[float]) -> str:
    """`brand` is deliberately left out of the image prompt: image models
    render a brand name as (garbled) lettering on the product -- measured on
    FLUX.2 Klein, "Acme" came back as an "ACMIE" logo across the upper. The
    brand still reaches personas through the persona prompt."""
    parts = [f"Professional studio product photo of {name}, a {category}"]
    if description:
        parts.append(description.strip()[:_DESCRIPTION_CHARS])
    parts.append(f"in {colour_phrase(hue_degrees)}")
    parts.append("single product, centred, plain white background, soft even lighting, photorealistic, high detail")
    return ", ".join(parts)


def generate_hybrid_variants(
    *,
    product_id: str,
    product_image: Image.Image,
    name: str,
    category: str,
    description: Optional[str],
    brand: Optional[str],
    n: int,
    provider: ImageProvider,
    api_budget: int,
    attribute_hints: Optional[dict] = None,
    seed_transform: Optional[Callable[[Image.Image], Image.Image]] = None,
) -> list[VariantResult]:
    """seed_transform: applied to each kept GAN concept before it is used as
    the img2img init image -- the ESRGAN upscaler, when enabled, so diffusion
    starts from a sharp 512px concept rather than stretching a 256px one."""
    candidates = generate_variants(
        product_id, n * max(settings.GAN_OVERSAMPLE, 1), attribute_hints=attribute_hints, apply_hue_shift=False
    )
    seeds = select_seeds(candidates, product_image, n)

    use_reference = getattr(provider, "supports_reference_image", False)
    results = []
    for index, seed in enumerate(seeds):
        attributes = dict(seed.attributes)
        attributes["gan_candidate_index"] = attributes["perturbation_index"]
        # Re-index so personas see "design variation 1..n", not a gap-ridden
        # 1..(n x oversample) sequence.
        attributes["perturbation_index"] = index
        hue = attributes.get("color_hue_shift_degrees")
        prompt = build_render_prompt(name, category, description, brand, hue)
        attributes["render_prompt"] = prompt
        attributes["diffusion_init"] = settings.DIFFUSION_INIT
        attributes["diffusion_strength"] = settings.DIFFUSION_STRENGTH
        attributes["note"] = (
            "GAN concept (latent-space perturbation) refined by a hosted diffusion "
            "model via img2img; colour rendered from the prompt, not a hue rotation"
        )

        if index >= api_budget:
            attributes["generation_method"] = GAN_FALLBACK_METHOD
            attributes["render_skipped"] = "per-simulation API image budget reached"
            results.append(_gan_fallback(seed, attributes))
            continue

        if settings.DIFFUSION_INIT == "seed":
            init_image = seed.image
            if seed_transform is not None:
                try:
                    init_image = seed_transform(seed.image)
                    attributes["seed_upscaled"] = True
                except Exception as e:
                    # Upscaling is an improvement, not a requirement: render
                    # from the raw concept rather than lose the variant.
                    logger.warning("Seed upscaling failed for product=%s variant=%d: %s", product_id, index, e)
        else:
            init_image = product_image
        try:
            rendered = provider.render(
                init_image=init_image,
                prompt=prompt,
                strength=settings.DIFFUSION_STRENGTH,
                seed=int(attributes["anchor_seed"]) + attributes["gan_candidate_index"],
                # When the photo is already the init image, sending it again
                # as the reference adds cost and nothing else.
                reference_image=product_image if use_reference and settings.DIFFUSION_INIT == "seed" else None,
            )
            attributes["generation_method"] = HYBRID_METHOD
            results.append(VariantResult(image=rendered.convert("RGB"), attributes=attributes, seed_image=seed.image))
        except Exception as e:  # isolate per variant, like persona_service's LLM calls
            logger.warning("Diffusion render failed for product=%s variant=%d: %s", product_id, index, e)
            attributes["generation_method"] = GAN_FALLBACK_METHOD
            attributes["render_error"] = str(e)[:300]
            results.append(_gan_fallback(seed, attributes))

    return results


def _gan_fallback(seed: VariantResult, attributes: dict) -> VariantResult:
    """The GAN-only output for a variant that was not rendered. Applies the
    recorded hue here, since the hybrid path generated the concept without it
    -- otherwise `color_hue_shift_degrees` (which the persona prompt reads)
    would describe a colour the image does not have."""
    tensor = torch.from_numpy(np.asarray(seed.image, dtype=np.float32) / 255.0).permute(2, 0, 1)
    image = _apply_hue_shift(tensor, float(attributes.get("color_hue_shift_degrees") or 0.0))
    return VariantResult(image=image, attributes=attributes, seed_image=None)
