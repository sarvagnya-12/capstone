"""Score FastGAN checkpoints against ONE shared reference set of real images.

WHY THIS EXISTS. Every training run writes its own results/<run>/fid_scores.txt,
and those numbers are not comparable between runs. The package measures FID
against the training set it was given, so a run on a larger, more diverse corpus
is scored against a harder target and reports a worse number even when the model
is better. Comparing raw fid_scores.txt across runs therefore prefers whichever
run had the least diverse data.

This scores every candidate against the same fixed, seeded sample of real
images, which makes the numbers comparable. It is what decided the current
GAN_CHECKPOINT, and it is the check to run before promoting any new one.

FID is lower-is-better, and it is a set-vs-set statistic: it says nothing about
any individual image. Always look at sample grids too -- FID alone completely
missed this project's colour-correlated failure mode.

Usage:
    cd backend
    .venv\\Scripts\\python.exe scripts\\compare_checkpoints.py \\
        --images-dir "<path to gan_training_images>" \\
        storage/fastgan/models/shoes150k/model_20.pt \\
        storage/fastgan/models/shoes300k/model_40.pt
"""

from __future__ import annotations

import argparse
import random
import sys
from pathlib import Path

import numpy as np
import torch
from PIL import Image

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.ml.gan.evaluation import compute_fid  # noqa: E402
from app.ml.gan.fastgan import generate_image_from_latent, load_fastgan_generator  # noqa: E402


def load_reference(images_dir: Path, count: int, seed: int, size: int) -> list[torch.Tensor]:
    paths = sorted(images_dir.glob("*.jpg"))
    if len(paths) < count:
        raise SystemExit(f"only {len(paths)} images in {images_dir}, need {count}")
    # Seeded and drawn from a sorted list, so the reference set is identical on
    # every invocation and on every machine. Without this the comparison drifts
    # between runs and small FID differences become meaningless.
    random.seed(seed)
    reals = []
    for path in random.sample(paths, count):
        image = Image.open(path).convert("RGB").resize((size, size))
        reals.append(torch.from_numpy(np.array(image)).permute(2, 0, 1).float() / 255.0)
    return reals


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("checkpoints", nargs="+", type=Path)
    parser.add_argument("--images-dir", required=True, type=Path, help="Folder of real training images")
    parser.add_argument("--count", type=int, default=256, help="Reference/generated images per model")
    parser.add_argument("--seed", type=int, default=1234, help="Fixes the reference sample; keep constant across comparisons")
    parser.add_argument("--size", type=int, default=256)
    args = parser.parse_args()

    if not args.images_dir.is_dir():
        raise SystemExit(f"No such images directory: {args.images_dir}")

    reals = load_reference(args.images_dir, args.count, args.seed, args.size)
    print(f"reference set: {len(reals)} real images from {args.images_dir} (seed {args.seed})\n")

    results: list[tuple[str, float]] = []
    for checkpoint in args.checkpoints:
        label = f"{checkpoint.parent.name}/{checkpoint.name}"
        if not checkpoint.exists():
            print(f"{label:<44} MISSING")
            continue
        generator = load_fastgan_generator(checkpoint=checkpoint)
        # Same latent seed for every model, so differences are the models', not
        # the luck of which latents each one happened to draw.
        torch.manual_seed(7)
        fakes = [generate_image_from_latent(generator, torch.randn(1, generator.z_dim))
                 for _ in range(args.count)]
        score = compute_fid(reals, fakes)
        results.append((label, score))
        print(f"{label:<44} FID {score:.2f}")
        del generator
        torch.cuda.empty_cache()

    if len(results) > 1:
        best = min(results, key=lambda r: r[1])
        print(f"\nbest (lowest FID): {best[0]}  ->  {best[1]:.2f}")
        print("Inspect its sample grid before promoting it to GAN_CHECKPOINT.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
