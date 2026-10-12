"""Compare the ESRGAN upscaler against bicubic on real FastGAN outputs.

The training-time validation (train_esrgan.py) uses real photos, which is the
wrong distribution for the question that matters: does ESRGAN help on what the
GAN actually produces? GAN outputs have no high-resolution original, so there
is no PSNR/SSIM here. Instead:

  - FID of the 2x-upscaled images against REAL 512px photos (lower = closer to
    real photos), bicubic vs ESRGAN, scored in one invocation on the same
    reference sample and the same GAN latents.
  - Sharpness (variance of the Laplacian, on the upscaled image) -- a crude
    proxy: higher = more fine detail, but noise and artefacts also raise it,
    so it is only meaningful together with the grids.
  - Side-by-side grids (bicubic | ESRGAN), full image and a 1:1 centre crop,
    to judge by eye. FID alone missed this project's colour failure before.

Usage:
    cd backend
    .venv\\Scripts\\python.exe scripts\\compare_upscalers.py \\
        --real-dir "<sr_training_images_512>" --out storage/esrgan/compare_gan
"""

from __future__ import annotations

import argparse
import random
import sys
from pathlib import Path

import numpy as np
import torch
import torch.nn.functional as F
from PIL import Image

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.core.config import settings  # noqa: E402
from app.ml.gan.evaluation import compute_fid  # noqa: E402
from app.ml.gan.fastgan import generate_image_from_latent, load_fastgan_generator  # noqa: E402
from app.ml.sr.data import to_image, to_tensor  # noqa: E402
from app.ml.sr.upscale import load_upscaler, upscale  # noqa: E402


def laplacian_variance(t: torch.Tensor) -> float:
    gray = (0.299 * t[0] + 0.587 * t[1] + 0.114 * t[2]).unsqueeze(0).unsqueeze(0)
    kernel = torch.tensor([[0, 1, 0], [1, -4, 1], [0, 1, 0]], dtype=torch.float32).view(1, 1, 3, 3)
    return float(F.conv2d(gray, kernel).var())


def load_reals(real_dir: Path, count: int, seed: int, size: int) -> list[torch.Tensor]:
    paths = sorted(real_dir.glob("*.jpg"))
    if len(paths) < count:
        raise SystemExit(f"only {len(paths)} images in {real_dir}, need {count}")
    random.seed(seed)
    return [to_tensor(Image.open(p).convert("RGB").resize((size, size), Image.LANCZOS))
            for p in random.sample(paths, count)]


def save_grid(rows: list[tuple[Image.Image, Image.Image]], path: Path, crop: int | None) -> None:
    tiles = []
    for bicubic, esrgan in rows:
        if crop:
            w, h = bicubic.size
            box = ((w - crop) // 2, (h - crop) // 2, (w + crop) // 2, (h + crop) // 2)
            bicubic, esrgan = bicubic.crop(box), esrgan.crop(box)
        tiles.append((bicubic, esrgan))
    tw, th = tiles[0][0].size
    gap = 4
    grid = Image.new("RGB", (2 * tw + gap, len(tiles) * (th + gap) - gap), (255, 255, 255))
    for i, (b, e) in enumerate(tiles):
        grid.paste(b, (0, i * (th + gap)))
        grid.paste(e, (tw + gap, i * (th + gap)))
    grid.save(path, quality=95)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--real-dir", required=True, type=Path, help="Real 512px photos (FID reference)")
    parser.add_argument("--gan-checkpoint", type=Path, default=Path(settings.GAN_CHECKPOINT))
    parser.add_argument("--sr-checkpoint", type=Path, default=Path(settings.SR_CHECKPOINT))
    parser.add_argument("--count", type=int, default=256)
    parser.add_argument("--grid-count", type=int, default=6)
    parser.add_argument("--seed", type=int, default=1234)
    parser.add_argument("--out", type=Path, default=BACKEND_ROOT / "storage" / "esrgan" / "compare_gan")
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    generator = load_fastgan_generator(checkpoint=args.gan_checkpoint)
    upscaler = load_upscaler(args.sr_checkpoint)
    print(f"GAN: {args.gan_checkpoint}\nESRGAN: {args.sr_checkpoint}\n")

    torch.manual_seed(7)  # same latents on every invocation
    bicubic_imgs, esrgan_imgs, grid_rows = [], [], []
    for i in range(args.count):
        gan = to_image(generate_image_from_latent(generator, torch.randn(1, generator.z_dim)))
        size = (gan.width * 2, gan.height * 2)
        b = gan.resize(size, Image.BICUBIC)
        e = upscale(gan, model=upscaler)
        bicubic_imgs.append(to_tensor(b))
        esrgan_imgs.append(to_tensor(e))
        if i < args.grid_count:
            grid_rows.append((b, e))
    del generator
    torch.cuda.empty_cache()

    reals = load_reals(args.real_dir, args.count, args.seed, size[0])
    print(f"reference: {len(reals)} real {size[0]}px photos from {args.real_dir} (seed {args.seed})\n")

    print(f"{'method':<10}{'FID vs real':>14}{'sharpness':>12}")
    for name, imgs in (("bicubic", bicubic_imgs), ("esrgan", esrgan_imgs)):
        fid = compute_fid(reals, imgs)
        sharp = float(np.mean([laplacian_variance(t) for t in imgs]))
        print(f"{name:<10}{fid:>14.2f}{sharp * 1e4:>12.2f}")
    sharp_real = float(np.mean([laplacian_variance(t) for t in reals]))
    print(f"{'real':<10}{'-':>14}{sharp_real * 1e4:>12.2f}   (sharpness of the real photos, for scale)")

    save_grid(grid_rows, args.out / "gan_full.jpg", crop=None)
    save_grid(grid_rows, args.out / "gan_crop.jpg", crop=192)
    print(f"\ngrids (left bicubic | right ESRGAN): {args.out / 'gan_full.jpg'}, {args.out / 'gan_crop.jpg'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
