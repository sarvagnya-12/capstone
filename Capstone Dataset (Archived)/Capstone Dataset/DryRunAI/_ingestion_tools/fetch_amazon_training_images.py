"""Download real high-resolution product photos for GAN fine-tuning (Step 17).

WHY THIS EXISTS, given the pipeline deliberately collects no Amazon images:
the ETL pipeline's image corpus comes from UT-Zappos50K, whose catalog photos
are 136x102 thumbnails. That is fine for the reference dataset, but useless as
StyleGAN2 training data -- the checkpoint is 512x512, so those images would
have to be upscaled 4x and the generator would learn to reproduce blur. The
Amazon metadata already on disk carries hi_res URLs (~1500px), which downscale
to 512 instead, preserving detail. This is a training corpus, not part of the
dataset pipeline's own outputs, so it writes outside datasets/.

Non-square photos are PADDED to square with white, not cropped. Amazon product
shots are overwhelmingly wide (1500x994, 1500x777, ...) on a pure white
background -- verified by sampling: 25 of 25 images had all four corners at
exactly (255,255,255). Centre-cropping those to a square cut the toe and heel
off the shoe, and an earlier aspect-ratio filter rejected 39 of 60 candidates
for the same reason. Padding keeps the whole product, adds background that is
indistinguishable from the real background, and accepts nearly everything.

Output:
  _ingestion_tools/gan_training_images/<parent_asin>.jpg  (512x512, RGB)

Usage:
    python _ingestion_tools/fetch_amazon_training_images.py --count 25000
"""

from __future__ import annotations

import argparse
import io
import json
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import requests
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
META = ROOT / "datasets" / "raw" / "amazon" / "amazon_meta_footwear.jsonl"
OUT_DIR = Path(__file__).resolve().parent / "gan_training_images"

# 256, not 512: app/ml/gan/model.py downsamples every generated image to
# image_preprocessing.TARGET_SIZE (256x256) before anything downstream uses it,
# so training at 512 discards half the resolution immediately while costing ~4x
# the compute per step. Sources are ~1500px, so this is still a downscale --
# the point is never to upscale, which would teach the generator to make blur.
TARGET_SIZE = 256
# Padding handles ordinary wide product shots, so this only rejects genuinely
# banner-shaped images, where the product would end up a thin strip of a mostly
# blank square.
MAX_ASPECT_RATIO = 2.5
# Long edge must clear this, since the long edge is what gets scaled to 512;
# anything smaller would be scaled up and reintroduce the blur this whole
# script exists to avoid.
MIN_SOURCE_LONG_EDGE = 256
USER_AGENT = "DryRunAI-Capstone/1.0 (academic research project)"


def candidate_urls(limit: int) -> list[tuple[str, str]]:
    """(asin, url) for products with a hi_res image, one image per product so
    the corpus is diverse across products rather than many angles of a few."""
    out: list[tuple[str, str]] = []
    with META.open(encoding="utf-8") as handle:
        for line in handle:
            record = json.loads(line)
            for image in record.get("images") or []:
                url = image.get("hi_res")
                if url:
                    out.append((record.get("parent_asin") or f"row{len(out)}", url))
                    break
            if len(out) >= limit:
                break
    return out


def fetch_one(asin: str, url: str, session: requests.Session) -> str | None:
    try:
        response = session.get(url, timeout=30)
        response.raise_for_status()
        image = Image.open(io.BytesIO(response.content)).convert("RGB")
    except (requests.RequestException, OSError):
        return None

    width, height = image.size
    if max(width, height) < MIN_SOURCE_LONG_EDGE:
        return None
    if max(width, height) / min(width, height) > MAX_ASPECT_RATIO:
        return None

    # Scale the long edge to 512 preserving aspect ratio, then paste onto a
    # white 512x512 canvas. No stretching, no cropped-off toes, and the padding
    # matches the photos' own white background.
    scale = TARGET_SIZE / max(width, height)
    image = image.resize((max(1, round(width * scale)), max(1, round(height * scale))), Image.LANCZOS)
    canvas = Image.new("RGB", (TARGET_SIZE, TARGET_SIZE), (255, 255, 255))
    canvas.paste(image, ((TARGET_SIZE - image.width) // 2, (TARGET_SIZE - image.height) // 2))
    canvas.save(OUT_DIR / f"{asin}.jpg", quality=95)
    return asin


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--count", type=int, default=25000, help="How many images to end up with")
    parser.add_argument("--workers", type=int, default=16, help="Concurrent downloads")
    args = parser.parse_args()

    if not META.exists():
        raise SystemExit(f"Amazon metadata not found at {META}")
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    # Over-fetch: some URLs 404, some images fail the aspect/size filters.
    candidates = candidate_urls(int(args.count * 1.25))
    print(f"{len(candidates)} candidate URLs for a target of {args.count} images")

    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})

    saved = failed = 0
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(fetch_one, asin, url, session): asin for asin, url in candidates}
        for future in as_completed(futures):
            if future.result():
                saved += 1
                if saved % 250 == 0:
                    print(f"  {saved} saved")
                if saved >= args.count:
                    break
            else:
                failed += 1

        for future in futures:
            future.cancel()

    print(f"\nsaved {saved} images ({failed} skipped: failed download or filtered)")
    print(f"-> {OUT_DIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
