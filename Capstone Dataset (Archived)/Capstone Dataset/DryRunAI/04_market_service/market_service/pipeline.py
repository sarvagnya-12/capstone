from __future__ import annotations

import argparse
import logging
import time
from pathlib import Path

from market_service.config import MarketServiceConfig
from market_service.exporters import MarketExporter
from market_service.manifest import ProjectManifestUpdater
from market_service.processors import MarketProcessor, MarketProductLinker
from market_service.reports import MarketReportBuilder
from market_service.validators import MarketValidator
from shared.collectors import CollectorFactory, global_collector_registry
from shared.logging import configure_service_logging
from shared.utils.paths import resolve_project_path

LOGGER = logging.getLogger(__name__)


class MarketServicePipeline:
    def __init__(self, config: MarketServiceConfig) -> None:
        self.config = config
        global_collector_registry.discover(config.collector_plugins)
        self.collector_factory = CollectorFactory(global_collector_registry)
        self.linker = MarketProductLinker(config.products_schema_path)
        self.validator = MarketValidator(config)
        self.exporter = MarketExporter(
            config.market_schema_path,
            config.versions_dir,
            config.processed_dir,
            config.quarantine_dir,
            config.reports_dir,
            config.metadata_dir,
        )
        self.report_builder = MarketReportBuilder()
        self.manifest_updater = ProjectManifestUpdater(config.manifest_path)

    def run(self, sources: list[str]) -> Path:
        if self.config.products_csv_path is None:
            raise FileNotFoundError("No products.csv found. Run Service 01 before running Market Service.")
        if self.config.market_input_path is None:
            raise FileNotFoundError("No market input path supplied.")
        start = time.perf_counter()
        LOGGER.info("Market Service started", extra={"dryrun_sources": ",".join(sources), "dryrun_input": str(self.config.market_input_path)})
        by_product_id, by_source_product_id, by_source_url = self.linker.load(self.config.products_csv_path)
        raw_records = []
        for source in sources:
            collector = self.collector_factory.create(self.config.service_name, source, {"source": source})
            raw_records.extend(collector.collect(self.config.market_input_path))
        processor = MarketProcessor(self.config, by_product_id, by_source_product_id, by_source_url)
        normalized = [processor.normalize(record) for record in raw_records]
        accepted, rejected, duplicates, validation_report = self.validator.validate(normalized)
        execution_time = time.perf_counter() - start

        version_dir, processed_dir, quarantine_dir, reports_dir, metadata_dir, version = self.exporter.create_version_dirs()
        self.exporter.write_market(version_dir / "processed" / "market.csv", accepted)
        self.exporter.write_market(processed_dir / "market.csv", accepted)
        self.exporter.write_market(quarantine_dir / "rejected_market.csv", rejected)
        self.exporter.write_market(quarantine_dir / "duplicate_market.csv", duplicates)
        self.exporter.write_json(metadata_dir / "source_metadata.json", {"sources": sources, "raw_records_collected": len(raw_records)})
        reports = self.report_builder.build(len(by_product_id), accepted, rejected, duplicates, validation_report, execution_time)
        for report_name, payload in reports.items():
            self.exporter.write_json(reports_dir / f"{report_name}.json", payload)
            self.exporter.write_json(version_dir / "reports" / f"{report_name}.json", payload)
        self.manifest_updater.update(len(accepted))
        LOGGER.info(
            "Market Service finished",
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
    parser = argparse.ArgumentParser(description="Build DryRunAI market datasets.")
    parser.add_argument("--sources", required=True, help="Comma-separated market sources, e.g. nike,zappos,stockx.")
    parser.add_argument("--market", required=True, type=Path, help="Market input CSV, JSON, JSONL, or directory.")
    parser.add_argument("--products", type=Path, default=None, help="Path to products.csv. Defaults to latest catalog version.")
    parser.add_argument("--config", type=Path, default=None, help="Optional Market Service config override.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    bootstrap_root = Path(__file__).resolve().parents[2]
    products_path = resolve_project_path(args.products, Path(), bootstrap_root) if args.products else None
    market_path = resolve_project_path(args.market, Path(), bootstrap_root)
    config = MarketServiceConfig.load(args.config, products_path, market_path)
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
        raise ValueError(f"Unsupported market sources: {', '.join(unknown)}")
    output_dir = MarketServicePipeline(config).run(sources)
    print(f"Market data exported to: {output_dir}")

