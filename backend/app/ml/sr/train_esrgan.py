"""Train an ESRGAN-style 2x upscaler from scratch on real product photos.

Two phases, as in ESRGAN:
  1. PSNR phase -- L1 loss only. Stable; teaches correct colour and structure.
     A GAN started from random weights tends to learn artefacts first.
  2. GAN phase -- L1 + VGG perceptual + adversarial (U-Net discriminator),
     Real-ESRGAN's weights (1.0 / 1.0 / 0.1). Trades a little PSNR for
     realistic texture instead of blur.

The generator starts from random initialisation and sees only the shoe
corpus. (VGG19 ImageNet weights are used inside the perceptual loss only --
see losses.py.) An exponential moving average of the generator's weights is
what gets saved for inference: it is smoother and less prone to GAN artefacts
than the raw weights at any single step.

Usage (first run, 512px originals):
    python -m app.ml.sr.train_esrgan --images-dir <sr_training_images_512> \\
        --run-name shoes512 --steps-psnr 20000 --steps-gan 40000 --amp

Adding the 256px GAN corpus later (same 2x task, more variety):
    python -m app.ml.sr.train_esrgan --images-dir <sr_512> --images-dir <gan_training_images> ...

Outputs under backend/storage/esrgan/:
    models/<run>/net_g_ema_<step>.pt   inference weights (+ architecture config)
    models/<run>/latest.pt             full training state for --resume
    results/<run>/metrics.csv          validation PSNR/SSIM/VGG distance vs bicubic
    results/<run>/samples_<step>.png   bicubic | ESRGAN | original crops
"""

from __future__ import annotations

import argparse
import copy
import csv
import math
import shutil
import sys
import time
from pathlib import Path

import torch
import torch.nn.functional as F
from torch.utils.data import DataLoader

BACKEND_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_BASE_DIR = BACKEND_ROOT / "storage" / "esrgan"


def _infinite(loader):
    while True:
        yield from loader


@torch.no_grad()
def _update_ema(ema, model, decay: float) -> None:
    for e, m in zip(ema.parameters(), model.parameters()):
        e.mul_(decay).add_(m.detach(), alpha=1 - decay)
    for e, m in zip(ema.buffers(), model.buffers()):
        e.copy_(m)


@torch.no_grad()
def evaluate(net, pairs, perceptual, device, amp: bool) -> dict:
    from kornia.metrics import psnr, ssim

    net.eval()
    totals = {"psnr": 0.0, "ssim": 0.0, "vgg": 0.0}
    for lr, hr in pairs:
        lr, hr = lr.unsqueeze(0).to(device), hr.unsqueeze(0).to(device)
        with torch.autocast("cuda", dtype=torch.bfloat16, enabled=amp and device.type == "cuda"):
            out = net(lr)
        out = out.float().clamp(0, 1)
        totals["psnr"] += float(psnr(out, hr, 1.0))
        totals["ssim"] += float(ssim(out, hr, 11).mean())
        totals["vgg"] += float(perceptual(out, hr))
    net.train()
    return {k: v / len(pairs) for k, v in totals.items()}


@torch.no_grad()
def bicubic_baseline(pairs, perceptual, device) -> dict:
    from kornia.metrics import psnr, ssim

    totals = {"psnr": 0.0, "ssim": 0.0, "vgg": 0.0}
    for lr, hr in pairs:
        lr, hr = lr.unsqueeze(0).to(device), hr.unsqueeze(0).to(device)
        up = F.interpolate(lr, size=hr.shape[-2:], mode="bicubic", align_corners=False).clamp(0, 1)
        totals["psnr"] += float(psnr(up, hr, 1.0))
        totals["ssim"] += float(ssim(up, hr, 11).mean())
        totals["vgg"] += float(perceptual(up, hr))
    return {k: v / len(pairs) for k, v in totals.items()}


@torch.no_grad()
def save_samples(net, pairs, path: Path, device, amp: bool, count: int = 4, crop: int = 128) -> None:
    from torchvision.utils import save_image

    net.eval()
    rows = []
    for lr, hr in pairs[:count]:
        lr_b = lr.unsqueeze(0).to(device)
        with torch.autocast("cuda", dtype=torch.bfloat16, enabled=amp and device.type == "cuda"):
            out = net(lr_b).float().clamp(0, 1)[0].cpu()
        up = F.interpolate(lr_b, size=hr.shape[-2:], mode="bicubic", align_corners=False).clamp(0, 1)[0].cpu()
        # Centre crop at full resolution -- detail is invisible in a thumbnail.
        h, w = hr.shape[-2:]
        c = min(crop, h, w)
        t, l = (h - c) // 2, (w - c) // 2
        rows += [up[:, t:t + c, l:l + c], out[:, t:t + c, l:l + c], hr[:, t:t + c, l:l + c]]
    save_image(torch.stack(rows), path, nrow=3, padding=2, pad_value=1.0)
    net.train()


def train(args) -> None:
    from app.ml.sr.arch import RRDBNet, UNetDiscriminatorSN
    from app.ml.sr.data import SRTrainDataset, load_validation_pairs
    from app.ml.sr.losses import VGGPerceptualLoss

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model_dir = args.base_dir / "models" / args.run_name
    results_dir = args.base_dir / "results" / args.run_name
    if args.fresh:
        for target in (model_dir, results_dir):
            if target.exists():
                shutil.rmtree(target)
                print(f"removed {target}")
    model_dir.mkdir(parents=True, exist_ok=True)
    results_dir.mkdir(parents=True, exist_ok=True)

    dataset = SRTrainDataset(args.images_dir, patch_size=args.patch_size, scale=args.scale)
    total_steps = args.steps_psnr + args.steps_gan
    epochs = total_steps * args.batch_size / len(dataset)
    print(f"training on {len(dataset):,} images from {[str(d) for d in args.images_dir]}")
    print(f"{args.scale}x  HR patch {args.patch_size}px  batch {args.batch_size}  "
          f"RRDB blocks {args.num_block}  amp={args.amp}  device={device}")
    print(f"=> {args.steps_psnr:,} PSNR steps + {args.steps_gan:,} GAN steps "
          f"= {total_steps * args.batch_size:,} patches, {epochs:.2f} passes over the images")

    loader = DataLoader(dataset, batch_size=args.batch_size, shuffle=True, drop_last=True,
                        num_workers=args.num_workers, pin_memory=device.type == "cuda",
                        persistent_workers=args.num_workers > 0)
    batches = _infinite(loader)
    val_pairs = load_validation_pairs(args.images_dir, args.scale, args.val_count)
    print(f"validation: {len(val_pairs)} held-out images (never trained on)\n")

    arch_config = {"scale": args.scale, "num_feat": args.num_feat, "num_block": args.num_block}
    net_g = RRDBNet(**arch_config).to(device)
    net_d = UNetDiscriminatorSN().to(device)
    net_g_ema = copy.deepcopy(net_g).eval()
    for p in net_g_ema.parameters():
        p.requires_grad_(False)
    perceptual = VGGPerceptualLoss().to(device)

    opt_g = torch.optim.Adam(net_g.parameters(), lr=args.lr_psnr, betas=(0.9, 0.99))
    opt_d = torch.optim.Adam(net_d.parameters(), lr=args.lr_d, betas=(0.9, 0.99))

    start_step = 0
    latest = model_dir / "latest.pt"
    if args.resume:
        if not latest.exists():
            raise SystemExit(f"--resume given but {latest} does not exist")
        state = torch.load(latest, map_location=device, weights_only=False)
        if state["arch_config"] != arch_config:
            raise SystemExit(f"architecture mismatch: checkpoint {state['arch_config']} vs args {arch_config}")
        net_g.load_state_dict(state["net_g"])
        net_g_ema.load_state_dict(state["net_g_ema"])
        net_d.load_state_dict(state["net_d"])
        opt_g.load_state_dict(state["opt_g"])
        opt_d.load_state_dict(state["opt_d"])
        start_step = state["step"]
        print(f"resumed at step {start_step}\n")

    metrics_path = results_dir / "metrics.csv"
    if not metrics_path.exists():
        base = bicubic_baseline(val_pairs, perceptual, device)
        with metrics_path.open("w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["step", "phase", "psnr", "ssim", "vgg_distance"])
            writer.writerow(["bicubic", "baseline", f"{base['psnr']:.3f}", f"{base['ssim']:.4f}", f"{base['vgg']:.4f}"])
        print(f"bicubic baseline: PSNR {base['psnr']:.2f}  SSIM {base['ssim']:.4f}  VGG {base['vgg']:.4f}")

    use_amp = args.amp and device.type == "cuda"
    net_g.train()
    net_d.train()
    t0, last_log = time.time(), start_step

    for step in range(start_step + 1, total_steps + 1):
        gan_phase = step > args.steps_psnr
        if step == args.steps_psnr + 1:
            for group in opt_g.param_groups:
                group["lr"] = args.lr_gan
            print(f"--- step {step}: entering GAN phase (lr_g {args.lr_gan}) ---", flush=True)

        lr_img, hr_img = next(batches)
        lr_img = lr_img.to(device, non_blocking=True)
        hr_img = hr_img.to(device, non_blocking=True)

        # --- generator ---
        for p in net_d.parameters():
            p.requires_grad_(False)
        with torch.autocast("cuda", dtype=torch.bfloat16, enabled=use_amp):
            out = net_g(lr_img)
            l_pix = F.l1_loss(out.float(), hr_img)
            if gan_phase:
                l_percep = perceptual(out.float(), hr_img)
                fake_logits = net_d(out)
                l_gan = F.binary_cross_entropy_with_logits(fake_logits.float(), torch.ones_like(fake_logits, dtype=torch.float32))
                loss_g = args.w_pix * l_pix + args.w_percep * l_percep + args.w_gan * l_gan
            else:
                loss_g = l_pix
        opt_g.zero_grad(set_to_none=True)
        loss_g.backward()
        opt_g.step()

        # --- discriminator ---
        loss_d = torch.tensor(0.0)
        if gan_phase:
            for p in net_d.parameters():
                p.requires_grad_(True)
            with torch.autocast("cuda", dtype=torch.bfloat16, enabled=use_amp):
                real_logits = net_d(hr_img).float()
                fake_logits = net_d(out.detach()).float()
                loss_d = (F.binary_cross_entropy_with_logits(real_logits, torch.ones_like(real_logits))
                          + F.binary_cross_entropy_with_logits(fake_logits, torch.zeros_like(fake_logits)))
            opt_d.zero_grad(set_to_none=True)
            loss_d.backward()
            opt_d.step()

        _update_ema(net_g_ema, net_g, args.ema_decay)

        g_val, d_val = loss_g.item(), loss_d.item()
        if not (math.isfinite(g_val) and math.isfinite(d_val)):
            # Fail in seconds rather than burn hours on NaNs; saved checkpoints stay usable.
            raise SystemExit(f"non-finite loss at step {step} (g={g_val}, d={d_val}); aborting")

        if step % args.log_every == 0:
            sps = (time.time() - t0) / (step - last_log)
            eta_h = sps * (total_steps - step) / 3600
            msg = f"step {step}/{total_steps}  {'gan ' if gan_phase else 'psnr'}  l_pix={l_pix.item():.4f}"
            if gan_phase:
                msg += f"  l_percep={l_percep.item():.4f}  l_gan={l_gan.item():.4f}  l_d={d_val:.4f}"
            vram = f"  vram {torch.cuda.max_memory_allocated() / 1e9:.1f}GB" if device.type == "cuda" else ""
            print(f"{msg}  {sps:.3f} s/step{vram}  eta {eta_h:.1f}h", flush=True)
            t0, last_log = time.time(), step

        if step % args.eval_every == 0 or step == total_steps:
            m = evaluate(net_g_ema, val_pairs, perceptual, device, args.amp)
            with metrics_path.open("a", newline="") as f:
                csv.writer(f).writerow([step, "gan" if gan_phase else "psnr",
                                        f"{m['psnr']:.3f}", f"{m['ssim']:.4f}", f"{m['vgg']:.4f}"])
            save_samples(net_g_ema, val_pairs, results_dir / f"samples_{step:06d}.png", device, args.amp)
            print(f"  [eval] step {step}: PSNR {m['psnr']:.2f}  SSIM {m['ssim']:.4f}  VGG {m['vgg']:.4f}", flush=True)

        if step % args.save_every == 0 or step == total_steps:
            torch.save({"arch_config": arch_config, "state_dict": net_g_ema.state_dict(), "step": step},
                       model_dir / f"net_g_ema_{step:06d}.pt")
            torch.save({"arch_config": arch_config, "step": step, "net_g": net_g.state_dict(),
                        "net_g_ema": net_g_ema.state_dict(), "net_d": net_d.state_dict(),
                        "opt_g": opt_g.state_dict(), "opt_d": opt_d.state_dict()}, latest)

    print(f"\ndone. weights in {model_dir}\nmetrics and sample grids in {results_dir}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--images-dir", type=Path, action="append", required=True,
                        help="Folder of high-res images; repeat to train on several folders")
    parser.add_argument("--run-name", default="shoes512")
    parser.add_argument("--base-dir", type=Path, default=DEFAULT_BASE_DIR)
    parser.add_argument("--scale", type=int, default=2, choices=(2, 4))
    parser.add_argument("--num-feat", type=int, default=64)
    parser.add_argument("--num-block", type=int, default=16, help="RRDB blocks (ESRGAN uses 23; 16 trains faster on 6GB)")
    parser.add_argument("--patch-size", type=int, default=128, help="HR crop size; multiple of 8*scale")
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--steps-psnr", type=int, default=20000)
    parser.add_argument("--steps-gan", type=int, default=40000)
    parser.add_argument("--lr-psnr", type=float, default=2e-4)
    parser.add_argument("--lr-gan", type=float, default=1e-4)
    parser.add_argument("--lr-d", type=float, default=1e-4)
    parser.add_argument("--w-pix", type=float, default=1.0)
    parser.add_argument("--w-percep", type=float, default=1.0)
    parser.add_argument("--w-gan", type=float, default=0.1)
    parser.add_argument("--ema-decay", type=float, default=0.999)
    parser.add_argument("--num-workers", type=int, default=4,
                        help="JPEG decode + degradation run here; too few and the GPU waits on the CPU")
    parser.add_argument("--amp", action="store_true", help="bfloat16 mixed precision: less VRAM, faster")
    parser.add_argument("--val-count", type=int, default=100)
    parser.add_argument("--log-every", type=int, default=100)
    parser.add_argument("--eval-every", type=int, default=2500)
    parser.add_argument("--save-every", type=int, default=5000)
    parser.add_argument("--resume", action="store_true", help="Continue from models/<run>/latest.pt")
    parser.add_argument("--fresh", action="store_true", help="Delete any existing run of this name first")
    args = parser.parse_args()

    if args.resume and args.fresh:
        parser.error("--resume and --fresh are mutually exclusive")
    if not torch.cuda.is_available():
        print("WARNING: no CUDA device found; this will be extremely slow on CPU", file=sys.stderr)
    train(args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
