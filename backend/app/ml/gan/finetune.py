"""Fine-tunes the pretrained StyleGAN2-ADA checkpoint (Step 15) on real
product images from ref_images (ingested via Step 13), continuing training
from the pretrained weights rather than training from scratch (Decision #6).

Simplified training loop: standard non-saturating GAN loss (generator +
discriminator, alternating Adam updates). This is deliberately NOT NVIDIA's
full training recipe (no R1 gradient penalty, no path-length regularization,
no adaptive-discriminator-augmentation pipeline) -- reproducing that would
require vendoring substantially more of NVIDIA's training infrastructure
than Step 15's inference-only subset (dnnlib/, torch_utils/, legacy.py). A
full reproduction is out of scope given this step's own stated purpose: a
smoke test proving the fine-tuning mechanics work, not a from-scratch
reimplementation of NVIDIA's research training pipeline. EMA sync is a
direct weight copy (G_ema <- G) rather than NVIDIA's running-average
schedule, for the same reason.

MUST be run on a cloud/rented GPU (Colab/Kaggle or equivalent) for anything
beyond a smoke test -- not the certified local hardware (PRD Sec 5.4/5.28,
the hardware-vs-compute tension this decision explicitly reconciles).

CANNOT produce a meaningfully improved checkpoint today: the dataset
pipeline has generated zero real records (project_manifest.json). Until
then, this script is validated only as a smoke test against a handful of
placeholder images -- confirming the training loop runs without error and
produces a different checkpoint, not that it improves output quality.
Re-run against real ref_images downloads once the pipeline has been
executed for real; no code change needed, only --images-dir.

Usage:
    python -m app.ml.gan.finetune --images-dir <dir of .jpg/.jpeg/.png> \
        --output storage/models/afhqcat_finetuned.pkl --steps 20
"""

import argparse
import pickle
import sys
from pathlib import Path

import numpy as np
import torch
import torch.nn.functional as F
from PIL import Image
from torch.utils.data import DataLoader, Dataset

_VENDOR_ROOT = Path(__file__).resolve().parent / "vendor" / "stylegan2_ada"
if str(_VENDOR_ROOT) not in sys.path:
    sys.path.insert(0, str(_VENDOR_ROOT))

import legacy  # noqa: E402  (vendored NVIDIA module, see vendor/stylegan2_ada/)

from app.ml.gan.model import DEFAULT_CHECKPOINT_PATH  # noqa: E402


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


def finetune(checkpoint_path: Path, images_dir: Path, steps: int, batch_size: int, lr: float, output_path: Path) -> None:
    device = "cuda" if torch.cuda.is_available() else "cpu"

    with open(checkpoint_path, "rb") as f:
        data = legacy.load_network_pkl(f)

    G = data["G"].train().requires_grad_(True).to(device)
    D = data["D"].train().requires_grad_(True).to(device)

    dataset = ImageFolderDataset(images_dir, resolution=G.img_resolution)
    if len(dataset) == 0:
        raise SystemExit(f"No .jpg/.jpeg/.png files found in {images_dir}")
    loader = DataLoader(dataset, batch_size=min(batch_size, len(dataset)), shuffle=True, drop_last=False)

    g_opt = torch.optim.Adam(G.parameters(), lr=lr, betas=(0.0, 0.99))
    d_opt = torch.optim.Adam(D.parameters(), lr=lr, betas=(0.0, 0.99))

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
        real_scores = D(real, label)
        fake_scores = D(fake, label)
        d_loss = (F.softplus(-real_scores) + F.softplus(fake_scores)).mean()
        d_loss.backward()
        d_opt.step()

        # --- Generator step ---
        z = torch.randn(batch, G.z_dim, device=device)
        g_opt.zero_grad(set_to_none=True)
        fake = G(z, label, noise_mode="const")
        fake_scores = D(fake, label)
        g_loss = F.softplus(-fake_scores).mean()
        g_loss.backward()
        g_opt.step()

        print(f"step {step + 1}/{steps}  d_loss={d_loss.item():.4f}  g_loss={g_loss.item():.4f}")

    # Simplified EMA sync (see module docstring): direct weight copy rather
    # than NVIDIA's proper running-average schedule.
    data["G_ema"].load_state_dict(G.state_dict())

    data["G"] = G.cpu()
    data["D"] = D.cpu()
    data["G_ema"] = data["G_ema"].cpu()

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "wb") as f:
        pickle.dump(data, f)
    print(f"Saved fine-tuned checkpoint to {output_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--images-dir", required=True, help="Directory of .jpg/.jpeg/.png images to fine-tune on")
    parser.add_argument("--checkpoint", default=str(DEFAULT_CHECKPOINT_PATH), help="Pretrained checkpoint to start from")
    parser.add_argument("--output", required=True, help="Path to write the fine-tuned checkpoint")
    parser.add_argument("--steps", type=int, default=20, help="Number of G/D alternating training steps")
    parser.add_argument("--batch-size", type=int, default=4)
    parser.add_argument("--lr", type=float, default=0.002)
    args = parser.parse_args()

    finetune(Path(args.checkpoint), Path(args.images_dir), args.steps, args.batch_size, args.lr, Path(args.output))


if __name__ == "__main__":
    main()
