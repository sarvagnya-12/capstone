from __future__ import annotations

import argparse
import logging
import time
from pathlib import Path

from knowledge_integration_service.collectors import DatasetCollector
from knowledge_integration_service.config import KnowledgeIntegrationConfig
from knowledge_integration_service.exporters import MasterExporter
from knowledge_integration_service.manifest import ProjectManifestUpdater
from knowledge_integration_service.processors import KnowledgeIntegrator
from knowledge_integration_service.reports import MasterReportBuilder
from knowledge_integration_service.validators import MasterValidator
from shared.logging import configure_service_logging
from shared.utils.paths import resolve_project_path

LOGGER = logging.getLogger(__name__)


class KnowledgeIntegrationPipeline:
    def __init__(self, config: KnowledgeIntegrationConfig) -> None:
        self.config = config
        self.collector = DatasetCollector()
        self.integrator = KnowledgeIntegrator()
        self.validator = MasterValidator()
        self.exporter = MasterExporter(config.master_schema_path, config.master_dir, config.quarantine_dir, config.reports_dir)
        self.report_builder = MasterReportBuilder()
        self.manifest_updater = ProjectManifestUpdater(config.manifest_path)

    def run(self) -> Path:
        if self.config.products_csv_path is None:
            raise FileNotFoundError("No products.csv found. Run Service 01 before running Knowledge Integration Service.")
        start = time.perf_counter()
        LOGGER.info("Knowledge Integration Service started")
        bundle = self.collector.collect_bundle(
            self.config.products_csv_path,
            self.config.image_metadata_path,
            self.config.reviews_csv_path,
            self.config.market_csv_path,
            self.config.product_intelligence_csv_path,
        )
        master_products = self.integrator.integrate(bundle)
        accepted, invalid, validation_report = self.validator.validate(bundle, master_products)
        execution_time = time.perf_counter() - start
        version_dir, version = self._create_version_dir()
        self.exporter.ensure_dirs()

        if self.config.exports.csv:
            self.exporter.write_csv(version_dir / "master_products.csv", accepted)
            self.exporter.write_csv(self.config.master_dir / "master_products.csv", accepted)
        if self.config.exports.parquet:
            self.exporter.write_parquet(version_dir / "master_products.parquet", accepted)
            self.exporter.write_parquet(self.config.master_dir / "master_products.parquet", accepted)
        if self.config.exports.jsonl:
            self.exporter.write_jsonl(version_dir / "master_products.jsonl", accepted)
            self.exporter.write_jsonl(self.config.master_dir / "master_products.jsonl", accepted)
        self.exporter.write_quarantine(self.config.quarantine_dir / f"master_v{version}_invalid_products.csv", invalid)
        reports = self.report_builder.build(bundle, accepted, invalid, validation_report, execution_time)
        for report_name, payload in reports.items():
            self.exporter.write_json(version_dir / f"{report_name}.json", payload)
            self.exporter.write_json(self.config.reports_dir / f"{report_name}.json", payload)
        self.manifest_updater.update(len(accepted), version)
        LOGGER.info(
            "Knowledge Integration Service finished",
            extra={
                "dryrun_version": version,
                "dryrun_products_integrated": len(accepted),
                "dryrun_invalid_products": len(invalid),
                "dryrun_execution_time_seconds": round(execution_time, 4),
            },
        )
        return version_dir

    def _create_version_dir(self) -> tuple[Path, int]:
        self.config.master_dir.mkdir(parents=True, exist_ok=True)
        versions = []
        for path in self.config.master_dir.glob("master_v*"):
            suffix = path.name.removeprefix("master_v")
            if path.is_dir() and suffix.isdigit():
                versions.append(int(suffix))
        version = max(versions, default=0) + 1
        version_dir = self.config.master_dir / f"master_v{version}"
        version_dir.mkdir(parents=True, exist_ok=False)
        return version_dir, version


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Integrate DryRunAI service outputs into the master dataset.")
    parser.add_argument("--products", type=Path, default=None, help="Path to products.csv.")
    parser.add_argument("--images", type=Path, default=None, help="Path to image_metadata.csv.")
    parser.add_argument("--reviews", type=Path, default=None, help="Path to reviews.csv.")
    parser.add_argument("--market", type=Path, default=None, help="Path to market.csv.")
    parser.add_argument("--product-intelligence", type=Path, default=None, help="Path to product_intelligence.csv.")
    parser.add_argument("--config", type=Path, default=None, help="Optional service config override.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    bootstrap_root = Path(__file__).resolve().parents[2]
    overrides = {
        "products": resolve_project_path(args.products, Path(), bootstrap_root) if args.products else None,
        "images": resolve_project_path(args.images, Path(), bootstrap_root) if args.images else None,
        "reviews": resolve_project_path(args.reviews, Path(), bootstrap_root) if args.reviews else None,
        "market": resolve_project_path(args.market, Path(), bootstrap_root) if args.market else None,
        "product_intelligence": resolve_project_path(args.product_intelligence, Path(), bootstrap_root)
        if args.product_intelligence
        else None,
    }
    config = KnowledgeIntegrationConfig.load(args.config, overrides)
    log_path = configure_service_logging(
        config.service_name,
        config.logs_dir,
        max_bytes=config.logging.max_bytes,
        backup_count=config.logging.backup_count,
        console=config.logging.console,
    )
    LOGGER.info("Structured log initialized", extra={"dryrun_log_path": str(log_path)})
    output_dir = KnowledgeIntegrationPipeline(config).run()
    print(f"Master dataset exported to: {output_dir}")
