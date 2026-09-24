"""Loads the FastGAN generator trained by train_fastgan.py (Step 17).

This exists to make a second generator architecture usable without touching
anything downstream. inference.py (Step 16's latent-space variation) and
gan_service.py only ever need two things from a generator:

    generator.z_dim                      -- latent width, to sample z
    generate_image_from_latent(g, z)     -- (3, 256, 256) float RGB in [0, 1]

FastGANGenerator below satisfies exactly that, so variant generation, FID
scoring, persona simulation and orchestration all keep working unchanged
against a completely different architecture.

Two interface mismatches are absorbed here rather than leaked upward:
  - StyleGAN2 is called as G(z, label, truncation_psi=..., noise_mode=...);
    FastGAN's generator takes only z. `truncation_psi` is therefore accepted
    and ignored, since FastGAN has no w-space to truncate toward a mean.
  - StyleGAN2 emits [-1, 1] and model.py rescales with (img + 1) / 2. FastGAN
    does NOT: its generator output is unbounded (measured [-2.40, 1.95] on the
    trained checkpoint), and the package itself simply clamps to [0, 1]
    (`generate_` does `clamp_(0., 1.)`). So the clamp below is load-bearing,
    not defensive tidying, and applying StyleGAN2's rescale on top of it would
    wash every image out.

The trained weights live under storage/fastgan/models/<run>/model_<n>.pt and
are checkpoints from the `lightweight-gan` package, not NVIDIA pickles, so
they are loaded with torch.load rather than legacy.load_network_pkl.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import torch
import torch.nn.functional as F

from app.services.image_preprocessing import TARGET_SIZE

BACKEND_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_FASTGAN_DIR = BACKEND_ROOT / "storage" / "fastgan" / "models" / "shoes"


class FastGANGenerator(torch.nn.Module):
    """Adapter presenting a FastGAN generator through the same surface the
    StyleGAN2 path exposes."""

    def __init__(self, generator: torch.nn.Module, latent_dim: int, image_size: int) -> None:
        super().__init__()
        self.generator = generator
        # Named z_dim, not latent_dim, because that is what inference.py reads.
        self.z_dim = latent_dim
        self.c_dim = 0  # no class conditioning; kept so callers can pass labels
        self.img_resolution = image_size

    def forward(self, z: torch.Tensor, label: Optional[torch.Tensor] = None,
                truncation_psi: float = 1.0, noise_mode: str = "const") -> torch.Tensor:
        # label / truncation_psi / noise_mode are StyleGAN2 concepts with no
        # FastGAN equivalent. Accepted for signature compatibility, unused.
        #
        # z is moved here rather than only in generate_image_from_latent, so
        # calling the generator directly -- which the StyleGAN2 path permits --
        # does not fail with a CPU/CUDA type mismatch.
        return self.generator(z.to(next(self.generator.parameters()).device))


def resolve_checkpoint(checkpoint: Optional[Path] = None, models_dir: Path = DEFAULT_FASTGAN_DIR) -> Path:
    """An explicit path wins; otherwise pick the highest-numbered checkpoint.

    Note the caller usually wants the *best* checkpoint, not the last one --
    training is not monotonic (this run's FID bottomed at step 14,000 and rose
    again by 18,000), so the run's fid_scores.txt should decide which number
    to pass in.
    """
    if checkpoint is not None:
        if not checkpoint.exists():
            raise FileNotFoundError(f"FastGAN checkpoint not found: {checkpoint}")
        return checkpoint

    candidates = sorted(
        models_dir.glob("model_*.pt"),
        key=lambda p: int(p.stem.split("_")[1]),
    )
    if not candidates:
        raise FileNotFoundError(
            f"No FastGAN checkpoints in {models_dir}. Train one first:\n"
            "  python -m app.ml.gan.train_fastgan --images-dir <dir>"
        )
    return candidates[-1]


def load_fastgan_generator(
    checkpoint: Optional[Path] = None,
    models_dir: Path = DEFAULT_FASTGAN_DIR,
    device: Optional[str] = None,
    use_ema: bool = True,
) -> FastGANGenerator:
    """Load a trained FastGAN generator ready for inference.

    use_ema selects the exponential-moving-average generator (`GE`), which is
    what the package itself samples from for its own output grids and is
    normally smoother than the raw `G`.
    """
    from lightweight_gan.lightweight_gan import Trainer

    device = device or ("cuda" if torch.cuda.is_available() else "cpu")
    checkpoint_path = resolve_checkpoint(checkpoint, models_dir)

    config_path = checkpoint_path.parent / ".config.json"
    if not config_path.exists():
        raise FileNotFoundError(
            f"Missing {config_path}; it records image_size/attn_res_layers and the "
            "model cannot be rebuilt without matching them exactly."
        )
    config = json.loads(config_path.read_text(encoding="utf-8"))

    # Load through the package's own Trainer rather than constructing
    # LightweightGAN and calling load_state_dict directly.
    #
    # Hand-construction looks like it works and does not: every key name
    # matches, load_state_dict raises nothing, and the model then generates
    # blue blobs on a tan field instead of shoes. The Trainer builds the
    # network from its stored config with several parameters beyond those in
    # .config.json, so a hand-built model is subtly a different architecture
    # wearing the same state-dict key names. Verified both ways side by side.
    checkpoint_num = int(checkpoint_path.stem.split("_")[1])
    trainer = Trainer(
        name=checkpoint_path.parent.name,
        base_dir=str(checkpoint_path.parents[2]),
        results_dir="results",
        models_dir="models",
        image_size=config["image_size"],
        use_aim=False,
    )
    trainer.load(checkpoint_num, print_version=False)
    model = trainer.GAN.eval()

    generator = (model.GE if use_ema else model.G).to(device).eval()
    for param in generator.parameters():
        param.requires_grad_(False)

    return FastGANGenerator(generator, latent_dim=256, image_size=config["image_size"]).to(device).eval()


@torch.no_grad()
def generate_image_from_latent(generator: FastGANGenerator, z: torch.Tensor,
                               truncation_psi: float = 0.7) -> torch.Tensor:
    """(3, TARGET_SIZE) float RGB in [0, 1] -- same contract as model.py's."""
    device = next(generator.parameters()).device
    img = generator(z.to(device))
    # Load-bearing: raw output genuinely exceeds [0, 1] in both directions.
    # This mirrors the package's own generate_(), which clamps identically.
    img = img.clamp(0, 1)
    if img.shape[-2:] != TARGET_SIZE:
        img = F.interpolate(img, size=TARGET_SIZE, mode="bilinear", align_corners=False)
    return img[0].cpu()
