from __future__ import annotations

import argparse
import logging
import time
from pathlib import Path

from product_intelligence_service.config import ProductIntelligenceConfig
from product_intelligence_service.exporters import IntelligenceExporter
from product_intelligence_service.manifest import ProjectManifestUpdater
from product_intelligence_service.processors import IntelligenceProcessor, ProductIntelligenceLinker
from product_intelligence_service.reports import IntelligenceReportBuilder
from product_intelligence_service.validators import IntelligenceValidator
from shared.collectors import CollectorFactory, global_collector_registry
from shared.logging import configure_service_logging
from shared.utils.paths import resolve_project_path

LOGGER = logging.getLogger(__name__)


class ProductIntelligencePipeline:
    def __init__(self, config: ProductIntelligenceConfig) -> None:
        self.config = config
        global_collector_registry.discover(config.collector_plugins)
        self.collector_factory = CollectorFactory(global_collector_registry)
        self.linker = ProductIntelligenceLinker(config.products_schema_path)
        self.validator = IntelligenceValidator(config)
        self.exporter = IntelligenceExporter(
            config.intelligence_schema_path,
            config.versions_dir,
            config.processed_dir,
            config.quarantine_dir,
            config.reports_dir,
            config.metadata_dir,
        )
        self.report_builder = IntelligenceReportBuilder()
        self.manifest_updater = ProjectManifestUpdater(config.manifest_path)

    def run(self, sources: list[str]) -> Path:
        if self.config.products_csv_path is None:
            raise FileNotFoundError("No products.csv found. Run Service 01 before running Product Intelligence Service.")
        if self.config.intelligence_input_path is None:
            raise FileNotFoundError("No product intelligence input path supplied.")
        start = time.perf_counter()
        LOGGER.info("Product Intelligence Service started", extra={"dryrun_sources": ",".join(sources)})
        products = self.linker.load(self.config.products_csv_path)
        raw_records = []
        for source in sources:
            collector = self.collector_factory.create(self.config.service_name, source, {"source": source})
            raw_records.extend(collector.collect(self.config.intelligence_input_path))
        processor = IntelligenceProcessor(self.config, products)
        normalized = [processor.normalize(record) for record in raw_records]
        accepted, rejected, duplicates, validation_report = self.validator.validate(normalized)
        execution_time = time.perf_counter() - start

        version_dir, processed_dir, quarantine_dir, reports_dir, metadata_dir, version = self.exporter.create_version_dirs()
        self.exporter.write_records(version_dir / "processed" / "product_intelligence.csv", accepted)
        self.exporter.write_records(processed_dir / "product_intelligence.csv", accepted)
        self.exporter.write_records(quarantine_dir / "rejected_product_intelligence.csv", rejected)
        self.exporter.write_records(quarantine_dir / "duplicate_product_intelligence.csv", duplicates)
        self.exporter.write_json(metadata_dir / "source_metadata.json", {"sources": sources, "raw_records_collected": len(raw_records)})
        reports = self.report_builder.build(len(products), accepted, rejected, duplicates, validation_report, execution_time)
        for report_name, payload in reports.items():
            self.exporter.write_json(reports_dir / f"{report_name}.json", payload)
            self.exporter.write_json(version_dir / "reports" / f"{report_name}.json", payload)
        self.manifest_updater.update(len(accepted))
        LOGGER.info(
            "Product Intelligence Service finished",
            extra={
                "dryrun_version": version,
                "dryrun_records_collected": len(raw_records),
                "dryrun_records_exported": len(accepted),
                "dryrun_records_rejected": len(rejected),
                "dryrun_duplicates": len(duplicates),
                "dryrun_execution_time_seconds": round(execution_time, 4),
            },
        )
        return version_dir


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build DryRunAI product intelligence datasets.")
    parser.add_argument("--sources", required=True, help="Comma-separated sources, e.g. nike,wikipedia,wikidata.")
    parser.add_argument("--intelligence", required=True, type=Path, help="Input CSV, JSON, JSONL, or directory.")
    parser.add_argument("--products", type=Path, default=None, help="Path to products.csv. Defaults to latest catalog version.")
    parser.add_argument("--config", type=Path, default=None, help="Optional service config override.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    bootstrap_root = Path(__file__).resolve().parents[2]
    products_path = resolve_project_path(args.products, Path(), bootstrap_root) if args.products else None
    intelligence_path = resolve_project_path(args.intelligence, Path(), bootstrap_root)
    config = ProductIntelligenceConfig.load(args.config, products_path, intelligence_path)
    log_path = configure_service_logging(
        config.service_name,
        config.logs_dir,
        max_bytes=config.logging.max_bytes,
        backup_count=config.logging.backup_count,
        console=config.logging.console,
    )
    LOGGER.info("Structured log initialized", extra={"dryrun_log_path": str(log_path)})
    sources = [source.strip().lower() for source in args.sources.split(",") if source.strip()]
    unknown = sorted(set(sources) - config.supported_collectors)
    if unknown:
        raise ValueError(f"Unsupported product intelligence sources: {', '.join(unknown)}")
    output_dir = ProductIntelligencePipeline(config).run(sources)
    print(f"Product intelligence exported to: {output_dir}")

