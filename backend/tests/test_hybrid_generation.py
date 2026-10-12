"""Hybrid generator backend: GAN concepts refined by a (fake) diffusion API.

Uses the same fakes as the rest of the suite -- a tiny random-weight GAN and a
fake image provider -- so these prove the wiring and the failure/cost rules,
not image quality. Quality needs a real provider and a by-eye comparison.
"""

import uuid

import numpy as np
import pytest
from PIL import Image

from app.core.config import settings
from app.ml.diffusion import hybrid
from app.ml.diffusion.provider import ImageConfigurationError, get_image_provider
from app.ml.gan.inference import VariantResult


def _make_product_simulation(db):
    from app.core.security import hash_password
    from app.models.product import Product
    from app.models.simulation import Simulation
    from app.models.user import User, UserRole
    from app.services import storage_service

    user = User(org_name="Hybrid Org", email=f"{uuid.uuid4()}@test.com", hashed_password=hash_password("x"),
                role=UserRole.USER)
    db.add(user)
    db.flush()

    product_id = uuid.uuid4()
    image = Image.new("RGB", (64, 64), color=(200, 50, 50))
    path = storage_service.save_pil_image(image, subfolder=f"products/{product_id}", filename="original.jpg")
    product = Product(id=product_id, user_id=user.id, name="Trail Runner", description="Lightweight running shoe",
                      brand="Acme", category="footwear", original_image_path=path, preprocessed_image_path=path)
    db.add(product)
    db.flush()

    simulation = Simulation(product_id=product.id, user_id=user.id,
                            pricing_strategy={"tiers": [{"tier_name": "standard", "price": 10.0}]},
                            target_demographic={})
    db.add(simulation)
    db.flush()
    return simulation


def _is_render(path):
    from app.services.storage_service import get_path

    with Image.open(get_path(path)) as img:
        r, g, b = np.asarray(img.convert("RGB"), dtype=np.float32).reshape(-1, 3).mean(axis=0)
    # JPEG-compressed solid render colour (10, 200, 10)
    return g > 150 and r < 60 and b < 60


def test_hybrid_produces_n_rendered_variants(db_session, fake_gan_generator, fake_image_provider):
    from app.services import gan_service

    simulation = _make_product_simulation(db_session)
    variants = gan_service.generate_variants_for_simulation(db_session, simulation.id, 3)

    assert len(variants) == 3
    assert len(fake_image_provider.calls) == 3
    for i, variant in enumerate(variants):
        assert variant.generation_method == hybrid.HYBRID_METHOD
        assert _is_render(variant.image_path)
        # Keys the optimiser and persona prompt read must survive the hybrid path.
        for key in ("anchor_seed", "perturbation_radius", "color_hue_shift_degrees", "perturbation_index"):
            assert key in variant.attributes
        assert variant.attributes["perturbation_index"] == i
        assert variant.attributes["seed_image_path"]
        assert not _is_render(variant.attributes["seed_image_path"])
        assert variant.fid_score is not None


def test_prompt_carries_product_identity_and_reference_image(db_session, fake_gan_generator, fake_image_provider):
    from app.services import gan_service

    simulation = _make_product_simulation(db_session)
    gan_service.generate_variants_for_simulation(db_session, simulation.id, 2)

    for call in fake_image_provider.calls:
        assert "Trail Runner" in call["prompt"]
        # Brand names get drawn as fake lettering by image models.
        assert "Acme" not in call["prompt"]
        assert "Lightweight running shoe" in call["prompt"]
        assert "colourway" in call["prompt"]
        assert call["reference_image"] is not None
        assert call["strength"] == settings.DIFFUSION_STRENGTH


def test_product_init_does_not_send_the_photo_twice(db_session, fake_gan_generator, fake_image_provider, monkeypatch):
    from app.services import gan_service

    monkeypatch.setattr(settings, "DIFFUSION_INIT", "product")
    simulation = _make_product_simulation(db_session)
    gan_service.generate_variants_for_simulation(db_session, simulation.id, 2)
    assert all(call["reference_image"] is None for call in fake_image_provider.calls)


def test_failed_render_falls_back_to_gan_without_aborting(db_session, fake_gan_generator, fake_image_provider):
    from app.services import gan_service

    fake_image_provider.fail_on_calls = {2}
    simulation = _make_product_simulation(db_session)
    variants = gan_service.generate_variants_for_simulation(db_session, simulation.id, 3)

    methods = [v.generation_method for v in variants]
    assert methods == [hybrid.HYBRID_METHOD, hybrid.GAN_FALLBACK_METHOD, hybrid.HYBRID_METHOD]
    failed = variants[1]
    assert "simulated API failure" in failed.attributes["render_error"]
    assert not _is_render(failed.image_path)
    assert "seed_image_path" not in failed.attributes


def test_api_budget_is_enforced_across_rounds(db_session, fake_gan_generator, fake_image_provider, monkeypatch):
    from app.services import gan_service

    monkeypatch.setattr(settings, "MAX_API_IMAGES_PER_SIMULATION", 4)
    simulation = _make_product_simulation(db_session)
    first = gan_service.generate_variants_for_simulation(db_session, simulation.id, 3)
    second = gan_service.generate_variants_for_simulation(db_session, simulation.id, 3)

    assert len(fake_image_provider.calls) == 4
    assert [v.generation_method for v in first] == [hybrid.HYBRID_METHOD] * 3
    assert [v.generation_method for v in second] == [hybrid.HYBRID_METHOD] + [hybrid.GAN_FALLBACK_METHOD] * 2
    assert second[1].attributes["render_skipped"]


def test_gan_backend_is_default_and_untouched(db_session, fake_gan_generator):
    from app.services import gan_service

    assert settings.GENERATOR_BACKEND == "gan"
    simulation = _make_product_simulation(db_session)
    variants = gan_service.generate_variants_for_simulation(db_session, simulation.id, 2)
    assert all(v.generation_method == "gan_latent_variation" for v in variants)
    assert all("seed_image_path" not in v.attributes for v in variants)


def test_hybrid_without_provider_fails_loudly(monkeypatch):
    monkeypatch.setattr(settings, "IMAGE_PROVIDER", None)
    with pytest.raises(ImageConfigurationError, match="IMAGE_PROVIDER is not set"):
        get_image_provider()
    monkeypatch.setattr(settings, "IMAGE_PROVIDER", "nonexistent")
    with pytest.raises(ImageConfigurationError, match="Unknown IMAGE_PROVIDER"):
        get_image_provider()


def test_seed_selection_is_deterministic_and_prefers_matching_silhouette():
    product = Image.new("RGB", (64, 64), (255, 255, 255))
    product.paste((0, 0, 0), (16, 24, 48, 40))  # dark shoe-like band on white

    def candidate(i, box):
        img = Image.new("RGB", (64, 64), (255, 255, 255))
        if box:
            img.paste((0, 0, 0), box)
        return VariantResult(image=img, attributes={"perturbation_index": i})

    candidates = [
        candidate(0, (0, 0, 64, 64)),     # malformed: all black
        candidate(1, (16, 24, 48, 40)),   # matches the product
        candidate(2, None),               # blank
        candidate(3, (14, 22, 50, 42)),   # close to the product
    ]
    picked = hybrid.select_seeds(candidates, product, 2)
    assert picked[0].attributes["perturbation_index"] == 1
    assert 0 not in [p.attributes["perturbation_index"] for p in picked]
    assert [p.attributes["perturbation_index"] for p in hybrid.select_seeds(candidates, product, 2)] == \
           [p.attributes["perturbation_index"] for p in picked]


def test_colour_phrase_wraps_and_handles_missing():
    assert hybrid.colour_phrase(None) == "the original colourway"
    assert hybrid.colour_phrase(355) == "the original colourway"
    assert "blue" in hybrid.colour_phrase(245)
