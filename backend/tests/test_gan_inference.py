"""Step 15/16: pretrained GAN integration and latent-space attribute
variation. Uses the fake_gan_generator fixture (tiny random-weight network)
rather than the real 364MB checkpoint -- verifies pipeline mechanics
(count/shape/persistence/reproducibility), not real image quality, per this
step's own guidance."""

from PIL import Image

from app.ml.gan import inference


def test_generate_variants_produces_n_results_with_expected_attributes(fake_gan_generator):
    results = inference.generate_variants("product-abc", 3)
    assert len(results) == 3
    for i, result in enumerate(results):
        assert result.attributes["generation_method"] == "gan_latent_variation"
        assert result.attributes["perturbation_index"] == i
        assert result.image.size[0] > 0 and result.image.size[1] > 0


def test_generate_variants_anchor_is_deterministic_per_product(fake_gan_generator):
    first = inference.generate_variants("same-product-id", 2)
    second = inference.generate_variants("same-product-id", 2)
    assert first[0].attributes["anchor_seed"] == second[0].attributes["anchor_seed"]

    different = inference.generate_variants("different-product-id", 2)
    assert different[0].attributes["anchor_seed"] != first[0].attributes["anchor_seed"]


def test_generate_variants_respects_attribute_hints(fake_gan_generator):
    results = inference.generate_variants(
        "hinted-product", 2, attribute_hints={"anchor_seed": 4242, "perturbation_radius": 0.1}
    )
    assert results[0].attributes["anchor_seed"] == 4242
    assert results[0].attributes["perturbation_radius"] == 0.1
    assert results[0].attributes["nudged_from_prior_round"] is True


def test_generate_variants_for_simulation_direct(db_session, fake_gan_generator):
    """Drives gan_service directly against a hand-built Simulation/Product
    row rather than through the API, since variant generation itself doesn't
    depend on any HTTP-layer concern."""
    import uuid

    from app.models.product import Product
    from app.models.simulation import Simulation
    from app.models.user import User, UserRole
    from app.services import gan_service, storage_service
    from app.core.security import hash_password

    user = User(org_name="GAN Direct Org", email="gandirect@test.com", hashed_password=hash_password("x"), role=UserRole.USER)
    db_session.add(user)
    db_session.flush()

    product_id = uuid.uuid4()
    image = Image.new("RGB", (64, 64), color=(50, 50, 200))
    relative_path = storage_service.save_pil_image(image, subfolder=f"products/{product_id}", filename="original.jpg")

    product = Product(
        id=product_id,
        user_id=user.id,
        name="Direct GAN Product",
        description="x",
        category="footwear",
        original_image_path=relative_path,
        preprocessed_image_path=relative_path,
    )
    db_session.add(product)
    db_session.flush()

    simulation = Simulation(
        product_id=product.id,
        user_id=user.id,
        pricing_strategy={"tiers": [{"tier_name": "standard", "price": 10.0}]},
        target_demographic={},
    )
    db_session.add(simulation)
    db_session.flush()

    variants = gan_service.generate_variants_for_simulation(db_session, simulation.id, 3)

    assert len(variants) == 3
    for variant in variants:
        assert variant.id is not None
        assert variant.simulation_id == simulation.id
        assert variant.image_path
        # FID needs >=2 real and >=2 fake images (Step 18); this product has
        # 2 real refs (original + preprocessed) and 3 fake variants, so a
        # real numeric score is expected, not the None fallback.
        assert variant.fid_score is not None
