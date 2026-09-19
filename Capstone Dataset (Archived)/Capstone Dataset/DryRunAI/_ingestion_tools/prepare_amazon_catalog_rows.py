"""Turn Amazon footwear metadata into Stage 1 catalog rows (and Stage 4 market rows).

SCOPE DECISION: only Amazon products that actually have a review in the kept
review set become catalog products. The acquisition pass keeps metadata for
300k footwear products but reviews for ~90k of them; carrying the other ~210k
into the catalog would add products with no reviews, no prices worth having and
no images, which inflates the row count while actively depressing Stage 7's
relationship-completeness scores. Including only what we have real data for is
the honest trade.

NO IMAGES ARE TAKEN FROM AMAZON. Stage 2 would have to fetch every one over
HTTP one at a time (its downloader is sequential), which is hours of traffic
against Amazon's CDN for photos that are worse GAN training data than what we
already have -- UT-Zappos50K is uniform white-background catalog photography,
while marketplace images are inconsistent. Amazon's contribution here is
reviews, prices and brands; Zappos supplies the image corpus.

COLUMN NAME GOTCHA (found by testing, not by reading): the catalog CSV's ASIN
column must be named "id" (or "asin"/"sku"/etc.), not "source_product_id" --
ZapposCollector.FIELD_ALIASES (which AmazonCollector inherits verbatim) maps
its "source_product_id" field only from columns named
("id", "product_id", "asin", "sku", "filename", "image", "image_path"). A
column literally called "source_product_id" matches none of those aliases and
silently falls back to an index-based placeholder ID, discarding every real
ASIN. Verified this the hard way: an earlier run of this exact script produced
a catalog where every Amazon row's source_product_id was "zappos-row-N".

Outputs:
  datasets/raw/amazon/amazon_catalog.csv -> Stage 1 (catalog) input
  datasets/market/raw/amazon_market.csv  -> Stage 4 (market) input

Usage:
    python _ingestion_tools/prepare_amazon_catalog_rows.py
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import date
from pathlib import Path

CATALOG_COLUMNS = [
    "id",
    "name",
    "brand",
    "category",
    "subcategory",
    "gender",
    "retail_price",
    "description",
    "source_url",
]
MARKET_COLUMNS = [
    "market_record_id",
    "source_product_id",
    "source",
    "source_url",
    "market_type",
    "price_type",
    "currency",
    "price",
    "availability",
    "region",
    "last_updated",
]

GENDER_SEGMENTS = {
    "men": "Men",
    "women": "Women",
    "boys": "Boys",
    "girls": "Girls",
    "baby": "Kids",
    "unisex": "Unisex",
}
FOOTWEAR_SEGMENTS = {"shoes", "sandals", "boots", "sneakers", "slippers"}


def reviewed_asins(reviews_path: Path) -> set[str]:
    asins: set[str] = set()
    with reviews_path.open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            try:
                asins.add(json.loads(line)["parent_asin"])
            except (json.JSONDecodeError, KeyError):
                continue
    return asins


def _segments(record: dict) -> list[str]:
    categories = record.get("categories") or []
    if not isinstance(categories, (list, tuple)):
        return []
    return [str(s).strip() for s in categories[1:] if str(s).strip()]


def _category_fields(segments: list[str]) -> tuple[str, str]:
    """Return (category, subcategory) from the taxonomy path."""
    category = "Shoes"
    for segment in segments:
        if segment.lower() in FOOTWEAR_SEGMENTS:
            category = segment
            break
    subcategory = segments[-1] if segments else ""
    if subcategory.lower() == category.lower() and len(segments) > 1:
        subcategory = segments[-2]
    return category, subcategory


def _gender(segments: list[str]) -> str:
    for segment in segments:
        mapped = GENDER_SEGMENTS.get(segment.strip().lower())
        if mapped:
            return mapped
    return ""


def _price(value) -> str:
    try:
        price = float(value)
    except (TypeError, ValueError):
        return ""
    return f"{price:.2f}" if price > 0 else ""


def _description(record: dict) -> str:
    for key in ("features", "description"):
        value = record.get(key)
        if isinstance(value, list) and value:
            return " ".join(str(v) for v in value)[:500]
        if isinstance(value, str) and value.strip():
            return value.strip()[:500]
    return ""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--all-products", action="store_true", help="Include footwear products with no kept reviews")
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    meta_path = root / "datasets" / "raw" / "amazon" / "amazon_meta_footwear.jsonl"
    reviews_path = root / "datasets" / "reviews" / "raw" / "amazon_reviews.jsonl"
    catalog_path = root / "datasets" / "raw" / "amazon" / "amazon_catalog.csv"
    market_path = root / "datasets" / "market" / "raw" / "amazon_market.csv"

    if not meta_path.exists():
        raise SystemExit(f"Missing {meta_path}. Run fetch_amazon_reviews.py first.")

    keep = set() if args.all_products else reviewed_asins(reviews_path)
    print(f"products with at least one kept review: {len(keep):,}")

    market_path.parent.mkdir(parents=True, exist_ok=True)
    snapshot = date.today().isoformat()
    written = priced = 0

    with meta_path.open(encoding="utf-8") as source, catalog_path.open(
        "w", encoding="utf-8", newline=""
    ) as catalog_handle, market_path.open("w", encoding="utf-8", newline="") as market_handle:
        catalog = csv.DictWriter(catalog_handle, fieldnames=CATALOG_COLUMNS)
        market = csv.DictWriter(market_handle, fieldnames=MARKET_COLUMNS)
        catalog.writeheader()
        market.writeheader()

        for line in source:
            if not line.strip():
                continue
            record = json.loads(line)
            asin = record.get("parent_asin")
            if not asin or (keep and asin not in keep):
                continue

            segments = _segments(record)
            category, subcategory = _category_fields(segments)
            price = _price(record.get("price"))
            url = f"https://www.amazon.com/dp/{asin}"

            catalog.writerow(
                {
                    "id": asin,
                    "name": (record.get("title") or "").strip(),
                    "brand": (record.get("store") or "").strip(),
                    "category": category,
                    "subcategory": subcategory,
                    "gender": _gender(segments),
                    "retail_price": price,
                    "description": _description(record),
                    "source_url": url,
                }
            )
            written += 1

            # Stage 4 gets a market record only where a real price exists --
            # an invented price would be worse than an absent one.
            if price:
                market.writerow(
                    {
                        "market_record_id": f"amz-mkt-{asin}",
                        "source_product_id": asin,
                        "source": "amazon",
                        "source_url": url,
                        "market_type": "Marketplace",
                        "price_type": "Retail",
                        "currency": "USD",
                        "price": price,
                        "availability": "Unknown",
                        "region": "US",
                        "last_updated": snapshot,
                    }
                )
                priced += 1

    print(f"catalog rows written: {written:,} -> {catalog_path}")
    print(f"market rows written : {priced:,} -> {market_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
