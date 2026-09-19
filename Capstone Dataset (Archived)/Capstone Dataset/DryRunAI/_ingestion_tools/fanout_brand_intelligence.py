"""Expand brand-level facts into the per-product rows Stage 5 requires.

fetch_brand_intelligence.py produces one row per BRAND, but the Product
Intelligence service has no brand-level entity: IntelligenceValidator rejects
any record without a product_id, and Stage 6 groups intelligence onto products
by exact product_id. So brand facts have to be fanned out -- one row per
(brand fact x product of that brand).

Rows are only emitted for products whose brand actually has fetched facts;
products of any other brand get no intelligence record rather than an empty
one. The duplicate key the service computes is
(product_id, brand, campaign_name, source), which is unique per product here,
so the fan-out does not trip its duplicate detection.

Output:
  datasets/product_intelligence/raw/product_intelligence.csv

Usage:
    python _ingestion_tools/fanout_brand_intelligence.py
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

csv.field_size_limit(10_000_000)

OUTPUT_COLUMNS = [
    "intelligence_record_id",
    "dryrun_product_id",
    "brand",
    "source",
    "source_url",
    "brand_description",
    "tagline",
    "parent_company",
    "country_of_origin",
    "collected_at",
]


def latest_products_csv(versions_dir: Path) -> Path:
    candidates = [
        path for path in versions_dir.glob("catalog_v*") if path.is_dir() and path.name.removeprefix("catalog_v").isdigit()
    ]
    if not candidates:
        raise SystemExit(f"No catalog_v* directory under {versions_dir}. Run the catalog build first.")
    return max(candidates, key=lambda p: int(p.name.removeprefix("catalog_v"))) / "products.csv"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--products", type=Path, default=None)
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    products_csv = args.products or latest_products_csv(root / "datasets" / "versions")
    facts_csv = root / "datasets" / "product_intelligence" / "raw" / "brand_facts.csv"
    out_csv = root / "datasets" / "product_intelligence" / "raw" / "product_intelligence.csv"

    if not facts_csv.exists():
        raise SystemExit(f"Missing {facts_csv}. Run fetch_brand_intelligence.py first.")

    with facts_csv.open(encoding="utf-8-sig", newline="") as handle:
        facts = {(row.get("brand") or "").strip().lower(): row for row in csv.DictReader(handle)}
    print(f"brand facts loaded: {len(facts):,}")

    written = 0
    covered_brands: set[str] = set()

    with products_csv.open(encoding="utf-8-sig", newline="") as source, out_csv.open(
        "w", encoding="utf-8", newline=""
    ) as target:
        writer = csv.DictWriter(target, fieldnames=OUTPUT_COLUMNS)
        writer.writeheader()

        for index, product in enumerate(csv.DictReader(source), start=1):
            brand = (product.get("brand") or "").strip()
            fact = facts.get(brand.lower())
            if not fact:
                continue
            product_id = (product.get("product_id") or "").strip()
            if not product_id:
                continue

            writer.writerow(
                {
                    "intelligence_record_id": f"INTSRC-{index:07d}",
                    "dryrun_product_id": product_id,
                    "brand": brand,
                    "source": fact.get("source") or "wikipedia",
                    "source_url": fact.get("source_url", ""),
                    "brand_description": fact.get("brand_description", ""),
                    "tagline": fact.get("tagline", ""),
                    "parent_company": fact.get("parent_company", ""),
                    "country_of_origin": fact.get("country_of_origin", ""),
                    "collected_at": fact.get("collected_at", ""),
                }
            )
            written += 1
            covered_brands.add(brand)

    print(f"intelligence rows written: {written:,} across {len(covered_brands):,} brands -> {out_csv}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
