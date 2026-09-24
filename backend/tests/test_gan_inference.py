"""Step 15/16: pretrained GAN integration and latent-space attribute
variation. Uses the fake_gan_generator fixture (tiny random-weight network)
rather than the real 364MB checkpoint -- verifies pipeline mechanics
(count/shape/persistence/reproducibility), not real image quality, per this
step's own guidance."""

import pytest
import torch
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


# --- FastGAN adapter (Step 17) -------------------------------------------
#
# These cover the contract inference.py depends on, and specifically the two
# conventions that differ from StyleGAN2 and silently corrupt output if got
# wrong. Both were real bugs during integration, not hypotheticals.


class _StubFastGANInner(torch.nn.Module):
    """Stands in for lightweight_gan's generator: takes z only (no label /
    truncation_psi / noise_mode) and emits values outside [0, 1]."""

    def __init__(self, image_size: int = 256):
        super().__init__()
        self.image_size = image_size
        self.linear = torch.nn.Linear(8, 3 * image_size * image_size)

    def forward(self, z: torch.Tensor) -> torch.Tensor:
        out = self.linear(z).view(-1, 3, self.image_size, self.image_size)
        # Deliberately out of range in both directions, matching the real
        # generator (measured [-2.40, 1.95] on the trained checkpoint).
        return out * 4.0 - 1.5


def _stub_fastgan():
    from app.ml.gan.fastgan import FastGANGenerator

    return FastGANGenerator(_StubFastGANInner(), latent_dim=8, image_size=256)


def test_fastgan_adapter_exposes_the_surface_inference_needs():
    from app.services.image_preprocessing import TARGET_SIZE

    generator = _stub_fastgan()
    # inference.py reads .z_dim to size its latents; without this the whole
    # Step 16 variation path breaks.
    assert generator.z_dim == 8
    assert generator.img_resolution == 256

    from app.ml.gan.fastgan import generate_image_from_latent

    img = generate_image_from_latent(generator, torch.randn(1, 8))
    assert img.shape == (3, *TARGET_SIZE)
    assert 0.0 <= float(img.min()) and float(img.max()) <= 1.0


def test_fastgan_adapter_clamps_rather_than_rescaling():
    """The clamp is load-bearing, not tidying.

    StyleGAN2 emits [-1, 1] and model.py rescales with (img + 1) / 2. FastGAN
    is unbounded and the package clamps instead, so applying that rescale here
    would brighten every pixel.

    This asserts on an exact mid-range value rather than on min/max: a first
    version of this test checked only that the output spanned [0, 1], which a
    mutation test showed passes with the rescale bug injected, since a wide
    output range saturates both ends either way. 0.5 is the discriminating
    probe -- it survives a clamp untouched but becomes 0.75 under the rescale.
    """
    from app.ml.gan.fastgan import FastGANGenerator, generate_image_from_latent

    class _ConstantInner(torch.nn.Module):
        def __init__(self):
            super().__init__()
            # Needs at least one parameter: the adapter locates its device via
            # next(generator.parameters()), which every real generator has.
            self.unused = torch.nn.Parameter(torch.zeros(1))

        def forward(self, z):
            return torch.full((1, 3, 256, 256), 0.5, device=self.unused.device)

    generator = FastGANGenerator(_ConstantInner(), latent_dim=8, image_size=256)
    img = generate_image_from_latent(generator, torch.randn(1, 8))

    assert float(img.mean()) == pytest.approx(0.5, abs=1e-4), (
        f"expected 0.5 to pass through a clamp unchanged, got {float(img.mean()):.4f} "
        "-- 0.75 means StyleGAN2's (img + 1) / 2 rescale is being applied to FastGAN output"
    )


def test_model_dispatches_fastgan_without_stylegan_rescale(monkeypatch):
    """model.generate_image_from_latent must route FastGAN generators to the
    FastGAN path; sending them through the StyleGAN2 branch would both apply
    the wrong rescale and pass a `label` argument the generator won't accept."""
    from app.ml.gan import model as model_module

    generator = _stub_fastgan()
    z = torch.randn(1, 8)
    via_model = model_module.generate_image_from_latent(generator, z)

    from app.ml.gan.fastgan import generate_image_from_latent as direct

    assert torch.allclose(via_model, direct(generator, z))


def test_fastgan_forward_accepts_cpu_latent_for_any_device():
    """inference.py builds latents on CPU via numpy. The adapter must move
    them itself -- calling the generator directly used to raise a CPU/CUDA
    type mismatch."""
    generator = _stub_fastgan()
    out = generator(torch.randn(1, 8))  # no explicit .to(device)
    assert out.shape[0] == 1


def test_resolve_checkpoint_errors_clearly_when_untrained(tmp_path):
    from app.ml.gan.fastgan import resolve_checkpoint

    with pytest.raises(FileNotFoundError, match="train_fastgan"):
        resolve_checkpoint(None, models_dir=tmp_path)
