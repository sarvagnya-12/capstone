import uuid

import numpy as np
import torch
from PIL import Image
from sqlalchemy.orm import Session

from app.ml.gan.evaluation import compute_fid
from app.ml.gan.inference import generate_variants
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


def generate_variants_for_simulation(db: Session, simulation_id: uuid.UUID, n: int) -> list[ProductVariant]:
    simulation = db.get(Simulation, simulation_id)
    if simulation is None:
        raise SimulationNotFoundError(simulation_id)

    product = db.get(Product, simulation.product_id)
    if product is None:
        raise ProductNotFoundError(simulation.product_id)

    results = generate_variants(str(product.id), n)

    variant_rows = []
    fake_tensors = []
    for result in results:
        variant_id = uuid.uuid4()
        relative_path = save_pil_image(
            result.image,
            subfolder=f"products/{product.id}/variants",
            filename=f"{variant_id}.jpg",
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
