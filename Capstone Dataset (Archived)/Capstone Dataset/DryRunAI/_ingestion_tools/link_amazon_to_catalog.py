"""Attach catalog product IDs to Amazon reviews and market records.

Stages 3, 4 and 5 each reject any record whose product_id is empty, quarantining
it as `missing_product_id`. That rejection path is the honest-unmatched
behaviour this project wants, so this script fills in `dryrun_product_id` ONLY
where Stage 1 actually accepted a catalog product for that ASIN. Anything it
cannot resolve is left blank deliberately and is expected to be quarantined --
no ASIN is ever matched to a guessed product.

Resolution is exact, not fuzzy: Stage 1 has already done all fuzzy matching, and
its exported products.csv records the `source`/`source_product_id` that each
product came from. Amazon rows that Stage 1 folded into a Zappos product carry
that Zappos product's ID here automatically, because the merge assigned it.

Usage:
    python _ingestion_tools/link_amazon_to_catalog.py
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

csv.field_size_limit(10_000_000)


def latest_catalog(versions_dir: Path) -> Path:
    candidates = [
        path
        for path in versions_dir.glob("catalog_v*")
        if path.is_dir() and path.name.removeprefix("catalog_v").isdigit()
    ]
    if not candidates:
        raise SystemExit(f"No catalog_v* directory under {versions_dir}. Run the catalog build first.")
    newest = max(candidates, key=lambda p: int(p.name.removeprefix("catalog_v")))
    return newest / "products.csv"


def build_lookup(products_csv: Path) -> dict[str, str]:
    lookup: dict[str, str] = {}
    with products_csv.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            if (row.get("source") or "").strip().lower() != "amazon":
                continue
            asin = (row.get("source_product_id") or "").strip()
            product_id = (row.get("product_id") or "").strip()
            if asin and product_id:
                lookup[asin] = product_id
    return lookup


def link_reviews(path: Path, lookup: dict[str, str]) -> tuple[int, int]:
    if not path.exists():
        return 0, 0
    temp = path.with_suffix(path.suffix + ".tmp")
    linked = total = 0
    with path.open(encoding="utf-8") as source, temp.open("w", encoding="utf-8") as target:
        for line in source:
            if not line.strip():
                continue
            record = json.loads(line)
            total += 1
            product_id = lookup.get(record.get("parent_asin") or "")
            if product_id:
                record["dryrun_product_id"] = product_id
                linked += 1
            target.write(json.dumps(record, ensure_ascii=False) + "\n")
    temp.replace(path)
    return linked, total


def link_market(path: Path, lookup: dict[str, str]) -> tuple[int, int]:
    if not path.exists():
        return 0, 0
    with path.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        return 0, 0

    fieldnames = list(rows[0].keys())
    if "dryrun_product_id" not in fieldnames:
        fieldnames.append("dryrun_product_id")

    linked = 0
    for row in rows:
        product_id = lookup.get((row.get("source_product_id") or "").strip())
        row["dryrun_product_id"] = product_id or ""
        if product_id:
            linked += 1

    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return linked, len(rows)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--products", type=Path, default=None, help="products.csv (default: latest catalog version)")
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    products_csv = args.products or latest_catalog(root / "datasets" / "versions")
    lookup = build_lookup(products_csv)
    print(f"catalog: {products_csv}")
    print(f"amazon products in catalog: {len(lookup):,}")

    linked, total = link_reviews(root / "datasets" / "reviews" / "raw" / "amazon_reviews.jsonl", lookup)
    pct = (linked / total * 100) if total else 0
    print(f"reviews linked: {linked:,}/{total:,} ({pct:.1f}%) -- unlinked rows stay blank and will be quarantined")

    linked, total = link_market(root / "datasets" / "market" / "raw" / "amazon_market.csv", lookup)
    pct = (linked / total * 100) if total else 0
    print(f"market linked : {linked:,}/{total:,} ({pct:.1f}%)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
