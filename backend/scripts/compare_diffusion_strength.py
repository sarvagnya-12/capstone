"""Does the GAN concept help or hurt once a diffusion model renders it?

For real products (held-out 512px photos from the SR corpus, described by
their own Amazon titles so photo and text agree), the real FastGAN proposes
concepts exactly as the hybrid pipeline does (oversample, keep the closest
silhouettes), and the configured image provider renders each one:

  seed@<s>   init = GAN concept, reference = product photo, at strength s
  photo      init = product photo (DIFFUSION_INIT=product), no GAN shape

Scores (rough, automatic -- the grids are the real evidence):
  shape_vs_seed     outline similarity to the GAN concept (higher = the GAN's
                    shape survived, including its malformations)
  shape_vs_product  outline similarity to the product photo
  look_vs_product   VGG19 feature cosine similarity to the product photo
                    (higher = resembles the actual product)
  flagged / failed  renders refused by the provider's safety filter / errors

Usage:
    cd backend
    .venv\\Scripts\\python.exe scripts\\compare_diffusion_strength.py \\
        --images-dir "<sr_training_images_512>" --meta "<amazon_meta_footwear.jsonl>"
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path

import numpy as np
import torch
from PIL import Image, ImageDraw

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.core.config import settings  # noqa: E402
from app.ml.diffusion.hybrid import build_render_prompt, select_seeds  # noqa: E402
from app.ml.diffusion.provider import CloudflareImageProvider, ImageProviderError, get_image_provider  # noqa: E402
from app.ml.gan.inference import generate_variants  # noqa: E402
from app.ml.sr.data import is_validation_file  # noqa: E402

# One product per shoe type, so the result is not about a single silhouette.
KINDS = {"running": ("running", "runner", "trail"), "sneaker": ("sneaker",), "boot": ("boot",),
         "sandal": ("sandal",), "loafer": ("loafer", "oxford", "slip-on")}
TILE = 220


def load_products(images_dir: Path, meta_path: Path, count: int) -> list[dict]:
    wanted = {p.stem: p for p in images_dir.glob("*.jpg") if is_validation_file(p)}
    chosen, kinds_left = [], list(KINDS)[:count]
    with meta_path.open(encoding="utf-8") as handle:
        for line in handle:
            record = json.loads(line)
            asin = record.get("parent_asin")
            if asin not in wanted:
                continue
            title = (record.get("title") or "").lower()
            kind = next((k for k in kinds_left if any(word in title for word in KINDS[k])), None)
            if kind is None:
                continue
            categories = record.get("categories") or []
            chosen.append({"asin": asin, "kind": kind, "path": wanted[asin], "title": record["title"],
                           "brand": record.get("store"),
                           "category": categories[-1] if categories else kind})
            kinds_left.remove(kind)
            if not kinds_left:
                break
    return chosen


class VGGFeatures:
    def __init__(self):
        from torchvision.models import VGG19_Weights, vgg19

        model = vgg19(weights=VGG19_Weights.IMAGENET1K_V1).eval()
        model.classifier = model.classifier[:-1]  # 4096-d penultimate features
        self.model = model.cuda() if torch.cuda.is_available() else model
        self.mean = torch.tensor([0.485, 0.456, 0.406]).view(3, 1, 1)
        self.std = torch.tensor([0.229, 0.224, 0.225]).view(3, 1, 1)

    @torch.no_grad()
    def __call__(self, img: Image.Image) -> np.ndarray:
        t = torch.from_numpy(np.asarray(img.convert("RGB").resize((224, 224)), dtype=np.float32) / 255).permute(2, 0, 1)
        t = ((t - self.mean) / self.std).unsqueeze(0).to(next(self.model.parameters()).device)
        f = self.model(t)[0].float().cpu().numpy()
        return f / (np.linalg.norm(f) or 1.0)


def silhouette(img: Image.Image) -> np.ndarray:
    """Foreground mask at 64px: product photos are on white, so 'not near-white'
    is the shoe. Compared with IoU, which ignores colour and texture."""
    gray = np.asarray(img.convert("L").resize((64, 64)), dtype=np.float32)
    return gray < 235


def iou(a: np.ndarray, b: np.ndarray) -> float:
    union = np.logical_or(a, b).sum()
    return float(np.logical_and(a, b).sum() / union) if union else 0.0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--images-dir", required=True, type=Path)
    parser.add_argument("--meta", required=True, type=Path)
    parser.add_argument("--products", type=int, default=4)
    parser.add_argument("--seeds", type=int, default=5, help="GAN concepts per product")
    parser.add_argument("--strengths", default="0.3,0.55,0.85")
    parser.add_argument("--output-size", type=int, default=512)
    parser.add_argument("--out", type=Path, default=BACKEND_ROOT / "storage" / "diffusion_eval")
    args = parser.parse_args()
    strengths = [float(s) for s in args.strengths.split(",")]

    provider = get_image_provider()
    if isinstance(provider, CloudflareImageProvider):
        provider._output_size = args.output_size
    products = load_products(args.images_dir, args.meta, args.products)
    out_dir = args.out / datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir.mkdir(parents=True, exist_ok=True)
    vgg = VGGFeatures()
    conditions = [f"seed@{s}" for s in strengths] + ["photo"]
    print(f"provider {type(provider).__name__}, {args.output_size}px; {len(products)} products x "
          f"{args.seeds} concepts x {len(conditions)} conditions = {len(products) * args.seeds * len(conditions)} renders\n")

    rows, started = [], time.time()
    for product in products:
        photo = Image.open(product["path"]).convert("RGB")
        photo_256 = photo.resize((256, 256))
        candidates = generate_variants(product["asin"], args.seeds * settings.GAN_OVERSAMPLE, apply_hue_shift=False)
        seeds = select_seeds(candidates, photo_256, args.seeds)
        photo_sil, photo_feat = silhouette(photo), vgg(photo)
        grid_rows = []
        print(f"{product['kind']:<8} {product['title'][:70]}", flush=True)
        for index, seed in enumerate(seeds):
            hue = seed.attributes["color_hue_shift_degrees"]
            prompt = build_render_prompt(product["title"], product["category"], None, product["brand"], hue)
            seed_sil = silhouette(seed.image)
            tiles = [seed.image]
            for condition in conditions:
                init, ref = (photo, None) if condition == "photo" else (seed.image, photo)
                strength = 0.55 if condition == "photo" else float(condition.split("@")[1])
                row = {"product": product["asin"], "kind": product["kind"], "concept": index, "condition": condition}
                try:
                    img = provider.render(init, prompt, strength, seed=1000 + index, reference_image=ref)
                    sil = silhouette(img)
                    row.update(ok=True, shape_vs_seed=iou(sil, seed_sil), shape_vs_product=iou(sil, photo_sil),
                               look_vs_product=float(vgg(img) @ photo_feat))
                    img.save(out_dir / f"{product['asin']}_{index}_{condition.replace('@', '_')}.jpg")
                    tiles.append(img)
                except ImageProviderError as e:
                    row.update(ok=False, flagged="flagged" in str(e), error=str(e)[:200])
                    tiles.append(None)
                rows.append(row)
            tiles.append(photo)
            grid_rows.append(tiles)
        save_grid(grid_rows, ["GAN concept"] + conditions + ["product photo"], out_dir / f"grid_{product['kind']}.jpg")
        print(f"         done ({time.time() - started:.0f}s elapsed)", flush=True)

    summary = {}
    for condition in conditions:
        group = [r for r in rows if r["condition"] == condition]
        ok = [r for r in group if r["ok"]]
        summary[condition] = {
            "rendered": len(ok), "flagged": sum(1 for r in group if not r["ok"] and r.get("flagged")),
            "failed": sum(1 for r in group if not r["ok"] and not r.get("flagged")),
            **{k: round(float(np.mean([r[k] for r in ok])), 3) if ok else None
               for k in ("shape_vs_seed", "shape_vs_product", "look_vs_product")},
        }
    (out_dir / "results.json").write_text(json.dumps({"products": [{k: str(v) for k, v in p.items()} for p in products],
                                                      "summary": summary, "rows": rows}, indent=2))
    header = f"{'condition':<12}{'ok':>4}{'flag':>6}{'fail':>6}{'shape~GAN':>11}{'shape~photo':>13}{'look~photo':>12}"
    print("\n" + header)
    for c, s in summary.items():
        fmt = lambda v: f"{v:.3f}" if v is not None else "-"  # noqa: E731
        print(f"{c:<12}{s['rendered']:>4}{s['flagged']:>6}{s['failed']:>6}{fmt(s['shape_vs_seed']):>11}"
              f"{fmt(s['shape_vs_product']):>13}{fmt(s['look_vs_product']):>12}")
    print(f"\ngrids and images: {out_dir}")
    return 0


def save_grid(rows, labels, path: Path) -> None:
    cols = len(labels)
    grid = Image.new("RGB", (cols * (TILE + 4), 20 + len(rows) * (TILE + 4)), "white")
    draw = ImageDraw.Draw(grid)
    for c, label in enumerate(labels):
        draw.text((c * (TILE + 4) + 4, 4), label, fill="black")
    for r, tiles in enumerate(rows):
        for c, tile in enumerate(tiles):
            x, y = c * (TILE + 4), 20 + r * (TILE + 4)
            if tile is None:
                draw.rectangle((x, y, x + TILE, y + TILE), fill=(235, 235, 235))
                draw.text((x + 70, y + TILE // 2), "flagged / failed", fill="red")
            else:
                grid.paste(tile.convert("RGB").resize((TILE, TILE)), (x, y))
    grid.save(path, quality=90)


if __name__ == "__main__":
    sys.exit(main())
