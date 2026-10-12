"""Training data for the ESRGAN upscaler: (low-res, high-res) pairs made on the fly.

Only high-resolution images are stored; each low-res input is synthesised
from its high-res crop. A clean bicubic downscale alone would teach the model
to invert exactly one blur kernel -- and the images it will actually receive
(GAN output, API renders) are softer and carry compression artefacts. So,
following Real-ESRGAN's degradation idea in a simplified single-pass form,
most samples get a random mix of blur, downscale filter, noise and JPEG.

Train/validation split is a pure function of the filename (CRC32), so the
validation images are the same on every run and on resume, and can never
leak into training when more folders are added later.
"""

from __future__ import annotations

import io
import random
import zlib
from pathlib import Path

import numpy as np
import torch
from PIL import Image, ImageFilter
from torch.utils.data import Dataset

_EXTENSIONS = {".jpg", ".jpeg", ".png"}
# 1 in VAL_MODULUS files (by filename hash) is held out for validation.
VAL_MODULUS = 100
# A crop this flat is almost certainly white background padding -- nothing to learn from.
_MIN_PATCH_STD = 0.02
_DOWNSCALE_FILTERS = (Image.BICUBIC, Image.BILINEAR, Image.BOX)


def is_validation_file(path: Path) -> bool:
    return zlib.crc32(path.name.encode()) % VAL_MODULUS == 0


def list_images(dirs: list[Path], split: str) -> list[Path]:
    files = sorted(p for d in dirs for p in Path(d).iterdir() if p.suffix.lower() in _EXTENSIONS)
    want_val = split == "val"
    return [p for p in files if is_validation_file(p) == want_val]


def to_tensor(img: Image.Image) -> torch.Tensor:
    return torch.from_numpy(np.asarray(img, dtype=np.float32) / 255.0).permute(2, 0, 1)


def to_image(t: torch.Tensor) -> Image.Image:
    array = (t.detach().float().clamp(0, 1).permute(1, 2, 0).cpu().numpy() * 255.0).round().astype(np.uint8)
    return Image.fromarray(array, mode="RGB")


def degrade(hr: Image.Image, scale: int, rng: random.Random, clean_prob: float = 0.2) -> Image.Image:
    """Synthesise the low-res input for one high-res crop."""
    lr_size = (hr.width // scale, hr.height // scale)
    if rng.random() < clean_prob:
        return hr.resize(lr_size, Image.BICUBIC)

    img = hr
    if rng.random() < 0.7:
        img = img.filter(ImageFilter.GaussianBlur(radius=rng.uniform(0.2, 1.5)))
    img = img.resize(lr_size, rng.choice(_DOWNSCALE_FILTERS))

    if rng.random() < 0.5:
        sigma = rng.uniform(1.0, 10.0) / 255.0
        array = np.asarray(img, dtype=np.float32) / 255.0
        noise_rng = np.random.default_rng(rng.getrandbits(32))
        if rng.random() < 0.4:  # luminance-only noise, as from a sensor
            noise = noise_rng.normal(0.0, sigma, array.shape[:2])[..., None]
        else:
            noise = noise_rng.normal(0.0, sigma, array.shape)
        img = Image.fromarray((np.clip(array + noise, 0, 1) * 255).round().astype(np.uint8), mode="RGB")

    if rng.random() < 0.7:
        buffer = io.BytesIO()
        img.save(buffer, format="JPEG", quality=rng.randint(50, 95))
        buffer.seek(0)
        img = Image.open(buffer).convert("RGB")
    return img


class SRTrainDataset(Dataset):
    def __init__(self, dirs: list[Path], patch_size: int = 128, scale: int = 2, seed: int = 0) -> None:
        if patch_size % (scale * 8):
            # The U-Net discriminator needs HR sizes divisible by 8, the 2x
            # generator needs even LR sizes.
            raise ValueError(f"patch_size must be a multiple of {scale * 8}")
        self.files = list_images(dirs, "train")
        if not self.files:
            raise ValueError(f"no training images found in {dirs}")
        self.patch_size = patch_size
        self.scale = scale
        self.seed = seed

    def __len__(self) -> int:
        return len(self.files)

    def __getitem__(self, index: int) -> tuple[torch.Tensor, torch.Tensor]:
        rng = random.Random()  # fresh entropy per sample; workers must not share a stream
        with Image.open(self.files[index]) as img:
            img = img.convert("RGB")
        p = self.patch_size
        if img.width < p or img.height < p:
            img = img.resize((max(p, img.width), max(p, img.height)), Image.BICUBIC)

        hr = None
        for _ in range(5):
            x = rng.randrange(0, img.width - p + 1)
            y = rng.randrange(0, img.height - p + 1)
            hr = img.crop((x, y, x + p, y + p))
            if np.asarray(hr, dtype=np.float32).std() / 255.0 >= _MIN_PATCH_STD:
                break
        if rng.random() < 0.5:
            hr = hr.transpose(Image.FLIP_LEFT_RIGHT)

        lr = degrade(hr, self.scale, rng)
        return to_tensor(lr), to_tensor(hr)


def load_validation_pairs(dirs: list[Path], scale: int, count: int, size: int = 256) -> list[tuple[torch.Tensor, torch.Tensor]]:
    """Fixed validation pairs: centre crop of `size` px, clean bicubic downscale.

    Clean (not randomly degraded) so the numbers are comparable across runs
    and against the plain-bicubic baseline.
    """
    pairs = []
    for path in list_images(dirs, "val")[:count]:
        with Image.open(path) as img:
            img = img.convert("RGB")
        s = min(size, img.width, img.height)
        s -= s % (scale * 8)
        left, top = (img.width - s) // 2, (img.height - s) // 2
        hr = img.crop((left, top, left + s, top + s))
        lr = hr.resize((s // scale, s // scale), Image.BICUBIC)
        pairs.append((to_tensor(lr), to_tensor(hr)))
    return pairs
