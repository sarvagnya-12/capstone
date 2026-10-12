"""ESRGAN upscaler: architecture contracts, data pipeline, inference wrapper,
and the gan_service hook. Uses tiny random-weight networks -- these prove
shapes and wiring, not upscaling quality (that is what train_esrgan.py's
validation metrics and sample grids are for)."""

import random

import pytest
import torch
from PIL import Image

from app.core.config import settings
from app.ml.sr.arch import RRDBNet, UNetDiscriminatorSN
from app.ml.sr.data import SRTrainDataset, degrade, is_validation_file, list_images, load_validation_pairs
from app.ml.sr.upscale import UpscalerConfigurationError, load_upscaler, upscale


def _tiny_generator():
    return RRDBNet(scale=2, num_feat=8, num_block=1, num_grow_ch=4).eval()


def test_generator_doubles_resolution():
    out = _tiny_generator()(torch.rand(2, 3, 32, 48))
    assert out.shape == (2, 3, 64, 96)


def test_discriminator_gives_per_pixel_logits():
    out = UNetDiscriminatorSN(num_feat=8)(torch.rand(2, 3, 64, 64))
    assert out.shape == (2, 1, 64, 64)


def test_rejects_unsupported_scale():
    with pytest.raises(ValueError):
        RRDBNet(scale=3)


def test_degrade_produces_half_size_for_every_branch():
    hr = Image.new("RGB", (128, 128), (120, 60, 30))
    for seed in range(30):  # exercises clean, blur, noise and JPEG branches
        assert degrade(hr, 2, random.Random(seed)).size == (64, 64)


def _write_images(folder, count, size):
    folder.mkdir()
    for i in range(count):
        img = Image.effect_noise((size, size), 64).convert("RGB")
        img.save(folder / f"img_{i:04d}.jpg")


def test_train_val_split_is_disjoint_and_stable(tmp_path):
    _write_images(tmp_path / "a", 300, 16)
    train, val = list_images([tmp_path / "a"], "train"), list_images([tmp_path / "a"], "val")
    assert not set(train) & set(val)
    assert len(train) + len(val) == 300
    assert all(is_validation_file(p) for p in val)
    assert val == list_images([tmp_path / "a"], "val")


def test_dataset_yields_matching_pairs_from_several_folders(tmp_path):
    _write_images(tmp_path / "big", 20, 512)
    _write_images(tmp_path / "small", 20, 256)
    dataset = SRTrainDataset([tmp_path / "big", tmp_path / "small"], patch_size=128, scale=2)
    for i in (0, len(dataset) - 1):
        lr, hr = dataset[i]
        assert lr.shape == (3, 64, 64) and hr.shape == (3, 128, 128)
        assert 0.0 <= float(lr.min()) and float(lr.max()) <= 1.0


def test_dataset_rejects_patch_size_the_discriminator_cannot_take(tmp_path):
    _write_images(tmp_path / "a", 5, 64)
    with pytest.raises(ValueError):
        SRTrainDataset([tmp_path / "a"], patch_size=100, scale=2)


def test_validation_pairs_are_fixed_size(tmp_path):
    _write_images(tmp_path / "a", 400, 300)
    pairs = load_validation_pairs([tmp_path / "a"], scale=2, count=3, size=256)
    assert pairs
    for lr, hr in pairs:
        assert hr.shape == (3, 256, 256) and lr.shape == (3, 128, 128)


def test_upscale_handles_odd_sizes():
    out = upscale(Image.new("RGB", (37, 21), (10, 20, 30)), model=_tiny_generator())
    assert out.size == (74, 42) and out.mode == "RGB"


def test_checkpoint_round_trip(tmp_path):
    net = _tiny_generator()
    path = tmp_path / "net.pt"
    torch.save({"arch_config": {"scale": 2, "num_feat": 8, "num_block": 1, "num_grow_ch": 4},
                "state_dict": net.state_dict(), "step": 1}, path)
    loaded = load_upscaler(path).cpu()
    x = torch.rand(1, 3, 16, 16)
    assert torch.allclose(loaded(x), net(x))


def test_missing_checkpoint_fails_with_actionable_message(tmp_path):
    with pytest.raises(UpscalerConfigurationError, match="SR_CHECKPOINT"):
        load_upscaler(tmp_path / "nope.pt")


def _enable_tiny_sr(monkeypatch):
    tiny = _tiny_generator()
    calls = []

    def fake_upscale(img):
        calls.append(img.size)
        return upscale(img, model=tiny)

    monkeypatch.setattr(settings, "SR_ENABLED", True)
    monkeypatch.setattr("app.services.gan_service.upscale", fake_upscale)
    return calls


def test_large_outputs_are_not_upscaled_again(db_session, fake_gan_generator, monkeypatch):
    from tests.test_hybrid_generation import _make_product_simulation
    from app.services import gan_service

    calls = _enable_tiny_sr(monkeypatch)
    monkeypatch.setattr(settings, "SR_TARGET_SIZE", 256)  # GAN output is 256 -> already at target
    simulation = _make_product_simulation(db_session)
    variants = gan_service.generate_variants_for_simulation(db_session, simulation.id, 2)
    assert calls == []
    assert all("upscaled" not in v.attributes for v in variants)


def test_hybrid_upscales_seed_before_diffusion_and_small_render_after(
        db_session, fake_gan_generator, fake_image_provider, monkeypatch):
    from tests.test_hybrid_generation import _make_product_simulation
    from app.services import gan_service
    from app.services.storage_service import get_path

    calls = _enable_tiny_sr(monkeypatch)
    simulation = _make_product_simulation(db_session)
    variants = gan_service.generate_variants_for_simulation(db_session, simulation.id, 2)

    # Diffusion received the upscaled 512px concept, not the raw 256px one.
    assert all(call["init_image"].size == (512, 512) for call in fake_image_provider.calls)
    for variant in variants:
        assert variant.attributes["seed_upscaled"] is True
        # The fake API returns the init size (512); below SR_TARGET_SIZE, so upscaled once more.
        assert variant.attributes["upscaled"] == "esrgan_2x"
        with Image.open(get_path(variant.image_path)) as img:
            assert img.size == (1024, 1024)
    # 2 seed upscales + 2 output upscales.
    assert calls == [(256, 256), (256, 256), (512, 512), (512, 512)]


def test_seed_upscale_can_be_turned_off(db_session, fake_gan_generator, fake_image_provider, monkeypatch):
    from tests.test_hybrid_generation import _make_product_simulation
    from app.services import gan_service

    _enable_tiny_sr(monkeypatch)
    monkeypatch.setattr(settings, "SR_UPSCALE_SEED", False)
    simulation = _make_product_simulation(db_session)
    variants = gan_service.generate_variants_for_simulation(db_session, simulation.id, 1)
    assert fake_image_provider.calls[0]["init_image"].size == (256, 256)
    assert "seed_upscaled" not in variants[0].attributes


def test_failed_seed_upscale_still_renders(db_session, fake_gan_generator, fake_image_provider, monkeypatch):
    from tests.test_hybrid_generation import _make_product_simulation
    from app.ml.diffusion import hybrid
    from app.services import gan_service

    monkeypatch.setattr(settings, "SR_ENABLED", True)

    def broken(img):
        raise RuntimeError("upscaler exploded")

    monkeypatch.setattr("app.services.gan_service.upscale", broken)
    monkeypatch.setattr(settings, "SR_TARGET_SIZE", 1)  # keep the output stage out of this test
    simulation = _make_product_simulation(db_session)
    variants = gan_service.generate_variants_for_simulation(db_session, simulation.id, 1)
    assert variants[0].generation_method == hybrid.HYBRID_METHOD
    assert fake_image_provider.calls[0]["init_image"].size == (256, 256)


def test_gan_service_upscales_variants_when_enabled(db_session, fake_gan_generator, monkeypatch):
    from tests.test_hybrid_generation import _make_product_simulation
    from app.services import gan_service
    from app.services.storage_service import get_path

    tiny = _tiny_generator()
    monkeypatch.setattr(settings, "SR_ENABLED", True)
    monkeypatch.setattr("app.services.gan_service.upscale", lambda img: upscale(img, model=tiny))

    simulation = _make_product_simulation(db_session)
    variants = gan_service.generate_variants_for_simulation(db_session, simulation.id, 2)

    for variant in variants:
        assert variant.attributes["upscaled"] == "esrgan_2x"
        with Image.open(get_path(variant.image_path)) as img:
            assert img.size == (512, 512)
        assert variant.fid_score is not None  # FID still works on the larger images
