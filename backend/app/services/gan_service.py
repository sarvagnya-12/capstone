import uuid

from sqlalchemy.orm import Session

from app.ml.gan.inference import generate_variants
from app.models.product import Product
from app.models.product_variant import ProductVariant
from app.models.simulation import Simulation
from app.services.storage_service import save_pil_image


class SimulationNotFoundError(Exception):
    pass


class ProductNotFoundError(Exception):
    pass


def generate_variants_for_simulation(db: Session, simulation_id: uuid.UUID, n: int) -> list[ProductVariant]:
    simulation = db.get(Simulation, simulation_id)
    if simulation is None:
        raise SimulationNotFoundError(simulation_id)

    product = db.get(Product, simulation.product_id)
    if product is None:
        raise ProductNotFoundError(simulation.product_id)

    results = generate_variants(str(product.id), n)

    variant_rows = []
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

    db.commit()
    for variant in variant_rows:
        db.refresh(variant)
    return variant_rows
