"""Inference for the trained ESRGAN upscaler (train_esrgan.py).

`upscale(image)` takes any RGB PIL image and returns it `scale`x larger. Used
after variant generation when settings.SR_ENABLED is on; the model loads
lazily on first use and runs on the GPU when there is one, the CPU otherwise.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import torch
import torch.nn.functional as F
from PIL import Image

from app.ml.sr.arch import RRDBNet
from app.ml.sr.data import to_image, to_tensor

_model_cache: Optional[RRDBNet] = None


class UpscalerConfigurationError(Exception):
    pass


def load_upscaler(checkpoint: str | Path) -> RRDBNet:
    path = Path(checkpoint)
    if not path.exists():
        raise UpscalerConfigurationError(
            f"SR_ENABLED is on but no upscaler checkpoint exists at {path}. Train one with "
            "`python -m app.ml.sr.train_esrgan`, point SR_CHECKPOINT at a net_g_ema_*.pt file, "
            "or set SR_ENABLED=false."
        )
    state = torch.load(path, map_location="cpu", weights_only=True)
    model = RRDBNet(**state["arch_config"])
    model.load_state_dict(state["state_dict"])
    model.eval()
    if torch.cuda.is_available():
        model = model.cuda()
    return model


def _get_upscaler() -> RRDBNet:
    global _model_cache
    if _model_cache is None:
        from app.core.config import settings

        _model_cache = load_upscaler(settings.SR_CHECKPOINT)
    return _model_cache


@torch.no_grad()
def upscale(image: Image.Image, model: Optional[RRDBNet] = None) -> Image.Image:
    model = model or _get_upscaler()
    device = next(model.parameters()).device
    x = to_tensor(image.convert("RGB")).unsqueeze(0).to(device)
    h, w = x.shape[-2:]
    # The 2x model pixel-unshuffles its input, so odd sizes are padded
    # (reflect, not zero, to avoid a dark edge) and the padding cropped back off.
    pad_h, pad_w = h % 2, w % 2
    if pad_h or pad_w:
        x = F.pad(x, (0, pad_w, 0, pad_h), mode="reflect")
    with torch.autocast("cuda", dtype=torch.bfloat16, enabled=device.type == "cuda"):
        out = model(x)
    out = out.float()[..., : h * model.scale, : w * model.scale]
    return to_image(out[0])
