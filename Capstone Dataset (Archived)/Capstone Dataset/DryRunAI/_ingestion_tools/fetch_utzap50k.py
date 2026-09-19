"""Download and extract the UT-Zappos50K dataset (Stage 1/2 source data).

UT-Zappos50K is 50,025 Zappos.com catalog shoe images plus per-shoe enum
metadata. It is the dataset the pipeline's existing ZapposCollector and README
were always written against.

LICENSE: non-commercial / academic use only (per the dataset's own readme.txt
and Yu & Grauman, CVPR 2014). This project is an academic capstone, which is
within those terms. Cite the paper in any publication.

Downloads:
    ut-zap50k-data.zip    (~3MB)   -> meta-data.csv, image-path.mat, labels
    ut-zap50k-images.zip  (~291MB) -> the 50,025 images in a nested tree

Both are skipped if already present and complete, so re-running is cheap.

Usage:
    python _ingestion_tools/fetch_utzap50k.py
    python _ingestion_tools/fetch_utzap50k.py --dest datasets/raw/zappos
"""

from __future__ import annotations

import argparse
import sys
import zipfile
from pathlib import Path

import requests
from tqdm import tqdm

BASE_URL = "https://vision.cs.utexas.edu/projects/finegrained/utzap50k"
ARCHIVES = {
    "ut-zap50k-data.zip": "metadata, image paths, attribute labels",
    "ut-zap50k-images.zip": "50,025 shoe images",
}
CHUNK = 1 << 20


def download(url: str, target: Path) -> None:
    head = requests.head(url, timeout=30, allow_redirects=True)
    head.raise_for_status()
    expected = int(head.headers.get("content-length", 0))

    if target.exists() and expected and target.stat().st_size == expected:
        print(f"[skip] {target.name} already downloaded ({expected:,} bytes)")
        return

    print(f"[get ] {url}")
    with requests.get(url, stream=True, timeout=60) as response:
        response.raise_for_status()
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("wb") as handle, tqdm(
            total=expected or None, unit="B", unit_scale=True, desc=target.name
        ) as bar:
            for chunk in response.iter_content(chunk_size=CHUNK):
                handle.write(chunk)
                bar.update(len(chunk))

    size = target.stat().st_size
    if expected and size != expected:
        target.unlink()
        raise RuntimeError(f"{target.name}: expected {expected:,} bytes, got {size:,} -- deleted partial file")


def extract(archive: Path, dest: Path) -> None:
    with zipfile.ZipFile(archive) as zf:
        members = zf.namelist()
        # Cheap completeness check: if every top-level entry already exists,
        # treat the archive as extracted rather than rewriting ~50k files.
        roots = {Path(m).parts[0] for m in members if m.strip()}
        if roots and all((dest / root).exists() for root in roots):
            print(f"[skip] {archive.name} already extracted into {dest}")
            return
        print(f"[unzip] {archive.name} -> {dest} ({len(members):,} entries)")
        dest.mkdir(parents=True, exist_ok=True)
        for member in tqdm(members, unit="file", desc=f"extract {archive.name}"):
            zf.extract(member, dest)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--dest",
        default="datasets/raw/zappos",
        help="Destination directory, relative to the pipeline root (default: datasets/raw/zappos)",
    )
    args = parser.parse_args()

    pipeline_root = Path(__file__).resolve().parents[1]
    dest = (pipeline_root / args.dest).resolve()
    downloads = dest / "_downloads"

    for name, description in ARCHIVES.items():
        print(f"\n=== {name} -- {description} ===")
        archive = downloads / name
        download(f"{BASE_URL}/{name}", archive)
        extract(archive, dest)

    print(f"\nDone. UT-Zappos50K extracted under: {dest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
