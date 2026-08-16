from __future__ import annotations

import argparse
import logging
import time
from pathlib import Path

from review_builder.collectors import AmazonReviewCollector, ReviewCollectorRegistry, ZapposReviewCollector
from review_builder.config import ReviewBuilderConfig
from review_builder.exporters import ReviewExporter
from review_builder.manifest import ProjectManifestUpdater
from review_builder.processors import ProductLinker, ReviewProcessor
from review_builder.reports import ReviewReportBuilder
from review_builder.validators import ReviewValidator
from shared.logging import configure_service_logging
from shared.utils.paths import resolve_project_path

LOGGER = logging.getLogger(__name__)


def build_registry() -> ReviewCollectorRegistry:
    registry = ReviewCollectorRegistry()
    registry.register(AmazonReviewCollector)
    registry.register(ZapposReviewCollector)
    return registry


class ReviewBuilderPipeline:
    def __init__(self, config: ReviewBuilderConfig) -> None:
        self.config = config
        self.registry = build_registry()
        self.linker = ProductLinker(config.products_schema_path)
        self.validator = ReviewValidator(config)
        self.exporter = ReviewExporter(
            config.reviews_schema_path,
            config.versions_dir,
            config.processed_dir,
            config.quarantine_dir,
            config.reports_dir,
            config.metadata_dir,
        )
        self.report_builder = ReviewReportBuilder()
        self.manifest_updater = ProjectManifestUpdater(config.manifest_path)

    def run(self, source: str) -> Path:
        if self.config.products_csv_path is None:
            raise FileNotFoundError("No products.csv found. Run Service 01 before running Review Builder.")
        if self.config.reviews_input_path is None:
            raise FileNotFoundError("No review input path supplied.")
        start = time.perf_counter()
        LOGGER.info("Review Builder started", extra={"dryrun_source": source, "dryrun_reviews_input": str(self.config.reviews_input_path)})
        collector = self.registry.create(source)
        raw_reviews = collector.collect(self.config.reviews_input_path)
        by_product_id, by_source_product_id, by_source_url = self.linker.load(self.config.products_csv_path)
        processor = ReviewProcessor(self.config, by_product_id, by_source_product_id, by_source_url)
        normalized_reviews = [processor.normalize(review) for review in raw_reviews]
        accepted, rejected, duplicates, validation_report = self.validator.validate(normalized_reviews)
        execution_time = time.perf_counter() - start

        version_dir, processed_dir, quarantine_dir, reports_dir, metadata_dir, version = self.exporter.create_version_dirs()
        self.exporter.write_reviews(version_dir / "processed" / "reviews.csv", accepted)
        self.exporter.write_reviews(processed_dir / "reviews.csv", accepted)
        self.exporter.write_reviews(quarantine_dir / "rejected_reviews.csv", rejected)
        self.exporter.write_reviews(quarantine_dir / "duplicate_reviews.csv", duplicates)
        self.exporter.write_json(metadata_dir / "source_metadata.json", {"source": source, "raw_reviews_collected": len(raw_reviews)})
        reports = self.report_builder.build(accepted, rejected, duplicates, validation_report, execution_time)
        for report_name, payload in reports.items():
            self.exporter.write_json(reports_dir / f"{report_name}.json", payload)
            self.exporter.write_json(version_dir / "reports" / f"{report_name}.json", payload)

        self.manifest_updater.update(len(accepted))
        LOGGER.info(
            "Review Builder finished",
            extra={
                "dryrun_version": version,
                "dryrun_reviews_collected": len(raw_reviews),
                "dryrun_reviews_exported": len(accepted),
                "dryrun_reviews_rejected": len(rejected),
                "dryrun_duplicates": len(duplicates),
                "dryrun_execution_time_seconds": round(execution_time, 4),
            },
        )
        return version_dir


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build DryRunAI product review datasets.")
    parser.add_argument("--source", required=True, choices=["amazon", "zappos"], help="Review collector source.")
    parser.add_argument("--reviews", required=True, type=Path, help="Review input CSV, JSON, JSONL, or directory.")
    parser.add_argument("--products", type=Path, default=None, help="Path to products.csv. Defaults to latest catalog version.")
    parser.add_argument("--config", type=Path, default=None, help="Optional Review Builder config override.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    bootstrap_root = Path(__file__).resolve().parents[2]
    products_path = resolve_project_path(args.products, Path(), bootstrap_root) if args.products else None
    reviews_path = resolve_project_path(args.reviews, Path(), bootstrap_root)
    config = ReviewBuilderConfig.load(args.config, products_path, reviews_path)
    log_path = configure_service_logging(
        config.service_name,
        config.logs_dir,
        max_bytes=config.logging.max_bytes,
        backup_count=config.logging.backup_count,
        console=config.logging.console,
    )
    LOGGER.info("Structured log initialized", extra={"dryrun_log_path": str(log_path)})
    output_dir = ReviewBuilderPipeline(config).run(args.source)
    print(f"Reviews exported to: {output_dir}")

