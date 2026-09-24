"""Fine-tunes the pretrained StyleGAN2-ADA checkpoint (Step 15) on real
product images from ref_images (ingested via Step 13), continuing training
from the pretrained weights rather than training from scratch (Decision #6).

Training loop: non-saturating GAN loss (generator + discriminator,
alternating Adam updates) plus an R1 gradient penalty on the discriminator.

R1 was added after a measured failure, not speculatively. The original loop
had no regularization at all, and fine-tuning the 512x512 afhqcat checkpoint
on 3,014 real shoe photos diverged hard: the discriminator reached
d_loss=0.0005 within 250 steps (near-perfect real/fake separation), g_loss
climbed past 9, and FID went 262 -> 466 -- i.e. markedly WORSE than the
pretrained starting point. Lowering the learning rate to 0.001 did not
prevent it. R1 penalizes the gradient of D's output w.r.t. real images,
which is the standard, targeted remedy for exactly that runaway; see
storage/models/diverged_run_evidence.txt for the recorded numbers.

Still deliberately NOT NVIDIA's full recipe: no path-length regularization
and no adaptive-discriminator-augmentation pipeline, since those would
require vendoring substantially more of their training infrastructure than
Step 15's inference-only subset (dnnlib/, torch_utils/, legacy.py). EMA sync
remains a direct weight copy (G_ema <- G) rather than NVIDIA's
running-average schedule, for the same reason. R1 is the one piece adopted,
because it addresses the specific, observed failure mode.

Runs on the local RTX 4050 at roughly 2.7-4.0 s/step (256x256, batch 4),
measured -- so a few thousand steps is an overnight job rather than the
cloud-GPU-only proposition this docstring originally assumed. A rented GPU
is still faster, but no longer required to get past a smoke test.

Defaults are set from measured failures, not from StyleGAN2's published
numbers, because those assume batch sizes 8-16x larger than fits in 6GB:
  --lr 0.0005     NVIDIA's 0.0025 at batch 4 sent g_loss 0.75 -> 17 -> NaN
                  by step 154.
  --r1-gamma 1.0  NVIDIA's own value at 256x256. gamma=10 combined with the
                  lazy-regularization interval scaling was ~20x too strong.
  --grad-clip 5.0 Bounds both G and D gradients.
Training aborts immediately if either loss becomes non-finite, rather than
spending hours propagating NaN through every weight.

Usage:
    python -m app.ml.gan.finetune --images-dir <dir of .jpg/.jpeg/.png> \
        --checkpoint storage/models/ffhq-res256.pkl \
        --output storage/models/shoes256.pkl --steps 3000 --eval-every 500
"""

import argparse
import copy
import json
import math
import pickle
import sys
from pathlib import Path
from typing import Optional

import numpy as np
import torch
import torch.nn.functional as F
from PIL import Image
from torch.utils.data import DataLoader, Dataset

_VENDOR_ROOT = Path(__file__).resolve().parent / "vendor" / "stylegan2_ada"
if str(_VENDOR_ROOT) not in sys.path:
    sys.path.insert(0, str(_VENDOR_ROOT))

import legacy  # noqa: E402  (vendored NVIDIA module, see vendor/stylegan2_ada/)

from app.ml.gan.evaluation import compute_fid  # noqa: E402
# STYLEGAN2_CHECKPOINT_PATH, not DEFAULT_CHECKPOINT_PATH: the application
# default is now a FastGAN .pt, which this StyleGAN2-only script cannot read.
from app.ml.gan.model import STYLEGAN2_CHECKPOINT_PATH  # noqa: E402


class ImageFolderDataset(Dataset):
    """Every .jpg/.jpeg/.png file directly under images_dir, resized to the
    generator's native resolution and normalized to [-1, 1]."""

    def __init__(self, images_dir: Path, resolution: int):
        self.paths = sorted(
            p for p in Path(images_dir).iterdir() if p.suffix.lower() in {".jpg", ".jpeg", ".png"}
        )
        self.resolution = resolution

    def __len__(self) -> int:
        return len(self.paths)

    def __getitem__(self, idx: int) -> torch.Tensor:
        img = Image.open(self.paths[idx]).convert("RGB").resize((self.resolution, self.resolution))
        tensor = torch.from_numpy(np.array(img)).permute(2, 0, 1).float()
        return tensor / 127.5 - 1.0  # [0, 255] -> [-1, 1]


@torch.no_grad()
def _score_against_real(G_ema, dataset, device: str, n: int = 32) -> Optional[float]:
    """FID between n generated samples and n real training images.

    Even with R1, the loop lacks path-length regularization and ADA (see
    module docstring), so it is not reliably monotonic -- training longer can
    make output worse, and a run without R1 measurably did (FID 262 -> 466).
    Scoring at intervals turns that risk into something measured: the caller
    keeps the best-scoring checkpoint instead of assuming the final one is best.
    """
    was_training = G_ema.training
    G_ema.eval()

    fakes = []
    for _ in range(n):
        z = torch.randn(1, G_ema.z_dim, device=device)
        img = G_ema(z, torch.zeros([1, G_ema.c_dim], device=device), noise_mode="const")
        # generator emits [-1, 1]; compute_fid expects [0, 1]
        fakes.append((img[0].clamp(-1, 1) * 0.5 + 0.5).cpu())

    indices = np.random.choice(len(dataset), size=min(n, len(dataset)), replace=False)
    reals = [(dataset[int(i)].clamp(-1, 1) * 0.5 + 0.5).cpu() for i in indices]

    if was_training:
        G_ema.train()
    return compute_fid(reals, fakes)


def _save_checkpoint(data: dict, G, D, G_ema_source, path: Path) -> None:
    """Snapshot to disk without disturbing the in-flight training tensors.

    Deep-copying to CPU matters: the original script mutated `data` by moving
    G/D to CPU before pickling, which is fine once at the end but would break
    training if done at every interval.
    """
    snapshot = dict(data)
    snapshot["G"] = copy.deepcopy(G).cpu().eval()
    snapshot["D"] = copy.deepcopy(D).cpu().eval()
    snapshot["G_ema"] = copy.deepcopy(G_ema_source).cpu().eval()
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as f:
        pickle.dump(snapshot, f)


def finetune(
    checkpoint_path: Path,
    images_dir: Path,
    steps: int,
    batch_size: int,
    lr: float,
    output_path: Path,
    eval_every: int = 0,
    eval_samples: int = 32,
    r1_gamma: float = 1.0,
    r1_interval: int = 16,
    d_lr_scale: float = 1.0,
    grad_clip: float = 5.0,
) -> list[dict]:
    device = "cuda" if torch.cuda.is_available() else "cpu"

    with open(checkpoint_path, "rb") as f:
        data = legacy.load_network_pkl(f)

    G = data["G"].train().requires_grad_(True).to(device)
    D = data["D"].train().requires_grad_(True).to(device)
    # G_ema must live on the same device as the latents fed to it during
    # interval FID evaluation. The original end-of-run-only flow left it on
    # CPU, which was harmless then (load_state_dict copies in place, keeping
    # the destination device) but breaks the moment it is actually run.
    data["G_ema"] = data["G_ema"].to(device)

    dataset = ImageFolderDataset(images_dir, resolution=G.img_resolution)
    if len(dataset) == 0:
        raise SystemExit(f"No .jpg/.jpeg/.png files found in {images_dir}")
    loader = DataLoader(dataset, batch_size=min(batch_size, len(dataset)), shuffle=True, drop_last=False)

    g_opt = torch.optim.Adam(G.parameters(), lr=lr, betas=(0.0, 0.99))
    # d_lr_scale < 1 slows the discriminator relative to the generator, a
    # second lever against the domination failure R1 also targets.
    d_opt = torch.optim.Adam(D.parameters(), lr=lr * d_lr_scale, betas=(0.0, 0.99))

    history: list[dict] = []
    if eval_every:
        baseline = _score_against_real(data["G_ema"], dataset, device, n=eval_samples)
        history.append({"step": 0, "fid": baseline, "path": str(checkpoint_path), "d_loss": None, "g_loss": None})
        print(f"  [eval] step 0 (pretrained baseline)  FID="
              f"{baseline if baseline is None else round(baseline, 2)}", flush=True)

    data_iter = iter(loader)
    for step in range(steps):
        try:
            real = next(data_iter)
        except StopIteration:
            data_iter = iter(loader)
            real = next(data_iter)
        real = real.to(device)
        batch = real.shape[0]
        label = torch.zeros([batch, G.c_dim], device=device)

        # --- Discriminator step ---
        z = torch.randn(batch, G.z_dim, device=device)
        with torch.no_grad():
            fake = G(z, label, noise_mode="const")
        d_opt.zero_grad(set_to_none=True)

        # R1 needs gradients w.r.t. the real images themselves.
        real_for_d = real.detach().requires_grad_(r1_gamma > 0)
        real_scores = D(real_for_d, label)
        fake_scores = D(fake, label)
        d_loss = (F.softplus(-real_scores) + F.softplus(fake_scores)).mean()

        r1_value = 0.0
        if r1_gamma > 0 and (step % r1_interval == 0):
            # Penalize the squared gradient norm of D's output on real data.
            # Lazy regularization (every r1_interval steps) is NVIDIA's own
            # trick: the double-backward is expensive and the penalty is
            # smooth enough that applying it every step buys little.
            (grad_real,) = torch.autograd.grad(
                outputs=real_scores.sum(), inputs=real_for_d, create_graph=True
            )
            r1_penalty = grad_real.square().sum(dim=[1, 2, 3]).mean()
            # gamma/2 * penalty, scaled by the interval so lazy application
            # keeps the same effective strength.
            d_loss = d_loss + (r1_gamma / 2) * r1_penalty * r1_interval
            r1_value = r1_penalty.item()

        d_loss.backward()
        if grad_clip > 0:
            torch.nn.utils.clip_grad_norm_(D.parameters(), grad_clip)
        d_opt.step()

        # --- Generator step ---
        z = torch.randn(batch, G.z_dim, device=device)
        g_opt.zero_grad(set_to_none=True)
        fake = G(z, label, noise_mode="const")
        fake_scores = D(fake, label)
        g_loss = F.softplus(-fake_scores).mean()
        g_loss.backward()
        if grad_clip > 0:
            torch.nn.utils.clip_grad_norm_(G.parameters(), grad_clip)
        g_opt.step()

        d_value, g_value = d_loss.item(), g_loss.item()
        print(f"step {step + 1}/{steps}  d_loss={d_value:.4f}  g_loss={g_value:.4f}"
              f"  r1={r1_value:.4f}", flush=True)

        # Abort the moment the run is unrecoverable. NaN propagates into every
        # weight, so all later steps and checkpoints are garbage -- a previous
        # run went NaN at step 154 and then burned ~2,400 further steps (about
        # two hours) computing nothing, and even wrote a scored checkpoint from
        # the corrupted model. Failing loudly and immediately is strictly
        # better than discovering it hours later.
        if not (math.isfinite(d_value) and math.isfinite(g_value)):
            raise SystemExit(
                f"\nABORTED at step {step + 1}: loss became non-finite "
                f"(d_loss={d_value}, g_loss={g_value}).\n"
                "The model is unrecoverable from here. Typical causes are too high a "
                "learning rate for the batch size, or too strong an R1 penalty.\n"
                "Try a lower --lr, a lower --r1-gamma, or a smaller --grad-clip.\n"
                + (f"Last good checkpoint: {history[-1]['path']}" if history else
                   "No interval checkpoint was written before the failure.")
            )

        if eval_every and (step + 1) % eval_every == 0:
            data["G_ema"].load_state_dict(G.state_dict())
            fid = _score_against_real(data["G_ema"], dataset, device, n=eval_samples)
            interval_path = output_path.with_name(f"{output_path.stem}_step{step + 1:05d}{output_path.suffix}")
            _save_checkpoint(data, G, D, data["G_ema"], interval_path)
            history.append({"step": step + 1, "fid": fid, "path": str(interval_path),
                            "d_loss": d_loss.item(), "g_loss": g_loss.item()})
            print(f"  [eval] step {step + 1}  FID={fid if fid is None else round(fid, 2)}"
                  f"  -> {interval_path.name}", flush=True)

    # Simplified EMA sync (see module docstring): direct weight copy rather
    # than NVIDIA's proper running-average schedule.
    data["G_ema"].load_state_dict(G.state_dict())
    _save_checkpoint(data, G, D, data["G_ema"], output_path)
    print(f"Saved fine-tuned checkpoint to {output_path}")

    if history:
        scored = [h for h in history if h["fid"] is not None]
        if scored:
            best = min(scored, key=lambda h: h["fid"])
            print(f"\nBest FID {best['fid']:.2f} at step {best['step']}: {best['path']}")
            print("Lower is better. If the best step is not the last one, the extra "
                  "training made output worse -- prefer the best checkpoint.")
        history_path = output_path.with_name(f"{output_path.stem}_history.json")
        history_path.write_text(json.dumps(history, indent=2), encoding="utf-8")
        print(f"FID history -> {history_path}")

    return history


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--images-dir", required=True, help="Directory of .jpg/.jpeg/.png images to fine-tune on")
    parser.add_argument("--checkpoint", default=str(STYLEGAN2_CHECKPOINT_PATH), help="Pretrained checkpoint to start from")
    parser.add_argument("--output", required=True, help="Path to write the fine-tuned checkpoint")
    parser.add_argument("--steps", type=int, default=20, help="Number of G/D alternating training steps")
    parser.add_argument("--batch-size", type=int, default=4)
    parser.add_argument("--lr", type=float, default=0.0005,
                        help="Adam LR. StyleGAN2's own 0.0025 assumes batch 32-64; at the small batches this script uses it explodes (observed: NaN at step 154).")
    parser.add_argument("--eval-every", type=int, default=0,
                        help="Save an interim checkpoint and score its FID every N steps (0 disables)")
    parser.add_argument("--eval-samples", type=int, default=32,
                        help="Generated/real images per FID evaluation")
    parser.add_argument("--r1-gamma", type=float, default=1.0,
                        help="R1 strength. 1.0 is NVIDIA's own value for 256x256; gamma=10 with lazy scaling was ~20x too strong and blew up.")
    parser.add_argument("--r1-interval", type=int, default=16,
                        help="Apply R1 every N steps (lazy regularization)")
    parser.add_argument("--d-lr-scale", type=float, default=1.0,
                        help="Multiplier on the discriminator's learning rate, e.g. 0.5 to slow it")
    parser.add_argument("--grad-clip", type=float, default=5.0,
                        help="Max gradient norm for G and D (0 disables)")
    args = parser.parse_args()

    finetune(Path(args.checkpoint), Path(args.images_dir), args.steps, args.batch_size, args.lr,
             Path(args.output), eval_every=args.eval_every, eval_samples=args.eval_samples,
             r1_gamma=args.r1_gamma, r1_interval=args.r1_interval, d_lr_scale=args.d_lr_scale,
             grad_clip=args.grad_clip)


if __name__ == "__main__":
    main()
