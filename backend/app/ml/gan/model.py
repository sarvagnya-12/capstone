"""Loads a pretrained StyleGAN2-ADA generator (NVIDIA's official PyTorch
implementation, vendored under vendor/stylegan2_ada/ -- the repo isn't a pip
package, so the minimal inference-only subset (dnnlib/, torch_utils/,
legacy.py) is vendored directly rather than pip-installed) and wraps it for
inference.

Checkpoint: AFHQ-cat, 512x512, from NVIDIA's official pretrained model zoo
(https://nvlabs-fi-cdn.nvidia.com/stylegan2-ada-pytorch/pretrained/afhqcat.pkl),
stored at backend/storage/models/afhqcat.pkl (gitignored, per Step 1).

License: NVIDIA Source Code License -- non-commercial research/evaluation use
only (see vendor/stylegan2_ada/LICENSE.txt). Appropriate for this academic
capstone; would need revisiting before any commercial use.

No CUDA/MSVC compiler toolchain is available on the target dev machine, so
the vendored custom ops (bias_act, upfirdn2d) fall back to their pure-PyTorch
reference implementations automatically (NVIDIA's own code catches the
compilation failure and warns, rather than erroring) -- slower, not broken.

Native output resolution is 512x512; generate_image() resizes to
image_preprocessing.TARGET_SIZE (256x256, fixed in Step 12) so GAN output
matches the rest of the pipeline. Domain (cats) does not match the
footwear/product vertical -- proving the pretrained-checkpoint inference path
works end-to-end is this step's actual goal; domain-appropriate output is
Step 17's fine-tuning job, deferred per project decision.
"""

import contextlib
import io
import sys
import warnings
from pathlib import Path
from typing import Optional

import numpy as np
import torch
import torch.nn.functional as F

from app.core.config import settings
from app.services.image_preprocessing import TARGET_SIZE

_VENDOR_ROOT = Path(__file__).resolve().parent / "vendor" / "stylegan2_ada"
if str(_VENDOR_ROOT) not in sys.path:
    sys.path.insert(0, str(_VENDOR_ROOT))

# Expected and harmless on this machine (no MSVC/nvcc) -- see module docstring.
# Without this filter, every generate_image() call reprints the same multi-line
# warning per custom op (bias_act/upfirdn2d) since NVIDIA's plugin cache doesn't
# persist the "compilation failed" result across call sites.
warnings.filterwarnings("ignore", message="Failed to build CUDA kernels")

import legacy  # noqa: E402  (vendored NVIDIA module, see vendor/stylegan2_ada/)


@contextlib.contextmanager
def _suppress_plugin_setup_noise():
    """NVIDIA's custom_ops.get_plugin() prints "Setting up PyTorch plugin ...
    Failed!" via plain print() (not logging/warnings) every time compilation is
    attempted -- harmless (see module docstring) but noisy across repeated
    generate_image() calls. Captures stdout only for the duration of the call;
    real exceptions still propagate normally."""
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        yield

# The StyleGAN2 checkpoint, still referenced by finetune.py's transfer-learning
# path. It is no longer what the application generates from -- see
# settings.GAN_CHECKPOINT.
STYLEGAN2_CHECKPOINT_PATH = Path(__file__).resolve().parents[3] / "storage" / "models" / "afhqcat.pkl"
DEFAULT_CHECKPOINT_PATH = Path(settings.GAN_CHECKPOINT)


def load_generator(checkpoint_path: Path = DEFAULT_CHECKPOINT_PATH, device: Optional[str] = None) -> torch.nn.Module:
    """Loads a generator, dispatching on checkpoint format.

    `.pt` -> FastGAN trained from scratch on real product photos (Step 17's
    working approach; see app/ml/gan/train_fastgan.py).
    `.pkl` -> StyleGAN2-ADA, the original transfer-learning path. Kept working
    and selectable so the earlier approach stays reproducible, even though
    every attempt to fine-tune it ended worse than its own starting point.

    Both return an object exposing `.z_dim` and producing a
    (3, TARGET_SIZE) [0, 1] image via generate_image_from_latent().
    """
    device = device or ("cuda" if torch.cuda.is_available() else "cpu")

    if Path(checkpoint_path).suffix == ".pt":
        from app.ml.gan.fastgan import load_fastgan_generator

        return load_fastgan_generator(checkpoint=Path(checkpoint_path), device=device)

    with open(checkpoint_path, "rb") as f:
        data = legacy.load_network_pkl(f)
    generator = data["G_ema"].to(device)
    generator.eval()
    return generator


def random_latent(seed: int, z_dim: int) -> torch.Tensor:
    """Deterministic random latent vector for a given seed, shape (1, z_dim)."""
    return torch.from_numpy(np.random.RandomState(seed).randn(1, z_dim).astype("float32"))


def generate_image_from_latent(generator: torch.nn.Module, z: torch.Tensor, truncation_psi: float = 0.7) -> torch.Tensor:
    """Runs one forward pass from an explicit latent vector z (shape (1, z_dim)),
    returning a (3, *TARGET_SIZE) float tensor in [0, 1]. Lower-level than
    generate_image() -- used directly when nearby latent-space perturbations
    around a shared anchor are needed (Step 16), not just an independent
    random draw per seed.

    Dispatches on generator type because the output conventions differ: the
    StyleGAN2 rescale below ([-1, 1] -> [0, 1]) applied to FastGAN's output
    would halve its contrast and wash every image out."""
    from app.ml.gan.fastgan import FastGANGenerator, generate_image_from_latent as fastgan_generate

    if isinstance(generator, FastGANGenerator):
        return fastgan_generate(generator, z, truncation_psi=truncation_psi)

    device = next(generator.parameters()).device
    z = z.to(device)
    label = torch.zeros([1, generator.c_dim], device=device)

    with torch.no_grad(), _suppress_plugin_setup_noise():
        img = generator(z, label, truncation_psi=truncation_psi, noise_mode="const")
        img = ((img + 1) / 2).clamp(0, 1)  # [-1, 1] -> [0, 1]
        if img.shape[-2:] != TARGET_SIZE:
            img = F.interpolate(img, size=TARGET_SIZE, mode="bilinear", align_corners=False)

    return img[0].cpu()


def generate_image(generator: torch.nn.Module, seed: int, truncation_psi: float = 0.7) -> torch.Tensor:
    """Runs one forward pass from a seeded random latent vector, returning a
    (3, *TARGET_SIZE) float tensor in [0, 1]."""
    z = random_latent(seed, generator.z_dim)
    return generate_image_from_latent(generator, z, truncation_psi=truncation_psi)
