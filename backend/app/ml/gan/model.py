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

DEFAULT_CHECKPOINT_PATH = Path(__file__).resolve().parents[3] / "storage" / "models" / "afhqcat.pkl"


def load_generator(checkpoint_path: Path = DEFAULT_CHECKPOINT_PATH, device: Optional[str] = None) -> torch.nn.Module:
    """Loads the pretrained StyleGAN2-ADA generator (G_ema) from a .pkl checkpoint."""
    device = device or ("cuda" if torch.cuda.is_available() else "cpu")
    with open(checkpoint_path, "rb") as f:
        data = legacy.load_network_pkl(f)
    generator = data["G_ema"].to(device)
    generator.eval()
    return generator


def generate_image(generator: torch.nn.Module, seed: int, truncation_psi: float = 0.7) -> torch.Tensor:
    """Runs one forward pass from a seeded random latent vector, returning a
    (3, *TARGET_SIZE) float tensor in [0, 1]."""
    device = next(generator.parameters()).device
    z = torch.from_numpy(np.random.RandomState(seed).randn(1, generator.z_dim).astype("float32")).to(device)
    label = torch.zeros([1, generator.c_dim], device=device)

    with torch.no_grad(), _suppress_plugin_setup_noise():
        img = generator(z, label, truncation_psi=truncation_psi, noise_mode="const")
        img = ((img + 1) / 2).clamp(0, 1)  # [-1, 1] -> [0, 1]
        if img.shape[-2:] != TARGET_SIZE:
            img = F.interpolate(img, size=TARGET_SIZE, mode="bilinear", align_corners=False)

    return img[0].cpu()
