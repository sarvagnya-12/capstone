"""Add image columns to products.csv so Stage 2 can find anything to process.

Stage 1's exported products.csv contains NO image column. That is not an
oversight to work around in Stage 1: NormalizedProduct has no image_url field at
all, and CatalogExporter writes a fixed column set taken from
schemas/products_schema.json, which has no image column either. RawProduct does
carry image_url, but normalization drops it.

Stage 2, meanwhile, reads the products CSV with a plain dict reader (it only
checks that schema-required columns are present, and does not strip extras) and
looks for any of asset_manager's configured image_url_columns:
    image_url, original_image_url, primary_image_url, asset_url
Pointing Stage 2 at products.csv verbatim therefore finds zero image references
and downloads nothing.

This script rebuilds that link: it joins the catalog against the per-colorway
image manifest written by convert_utzap50k_metadata.py (on source +
source_product_id) and emits products_with_images.csv -- every original column,
plus up to four colorway images spread across those four column names.

WHY ONLY FOUR: the asset manager supports exactly four image columns, so a
product with more colorways contributes its first four. That covers all but
~1,300 of the 24,522 Zappos products (which average ~2 colorways), retaining
roughly 46k of the 50,025 images. Amazon products get no images by design --
see prepare_amazon_catalog_rows.py.

Usage:
    python _ingestion_tools/prepare_asset_manager_input.py
"""

from __future__ import annotations

import argparse
import csv
import sys
from collections import defaultdict
from pathlib import Path

csv.field_size_limit(10_000_000)

IMAGE_COLUMNS = ["image_url", "original_image_url", "primary_image_url", "asset_url"]


def latest_catalog_dir(versions_dir: Path) -> Path:
    candidates = [
        path
        for path in versions_dir.glob("catalog_v*")
        if path.is_dir() and path.name.removeprefix("catalog_v").isdigit()
    ]
    if not candidates:
        raise SystemExit(f"No catalog_v* directory under {versions_dir}. Run the catalog build first.")
    return max(candidates, key=lambda p: int(p.name.removeprefix("catalog_v")))


def load_manifest(manifest_csv: Path) -> dict[tuple[str, str], list[str]]:
    images: dict[tuple[str, str], list[str]] = defaultdict(list)
    if not manifest_csv.exists():
        raise SystemExit(f"Missing image manifest: {manifest_csv}")
    with manifest_csv.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            key = ((row.get("source") or "").strip().lower(), (row.get("source_product_id") or "").strip())
            path = (row.get("image_path") or "").strip()
            if key[1] and path:
                images[key].append(path)
    return images


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--catalog-dir", type=Path, default=None)
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    catalog_dir = args.catalog_dir or latest_catalog_dir(root / "datasets" / "versions")
    products_csv = catalog_dir / "products.csv"
    output_csv = catalog_dir / "products_with_images.csv"
    manifest = load_manifest(root / "datasets" / "raw" / "zappos" / "zappos_image_manifest.csv")

    with products_csv.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        raise SystemExit(f"No rows in {products_csv}")

    fieldnames = list(rows[0].keys()) + [c for c in IMAGE_COLUMNS if c not in rows[0]]
    with_images = 0
    attached = 0

    with output_csv.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            key = ((row.get("source") or "").strip().lower(), (row.get("source_product_id") or "").strip())
            paths = manifest.get(key, [])
            for index, column in enumerate(IMAGE_COLUMNS):
                row[column] = paths[index] if index < len(paths) else ""
            if paths:
                with_images += 1
                attached += min(len(paths), len(IMAGE_COLUMNS))
            writer.writerow(row)

    print(f"catalog rows      : {len(rows):,}")
    print(f"rows with images  : {with_images:,}")
    print(f"images attached   : {attached:,}")
    print(f"written           : {output_csv}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
