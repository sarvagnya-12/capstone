from __future__ import annotations

import argparse
import logging
import time
from pathlib import Path

from catalog_builder.collectors.registry import CollectorRegistry
from catalog_builder.collectors.zappos import ZapposCollector
from catalog_builder.config.settings import CatalogConfig
from catalog_builder.exporter import CatalogExporter
from catalog_builder.id_registry import ProductIdRegistry
from catalog_builder.logging_utils import configure_logging
from catalog_builder.matcher import DuplicateMatcher
from catalog_builder.merger import ProductMerger
from catalog_builder.normalizer import ProductNormalizer
from catalog_builder.reports import ReportBuilder
from catalog_builder.taxonomy_loader import Taxonomy
from catalog_builder.validator import ProductValidator

LOGGER = logging.getLogger(__name__)


def build_registry() -> CollectorRegistry:
    registry = CollectorRegistry()
    registry.register(ZapposCollector)
    return registry


class CatalogBuilderPipeline:
    def __init__(self, config: CatalogConfig) -> None:
        self.config = config
        self.registry = build_registry()
        self.taxonomy = Taxonomy(config.taxonomy_dir)
        self.normalizer = ProductNormalizer(self.taxonomy)
        self.validator = ProductValidator()
        self.id_registry = ProductIdRegistry(config.id_registry_path, config.category_code)
        self.matcher = DuplicateMatcher(config.matching)
        self.merger = ProductMerger(self.matcher, self.id_registry)
        self.exporter = CatalogExporter(config.output_dir, config.reports_dir, config.master_schema_path)
        self.report_builder = ReportBuilder()

    def run(self, source: str, input_path: Path) -> Path:
        start = time.perf_counter()
        LOGGER.info("Catalog builder started", extra={"dryrun_source": source, "dryrun_input_path": str(input_path)})

        collector = self.registry.create(source)
        raw_products = collector.collect(input_path)
        LOGGER.info("Raw products collected", extra={"dryrun_count": len(raw_products)})

        normalized_products = [self.normalizer.normalize(product) for product in raw_products]
        valid_pre_merge, rejected_products, validation_report = self.validator.validate(normalized_products)
        LOGGER.info(
            "Products validated",
            extra={"dryrun_valid": len(valid_pre_merge), "dryrun_rejected": len(rejected_products)},
        )

        merged_products, duplicate_products = self.merger.merge(valid_pre_merge)
        exported_products = [product for product in merged_products if product.status != "duplicate_merged"]
        execution_time = time.perf_counter() - start
        reports = self.report_builder.build(
            imported_count=len(raw_products),
            valid_products=exported_products,
            rejected_products=rejected_products,
            duplicate_products=duplicate_products,
            validation_report=validation_report,
            execution_time_seconds=execution_time,
        )

        output_version_dir, reports_version_dir, version = self.exporter.next_version_dir()
        normalized_version_dir = self.config.normalized_dir / f"catalog_v{version}"
        merged_version_dir = self.config.merged_dir / f"catalog_v{version}"
        normalized_version_dir.mkdir(parents=True, exist_ok=False)
        merged_version_dir.mkdir(parents=True, exist_ok=False)

        self.exporter.write_products(normalized_version_dir / "normalized_products.csv", normalized_products)
        self.exporter.write_products(merged_version_dir / "merged_products.csv", exported_products)
        self.exporter.write_products(output_version_dir / "products.csv", exported_products)
        for report_name, report_payload in reports.items():
            self.exporter.write_json(reports_version_dir / f"{report_name}.json", report_payload)

        LOGGER.info(
            "Catalog builder finished",
            extra={
                "dryrun_version": version,
                "dryrun_output_path": str(output_version_dir / "products.csv"),
                "dryrun_execution_time_seconds": round(execution_time, 4),
            },
        )
        return output_version_dir


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the DryRunAI master sneaker catalog.")
    parser.add_argument("--source", default="zappos", help="Collector source name. Default: zappos")
    parser.add_argument("--input", required=True, type=Path, help="Input CSV, JSON, JSONL, or directory.")
    parser.add_argument("--config", type=Path, default=None, help="Optional JSON config path.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = CatalogConfig.load(args.config)
    config.ensure_directories()
    log_path = configure_logging(config.logs_dir)
    LOGGER.info("Structured log initialized", extra={"dryrun_log_path": str(log_path)})
    pipeline = CatalogBuilderPipeline(config)
    input_path = resolve_input_path(args.input, config.project_root)
    output_dir = pipeline.run(args.source, input_path)
    print(f"Catalog exported to: {output_dir}")


def resolve_input_path(input_path: Path, project_root: Path) -> Path:
    if input_path.is_absolute():
        return input_path
    if input_path.exists():
        return input_path.resolve()
    return project_root / input_path
