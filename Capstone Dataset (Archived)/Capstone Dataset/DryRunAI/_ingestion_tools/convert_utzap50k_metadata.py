"""Convert extracted UT-Zappos50K into the CSV shape ZapposCollector expects.

Two things the dataset's own readme.txt does not spell out, both established by
inspecting the extracted tree directly:

1. BRAND LIVES IN THE DIRECTORY PATH, NOT THE METADATA CSV.
   meta-data.csv has no brand column at all, but every image sits at exactly
   Category/SubCategory/Brand/ProductID.ColorID.jpg (verified: all 50,025 images
   are at that same depth). Brand is therefore recovered from the path.

2. CID IN meta-data.csv IS "ProductID-ColorID"; THE FILENAME USES A DOT.
   e.g. image 8045627.325.jpg <-> CID 8045627-325. Joining on that mapping
   matches 50,024 of 50,025 images.

PRODUCT GRANULARITY: one row per ProductID, not per image. The dataset ships
~2.04 images per ProductID because the same shoe is photographed in several
colorways ("There can be several shoes of the same kind (same ProductID) but in
different colors" -- readme.txt). Collapsing colorways here, deterministically
on the authoritative Zappos ProductID, is both semantically right and safer than
letting the fuzzy duplicate matcher do it: UT-Zappos50K has no product names, so
every model string must be built from attributes plus the numeric ID, and two
genuinely different shoes of the same brand/category then score ~0.96 against
each other -- above the 0.92 merge threshold. Deterministic ID-based collapsing
avoids that false-merge class entirely. The per-colorway images are not lost;
they go to the image manifest for Stage 2.

COLUMN NAME GOTCHA (found by testing, not by reading): the catalog CSV's
identifier column must be named "id" -- ZapposCollector.FIELD_ALIASES maps its
internal "source_product_id" field to CSV columns named
("id", "product_id", "asin", "sku", "filename", "image", "image_path"), which
does NOT include a column literally called "source_product_id". Naming it that
(an earlier version of this script did) silently falls through to the
collector's index-based fallback ("zappos-row-1", "zappos-row-2", ...) instead
of the real Zappos ProductID, breaking every downstream join that depends on
the true ID. The image manifest CSV (this script's second output) is a
different, our-own-schema file and correctly keeps the column named
"source_product_id" there -- only the catalog CSV that ZapposCollector itself
parses needs the "id" spelling.

Outputs:
  datasets/raw/zappos/zappos_utzap50k.csv       -> Stage 1 catalog input
  datasets/raw/zappos/zappos_image_manifest.csv -> Stage 2 image bridge input

Usage:
    python _ingestion_tools/convert_utzap50k_metadata.py
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import defaultdict
from pathlib import Path

CATALOG_COLUMNS = [
    "id",
    "name",
    "brand",
    "category",
    "subcategory",
    "gender",
    "material",
    "description",
    "image_url",
]
MANIFEST_COLUMNS = ["source", "source_product_id", "colorway_id", "image_path"]


def load_metadata(data_dir: Path) -> dict[str, dict]:
    path = data_dir / "meta-data.csv"
    rows: dict[str, dict] = {}
    with path.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            cid = (row.get("CID") or "").strip()
            if cid:
                rows[cid] = row
    return rows


def _describe(meta: dict) -> str:
    """Build a description from the real attribute labels, nothing invented."""
    parts = []
    for label in ("HeelHeight", "Insole", "Closure", "Material", "ToeStyle"):
        value = (meta.get(label) or "").strip()
        if value:
            parts.append(f"{label}: {value}")
    return "; ".join(parts)


def convert(root: Path) -> dict:
    zappos_dir = root / "datasets" / "raw" / "zappos"
    images_dir = zappos_dir / "ut-zap50k-images"
    data_dir = zappos_dir / "ut-zap50k-data"

    if not images_dir.is_dir() or not data_dir.is_dir():
        raise SystemExit(f"UT-Zappos50K not found under {zappos_dir}. Run fetch_utzap50k.py first.")

    metadata = load_metadata(data_dir)
    grouped: dict[str, list[tuple[str, Path, tuple[str, ...]]]] = defaultdict(list)
    unmatched_cids = 0

    for image_path in images_dir.rglob("*.jpg"):
        relative = image_path.relative_to(images_dir)
        if len(relative.parts) != 4:
            continue
        category_dir, subcategory_dir, brand_dir, filename = relative.parts
        stem = Path(filename).stem
        product_id, _, colorway_id = stem.partition(".")
        cid = stem.replace(".", "-")
        if cid not in metadata:
            unmatched_cids += 1
        grouped[product_id].append((cid, image_path, (category_dir, subcategory_dir, brand_dir, colorway_id)))

    catalog_path = zappos_dir / "zappos_utzap50k.csv"
    manifest_path = zappos_dir / "zappos_image_manifest.csv"

    with catalog_path.open("w", encoding="utf-8", newline="") as catalog_handle, manifest_path.open(
        "w", encoding="utf-8", newline=""
    ) as manifest_handle:
        catalog = csv.DictWriter(catalog_handle, fieldnames=CATALOG_COLUMNS)
        manifest = csv.DictWriter(manifest_handle, fieldnames=MANIFEST_COLUMNS)
        catalog.writeheader()
        manifest.writeheader()

        for product_id, entries in sorted(grouped.items()):
            entries.sort(key=lambda item: item[0])
            cid, first_image, (category_dir, subcategory_dir, brand_dir, _) = entries[0]
            meta = metadata.get(cid, {})

            category = (meta.get("Category") or category_dir).strip()
            subcategory = (meta.get("SubCategory") or subcategory_dir).strip()
            brand = brand_dir.strip()

            catalog.writerow(
                {
                    "id": product_id,
                    # No product names exist in this dataset; the model name is
                    # built from subcategory + the authoritative Zappos ProductID.
                    "name": f"{brand} {subcategory} {product_id}".strip(),
                    "brand": brand,
                    "category": category,
                    "subcategory": subcategory,
                    "gender": (meta.get("Gender") or "").strip(),
                    "material": (meta.get("Material") or "").strip(),
                    "description": _describe(meta),
                    "image_url": str(first_image.resolve()),
                }
            )

            for entry_cid, image_path, (_, _, _, colorway_id) in entries:
                manifest.writerow(
                    {
                        "source": "zappos",
                        "source_product_id": product_id,
                        "colorway_id": colorway_id or entry_cid,
                        "image_path": str(image_path.resolve()),
                    }
                )

    total_images = sum(len(v) for v in grouped.values())
    stats = {
        "images_found": total_images,
        "distinct_products": len(grouped),
        "images_per_product": round(total_images / len(grouped), 2) if grouped else 0,
        "images_without_metadata_row": unmatched_cids,
        "catalog_csv": str(catalog_path),
        "image_manifest_csv": str(manifest_path),
    }
    (zappos_dir / "conversion_report.json").write_text(json.dumps(stats, indent=2), encoding="utf-8")
    return stats


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.parse_args()
    stats = convert(Path(__file__).resolve().parents[1])
    for key, value in stats.items():
        print(f"  {key}: {value}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
