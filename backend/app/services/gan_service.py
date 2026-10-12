import uuid
from typing import Optional

import numpy as np
import torch
from PIL import Image
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.ml.diffusion.hybrid import HYBRID_METHOD, generate_hybrid_variants
from app.ml.diffusion.provider import get_image_provider
from app.ml.gan.evaluation import compute_fid
from app.ml.gan.inference import VariantResult, generate_variants
from app.ml.sr.upscale import upscale
from app.models.product import Product
from app.models.product_variant import ProductVariant
from app.models.simulation import Simulation
from app.services.image_preprocessing import TARGET_SIZE
from app.services.storage_service import get_path, save_pil_image


class SimulationNotFoundError(Exception):
    pass


class ProductNotFoundError(Exception):
    pass


def _load_image_tensor(relative_path: str) -> torch.Tensor:
    """Loads an image from STORAGE_ROOT/<relative_path> as a (3, *TARGET_SIZE)
    float tensor in [0, 1] -- the format app.ml.gan.evaluation.compute_fid
    expects. Resized to TARGET_SIZE so real (original-resolution) and fake
    (GAN-native-resolution) images can be stacked into one batch regardless
    of their original dimensions -- e.g. an unprocessed original upload and a
    256x256 preprocessed/generated image are not naturally the same shape."""
    with Image.open(get_path(relative_path)) as img:
        img = img.convert("RGB").resize(TARGET_SIZE)
        array = np.array(img, dtype=np.float32) / 255.0
    return torch.from_numpy(array).permute(2, 0, 1)


def _generate_hybrid(
    db: Session, simulation: Simulation, product: Product, n: int, attribute_hints: Optional[dict]
) -> list[VariantResult]:
    """GAN concepts refined by the hosted diffusion API (app/ml/diffusion/hybrid.py).
    The API budget is per simulation, across all optimisation rounds."""
    provider = get_image_provider()  # raises ImageConfigurationError if unconfigured -- fail loudly, not silently GAN-only
    renders_used = db.scalar(
        select(func.count()).select_from(ProductVariant).where(
            ProductVariant.simulation_id == simulation.id,
            ProductVariant.generation_method == HYBRID_METHOD,
        )
    ) or 0
    image_path = product.preprocessed_image_path or product.original_image_path
    with Image.open(get_path(image_path)) as img:
        product_image = img.convert("RGB").resize(TARGET_SIZE)
    return generate_hybrid_variants(
        product_id=str(product.id),
        product_image=product_image,
        name=product.name,
        category=product.category,
        description=product.description,
        brand=product.brand,
        n=n,
        provider=provider,
        api_budget=max(settings.MAX_API_IMAGES_PER_SIMULATION - renders_used, 0),
        attribute_hints=attribute_hints,
        seed_transform=upscale if settings.SR_ENABLED and settings.SR_UPSCALE_SEED else None,
    )


def generate_variants_for_simulation(
    db: Session, simulation_id: uuid.UUID, n: int, attribute_hints: Optional[dict] = None
) -> list[ProductVariant]:
    simulation = db.get(Simulation, simulation_id)
    if simulation is None:
        raise SimulationNotFoundError(simulation_id)

    product = db.get(Product, simulation.product_id)
    if product is None:
        raise ProductNotFoundError(simulation.product_id)

    if settings.GENERATOR_BACKEND == "hybrid":
        results = _generate_hybrid(db, simulation, product, n, attribute_hints)
    else:
        results = generate_variants(str(product.id), n, attribute_hints=attribute_hints)

    if settings.SR_ENABLED:
        for result in results:
            if max(result.image.size) < settings.SR_TARGET_SIZE:
                result.image = upscale(result.image)
                result.attributes["upscaled"] = "esrgan_2x"

    variant_rows = []
    fake_tensors = []
    for result in results:
        variant_id = uuid.uuid4()
        relative_path = save_pil_image(
            result.image,
            subfolder=f"products/{product.id}/variants",
            filename=f"{variant_id}.jpg",
        )
        if result.seed_image is not None:
            result.attributes["seed_image_path"] = save_pil_image(
                result.seed_image,
                subfolder=f"products/{product.id}/variants",
                filename=f"{variant_id}_gan_seed.jpg",
            )
        variant = ProductVariant(
            id=variant_id,
            product_id=product.id,
            simulation_id=simulation.id,
            image_path=relative_path,
            attributes=result.attributes,
            generation_method=result.attributes["generation_method"],
        )
        db.add(variant)
        variant_rows.append(variant)
        fake_tensors.append(_load_image_tensor(relative_path))

    # FID is a set-level statistic (see evaluation.py docstring): the whole
    # batch shares one score against the product's own reference images,
    # rather than each variant getting an independently-computed FID.
    real_tensors = [_load_image_tensor(product.original_image_path)]
    if product.preprocessed_image_path:
        real_tensors.append(_load_image_tensor(product.preprocessed_image_path))
    fid_score = compute_fid(real_tensors, fake_tensors)
    for variant in variant_rows:
        variant.fid_score = fid_score

    db.commit()
    for variant in variant_rows:
        db.refresh(variant)
    return variant_rows
