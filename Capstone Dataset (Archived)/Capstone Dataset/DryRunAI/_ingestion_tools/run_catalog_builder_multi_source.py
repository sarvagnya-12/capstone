"""Run Stage 1 (catalog builder) over Zappos AND Amazon in a single pass.

WHY THIS SCRIPT EXISTS
----------------------
catalog_builder's own CLI takes one --source per run, and each run starts its
duplicate-matching list empty and exports a brand new catalog_v{N} containing
only that run's products. Running it twice would therefore produce catalog_v1
(zappos) and catalog_v2 (amazon) with no cross-source matching at all -- and
Stage 6 auto-discovers only the *latest* catalog version, so the ~24.5k Zappos
products would be silently dropped from the master dataset. Both sources must
go through one normalize -> validate -> merge -> export pass.

It reuses the pipeline's own classes (Taxonomy, ProductNormalizer,
ProductValidator, DuplicateMatcher, ProductIdRegistry, CatalogExporter,
ReportBuilder) rather than reimplementing any of that logic, and writes the same
outputs to the same places. Nothing inside the 01_catalog_builder package is
modified.

TWO DELIBERATE DEVIATIONS FROM ProductMerger.merge(), both verified against the
real matcher rather than assumed:

1. BRAND-BLOCKED COMPARISON (a pure optimization, provably outcome-identical).
   merge() is O(n^2): every product is scored against every previously accepted
   product. At this scale that is ~(115k)^2/2 = 6.6 BILLION SequenceMatcher
   calls -- days of compute. But DuplicateMatcher.score() weights brand at 0.28,
   so two products whose canonical brands differ can reach at most
   0.42 + 0.2 + 0.1 = 0.72, which is below the 0.78 manual_review threshold.
   Cross-brand pairs therefore can never be classified as anything but "new",
   and restricting comparisons to same-brand buckets cannot change any outcome.
   (score()'s fingerprint shortcut is also brand-derived, so it cannot fire
   across brands either.) Products with no brand can never exceed 0.72 against
   anything and are not compared at all.

2. ZAPPOS IS NOT FUZZY-MATCHED AGAINST ITSELF.
   UT-Zappos50K contains no product names, so every Zappos model string has to
   be built from subcategory + the numeric ProductID. Two genuinely different
   shoes of the same brand and category then score ~0.97 -- above the 0.92 merge
   threshold. Verified directly: two distinct Bostonian oxfords (100627 and
   100657) classify as duplicate_merged. Fuzzy-matching this source against
   itself would silently collapse thousands of distinct products. Zappos rows
   are already deduplicated deterministically on Zappos's own authoritative
   ProductID by convert_utzap50k_metadata.py, so they are accepted as-is.
   Amazon rows, which have rich distinctive titles, ARE fuzzy-matched against
   the Zappos set.

3. AMAZON IS NOT FUZZY-MATCHED AGAINST ITSELF EITHER (scope, and tractability).
   The valuable comparison is cross-source: does this Amazon listing describe a
   shoe already in the Zappos catalog? Matching Amazon against itself is only
   near-duplicate-listing cleanup, and it is what makes the run intractable --
   candidate buckets grow as Amazon rows are added, so the cost is quadratic in
   Amazon's ~90k rows. Measured: >13 minutes of CPU without finishing the first
   10,000, extrapolating to roughly ten hours. Excluding Amazon from the
   candidate pool makes each Amazon row a scan of its brand's Zappos products
   (~36 on average) instead, which is linear and finishes in minutes. The
   consequence, stated plainly: two Amazon listings of the same shoe remain two
   catalog products. Stage 7 counts them honestly.

Usage:
    python _ingestion_tools/run_catalog_builder_multi_source.py
"""

from __future__ import annotations

import argparse
import sys
import time
from collections import defaultdict
from pathlib import Path

PIPELINE_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PIPELINE_ROOT))
sys.path.insert(0, str(PIPELINE_ROOT / "01_catalog_builder"))

from catalog_builder.collectors.amazon import AmazonCollector  # noqa: E402
from catalog_builder.collectors.zappos import ZapposCollector  # noqa: E402
from catalog_builder.config.settings import CatalogConfig  # noqa: E402
from catalog_builder.exporter import CatalogExporter  # noqa: E402
from catalog_builder.id_registry import ProductIdRegistry  # noqa: E402
from catalog_builder.matcher import DuplicateMatcher  # noqa: E402
from catalog_builder.models import NormalizedProduct  # noqa: E402
from catalog_builder.normalizer import ProductNormalizer  # noqa: E402
from catalog_builder.reports import ReportBuilder  # noqa: E402
from catalog_builder.taxonomy_loader import Taxonomy  # noqa: E402
from catalog_builder.validator import ProductValidator  # noqa: E402


class DeferredSaveIdRegistry(ProductIdRegistry):
    """ProductIdRegistry that writes its JSON file once, not once per product.

    The base class calls save() inside get_or_create(), rewriting the entire
    registry file on every newly assigned ID. That is fine for a 4-row fixture
    and quadratic for a real catalog: at ~115k products the file grows past
    10MB and gets rewritten 115k times, which does not finish in any reasonable
    time. ID assignment semantics are untouched -- only the write is deferred
    to an explicit flush() at the end of the run.
    """

    def save(self) -> None:  # no-op during the run
        return

    def flush(self) -> None:
        super().save()


def _bucket_key(product: NormalizedProduct) -> str | None:
    return product.brand.strip().lower() if product.brand else None


def merge_blocked(
    products: list[NormalizedProduct],
    matcher: DuplicateMatcher,
    id_registry: ProductIdRegistry,
    fuzzy_match: bool,
    buckets: dict[str, list[NormalizedProduct]],
    add_to_buckets: bool = True,
) -> tuple[list[NormalizedProduct], list[NormalizedProduct]]:
    """ProductMerger.merge()'s logic, with brand blocking and an opt-out of fuzzy matching.

    `add_to_buckets=False` keeps a source out of the candidate pool, so its rows
    are matched against earlier sources without also being matched against each
    other (see deviation 3 in the module docstring).
    """
    accepted: list[NormalizedProduct] = []
    duplicates: list[NormalizedProduct] = []
    # Exact-fingerprint dedup within this source. Skipping fuzzy matching for a
    # source (deviation 3) must not also skip this: the ID registry hands out
    # ONE product_id per fingerprint, so several Amazon listings of the same
    # shoe (different ASINs for colourways/sizes) otherwise all get the same id
    # and are all exported -- observed as 3,334 product_ids appearing more than
    # once in catalog_v1 (4,875 extra rows). Collapsing them is what
    # ProductMerger would have done; fuzzy matching is what stays off.
    seen_fingerprints: dict[str, NormalizedProduct] = {}

    for index, product in enumerate(products, start=1):
        key = _bucket_key(product)

        first = seen_fingerprints.get(product.fingerprint)
        if first is not None:
            product.status = "duplicate_merged"
            product.confidence = 1.0
            product.duplicate_of = first.product_id
            product.product_id = first.product_id
            duplicates.append(product)
            _fill_missing([first], product)
            continue

        if fuzzy_match and key is not None:
            decision = matcher.classify(product, buckets[key])
            product.status = decision.status
            product.confidence = decision.confidence
            product.duplicate_of = decision.duplicate_of
            if decision.status == "duplicate_merged":
                product.product_id = decision.duplicate_of
                duplicates.append(product)
                _fill_missing(buckets[key], product)
                continue
        else:
            product.status = "new"
            product.confidence = 1.0
            product.duplicate_of = None
            decision = None

        product.product_id = id_registry.get_or_create(product.fingerprint)
        accepted.append(product)
        seen_fingerprints[product.fingerprint] = product
        if key is not None and add_to_buckets:
            buckets[key].append(product)
        if decision is not None and decision.status == "manual_review":
            duplicates.append(product)

        if index % 10_000 == 0:
            print(f"    merged {index:,}/{len(products):,}", flush=True)

    return accepted, duplicates


def _fill_missing(accepted: list[NormalizedProduct], duplicate: NormalizedProduct) -> None:
    target = next((item for item in accepted if item.product_id == duplicate.duplicate_of), None)
    if target is None:
        return
    for field_name in (
        "retail_price",
        "release_year",
        "primary_color",
        "secondary_color",
        "material",
        "subcategory",
        "source_url",
    ):
        if getattr(target, field_name) is None and getattr(duplicate, field_name) is not None:
            setattr(target, field_name, getattr(duplicate, field_name))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--zappos", default="datasets/raw/zappos/zappos_utzap50k.csv")
    parser.add_argument("--amazon", default="datasets/raw/amazon/amazon_catalog.csv")
    args = parser.parse_args()

    start = time.perf_counter()
    config = CatalogConfig.load(None)
    config.ensure_directories()

    taxonomy = Taxonomy(config.taxonomy_dir)
    normalizer = ProductNormalizer(taxonomy)
    validator = ProductValidator()
    id_registry = DeferredSaveIdRegistry(config.id_registry_path, config.category_code)
    matcher = DuplicateMatcher(config.matching)
    exporter = CatalogExporter(config.output_dir, config.reports_dir, config.master_schema_path)
    report_builder = ReportBuilder()

    # (name, collector, input path, fuzzy_match, add_to_candidate_pool)
    sources = [
        ("zappos", ZapposCollector(), PIPELINE_ROOT / args.zappos, False, True),
        ("amazon", AmazonCollector(), PIPELINE_ROOT / args.amazon, True, False),
    ]

    all_normalized: list[NormalizedProduct] = []
    all_rejected: list[NormalizedProduct] = []
    all_accepted: list[NormalizedProduct] = []
    all_duplicates: list[NormalizedProduct] = []
    imported_count = 0
    validation_report: dict = {}
    buckets: dict[str, list[NormalizedProduct]] = defaultdict(list)
    per_source: dict[str, dict] = {}

    for source_name, collector, input_path, fuzzy, pool in sources:
        if not input_path.exists():
            raise SystemExit(f"Missing input for {source_name}: {input_path}")

        print(f"\n=== {source_name} ===")
        raw = collector.collect(input_path)
        imported_count += len(raw)
        print(f"  collected: {len(raw):,}")

        normalized = [normalizer.normalize(product) for product in raw]
        valid, rejected, report = validator.validate(normalized)
        print(f"  valid: {len(valid):,}  rejected: {len(rejected):,}  {report['missing_required_fields']}")

        print(f"  merging (fuzzy_match={fuzzy}) ...")
        accepted, duplicates = merge_blocked(valid, matcher, id_registry, fuzzy, buckets, add_to_buckets=pool)
        print(f"  accepted: {len(accepted):,}  duplicates/manual_review: {len(duplicates):,}")

        all_normalized.extend(normalized)
        all_rejected.extend(rejected)
        all_accepted.extend(accepted)
        all_duplicates.extend(duplicates)
        per_source[source_name] = {
            "collected": len(raw),
            "valid": len(valid),
            "rejected": len(rejected),
            "accepted": len(accepted),
            "duplicates_or_manual_review": len(duplicates),
            "fuzzy_matched": fuzzy,
        }
        if not validation_report:
            validation_report = report
        else:
            validation_report = {
                "products_checked": validation_report["products_checked"] + report["products_checked"],
                "products_valid": validation_report["products_valid"] + report["products_valid"],
                "products_rejected": validation_report["products_rejected"] + report["products_rejected"],
                "missing_required_fields": {
                    key: validation_report["missing_required_fields"].get(key, 0)
                    + report["missing_required_fields"].get(key, 0)
                    for key in set(validation_report["missing_required_fields"]) | set(report["missing_required_fields"])
                },
                "rejected_products": validation_report["rejected_products"] + report["rejected_products"],
            }

    id_registry.flush()
    exported = [product for product in all_accepted if product.status != "duplicate_merged"]
    execution_time = time.perf_counter() - start

    reports = report_builder.build(
        imported_count=imported_count,
        valid_products=exported,
        rejected_products=all_rejected,
        duplicate_products=all_duplicates,
        validation_report=validation_report,
        execution_time_seconds=execution_time,
    )
    reports["multi_source_summary"] = {
        "per_source": per_source,
        "total_exported": len(exported),
        "note": "Zappos is deduplicated deterministically on its own ProductID and not fuzzy-matched against itself; see this script's module docstring.",
    }

    output_dir, reports_dir, version = exporter.next_version_dir()
    normalized_dir = config.normalized_dir / f"catalog_v{version}"
    merged_dir = config.merged_dir / f"catalog_v{version}"
    normalized_dir.mkdir(parents=True, exist_ok=False)
    merged_dir.mkdir(parents=True, exist_ok=False)

    exporter.write_products(normalized_dir / "normalized_products.csv", all_normalized)
    exporter.write_products(merged_dir / "merged_products.csv", exported)
    exporter.write_products(output_dir / "products.csv", exported)
    for name, payload in reports.items():
        exporter.write_json(reports_dir / f"{name}.json", payload)

    print(f"\nExported {len(exported):,} products to {output_dir / 'products.csv'}")
    print(f"Elapsed: {execution_time:.1f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
