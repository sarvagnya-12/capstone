"""Train a FastGAN generator from scratch on real product photos (Step 17).

WHY FROM SCRATCH, AND WHY NOT STYLEGAN2. Decision #6 originally specified
transfer learning from a pretrained StyleGAN2 checkpoint, on the reasoning
that local hardware could not train a generator from nothing. Three measured
attempts at that approach all ended worse than their own starting point:

  1. no regularization, 512px, 3,014 images   -> D dominated (d_loss 0.0005),
                                                 FID 262 -> 466
  2. R1 gamma=10, 256px, 25,023 images        -> g_loss 0.75 -> 17 -> NaN @154
  3. R1 gamma=1 + grad clipping, lr 5e-4      -> numerically healthy, FID
                                                 325 -> 344 -> 371 -> 365

Attempt 3 is the decisive one: it was stable and still got monotonically
worse, and finetune.py's own selector reported the untouched pretrained
checkpoint as the best of every scored checkpoint. The failure is not tuning,
it is the domain gap -- the only pretrained checkpoints available are faces
and cats, and a batch-4 loop cannot carry either to footwear.

What changed is the data: 25,023 real 256x256 shoe photos now exist (they did
not when Decision #6 was written). FastGAN (ICLR 2021, arXiv 2101.04775) is
built for precisely this regime -- from-scratch convergence on small datasets,
on one consumer GPU, in hours -- and needs no custom CUDA kernels, unlike the
StyleGAN2 ops that fall back to slow pure-Python here for want of a compiler.

NO PRETRAINED WEIGHTS ARE USED. G and D start from random initialization and
see only the shoe corpus.

The StyleGAN2 path (model.py, finetune.py) is deliberately left intact and
selectable, so the earlier approach stays reproducible rather than deleted.

Usage:
    python -m app.ml.gan.train_fastgan --images-dir <dir> --steps 20000
"""

from __future__ import annotations

import argparse
import math
import shutil
import sys
from pathlib import Path

import torch

BACKEND_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_RESULTS_DIR = BACKEND_ROOT / "storage" / "fastgan"
DEFAULT_RUN_NAME = "shoes"


def train(
    images_dir: Path,
    steps: int,
    image_size: int,
    batch_size: int,
    lr: float,
    save_every: int,
    fid_every: int,
    fid_images: int,
    base_dir: Path,
    run_name: str,
    aug_prob: float,
    amp: bool,
    num_workers: int,
    resume: bool,
) -> int:
    from lightweight_gan.lightweight_gan import Trainer

    if not images_dir.is_dir():
        raise SystemExit(f"No such images directory: {images_dir}")
    image_count = sum(1 for p in images_dir.iterdir() if p.suffix.lower() in {".jpg", ".jpeg", ".png"})
    if image_count == 0:
        raise SystemExit(f"No .jpg/.jpeg/.png files in {images_dir}")

    print(f"training on {image_count:,} images from {images_dir}")
    print(f"{image_size}px  batch={batch_size}  lr={lr}  steps={steps}")
    print(f"checkpoint every {save_every}, FID every {fid_every} over {fid_images} images\n")

    trainer = Trainer(
        name=run_name,
        base_dir=str(base_dir),
        # Relative, not absolute: the Trainer joins these onto base_dir, so
        # passing full paths here produces storage/fastgan/storage/fastgan/...
        results_dir="results",
        models_dir="models",
        image_size=image_size,
        batch_size=batch_size,
        lr=lr,
        # No num_train_steps here: it is not a Trainer parameter, so it falls
        # through **kwargs into LightweightGAN, which rejects it. The step
        # count is driven by the loop below instead.
        save_every=save_every,
        evaluate_every=save_every,
        # The package disables FID on None, not 0 -- it tests `exists(...)`
        # and then takes a modulo, so a literal 0 raises ZeroDivisionError.
        calculate_fid_every=fid_every if fid_every else None,
        calculate_fid_num_images=fid_images,
        # Even with 25k images, FastGAN's differentiable augmentation is what
        # keeps its self-supervised discriminator from memorising the set --
        # the same failure that killed every StyleGAN2 attempt here.
        aug_prob=aug_prob,
        aug_types=["translation", "cutout"],
        amp=amp,
        # Must be explicit: the package defaults use_aim=True, and its own
        # ImportError handler for the optional `aim` tracker only prints a
        # warning before dereferencing self.aim anyway, so leaving the default
        # crashes with AttributeError before training starts.
        use_aim=False,
        # The package defaults this to None, which decodes all 25k JPEGs on the
        # main process and makes data loading -- not the GPU -- the bottleneck:
        # measured 4.55 s/step at the default versus 0.45 s/step with 4 workers,
        # a 10x difference that decides whether a real run takes 2 hours or 22.
        num_workers=num_workers,
    )
    trainer.set_data_src(str(images_dir))

    start_step = 0
    if resume:
        trainer.load(-1)
        start_step = int(trainer.steps)
        print(f"resumed from checkpoint {trainer.checkpoint_num} at step {start_step}\n")

    for step in range(start_step, steps):
        # An evaluation failure must not destroy the training run. The first
        # real attempt died at step 2000 because the package's FID helper
        # imports pytorch_fid lazily and it was not installed -- the exception
        # propagated out of train() and killed 2.4 hours of queued work over a
        # metric. Losing a datapoint is acceptable; losing the run is not.
        try:
            trainer.train()
        except ModuleNotFoundError as e:
            print(f"  [warn] step {step}: evaluation dependency missing ({e}); "
                  "disabling FID for the rest of this run", flush=True)
            trainer.calculate_fid_every = None
        except Exception as e:  # noqa: BLE001 - deliberately broad, see above
            if "fid" not in str(e).lower():
                raise
            print(f"  [warn] step {step}: FID calculation failed ({e}); continuing", flush=True)
            trainer.calculate_fid_every = None

        if step % 10 == 0:
            d, g = float(trainer.d_loss), float(trainer.g_loss)
            # Abort immediately on a non-finite loss. A previous StyleGAN2 run
            # went NaN at step 154 and then burned ~2,400 further steps
            # computing nothing before anyone noticed.
            if not (math.isfinite(d) and math.isfinite(g)):
                raise SystemExit(
                    f"\nABORTED at step {step}: loss became non-finite (d={d}, g={g}).\n"
                    "Lower --lr and retry; checkpoints already written are still usable."
                )
            print(f"step {step}/{steps}  d_loss={d:.4f}  g_loss={g:.4f}", flush=True)

    trainer.save(trainer.checkpoint_num)
    print(f"\ndone. checkpoints in {base_dir / 'models' / run_name}")
    print(f"sample grids in {base_dir / 'results' / run_name}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--images-dir", required=True, type=Path)
    parser.add_argument("--steps", type=int, default=20000)
    parser.add_argument("--image-size", type=int, default=256)
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--lr", type=float, default=2e-4, help="FastGAN's own default; unlike StyleGAN2's 2.5e-3 this is tuned for small batches")
    parser.add_argument("--save-every", type=int, default=1000)
    parser.add_argument("--fid-every", type=int, default=1000)
    parser.add_argument("--fid-images", type=int, default=2048)
    parser.add_argument("--base-dir", type=Path, default=DEFAULT_RESULTS_DIR)
    parser.add_argument("--run-name", default=DEFAULT_RUN_NAME)
    parser.add_argument("--aug-prob", type=float, default=0.5)
    parser.add_argument("--num-workers", type=int, default=4,
                        help="Dataloader workers; 0/None makes JPEG decode the bottleneck (10x slower)")
    parser.add_argument("--amp", action="store_true", help="Mixed precision; lower VRAM and faster on this 6GB card")
    parser.add_argument("--resume", action="store_true",
                        help="Continue from the latest checkpoint of this run name")
    parser.add_argument("--fresh", action="store_true", help="Delete any existing run of this name first")
    args = parser.parse_args()

    if args.fresh:
        for sub in ("models", "results"):
            target = args.base_dir / sub / args.run_name
            if target.exists():
                shutil.rmtree(target)
                print(f"removed {target}")

    if not torch.cuda.is_available():
        print("WARNING: no CUDA device found; this will be extremely slow on CPU", file=sys.stderr)

    return train(
        images_dir=args.images_dir,
        steps=args.steps,
        image_size=args.image_size,
        batch_size=args.batch_size,
        lr=args.lr,
        save_every=args.save_every,
        fid_every=args.fid_every,
        fid_images=args.fid_images,
        base_dir=args.base_dir,
        run_name=args.run_name,
        aug_prob=args.aug_prob,
        amp=args.amp,
        num_workers=args.num_workers,
        resume=args.resume,
    )


if __name__ == "__main__":
    sys.exit(main())
