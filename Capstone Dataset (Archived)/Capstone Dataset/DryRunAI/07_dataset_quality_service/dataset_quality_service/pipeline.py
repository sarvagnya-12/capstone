from __future__ import annotations

import argparse
import logging
from pathlib import Path

from dataset_quality_service.collectors import DatasetReader
from dataset_quality_service.config import DatasetQualityConfig
from dataset_quality_service.exporters import ReportExporter
from dataset_quality_service.manifest import ProjectManifestUpdater
from dataset_quality_service.models import DatasetSpec
from dataset_quality_service.processors import QualityScorer
from dataset_quality_service.reports import QualityReportBuilder
from dataset_quality_service.validators import QualityValidator
from shared.logging import configure_service_logging
from shared.utils.paths import resolve_project_path

LOGGER = logging.getLogger(__name__)


class DatasetQualityPipeline:
    def __init__(self, config: DatasetQualityConfig) -> None:
        self.config = config
        self.reader = DatasetReader()
        self.validator = QualityValidator()
        self.scorer = QualityScorer(config.quality_rules)
        self.report_builder = QualityReportBuilder()
        self.exporter = ReportExporter(config.reports_dir)
        self.manifest_updater = ProjectManifestUpdater(config.manifest_path)

    def run(self) -> Path:
        LOGGER.info("Dataset Quality Service started")
        specs = self._specs()
        product_rows = self.reader.read(specs["products"])
        product_ids = {row.get("product_id") for row in product_rows if row.get("product_id")}
        results = {}
        for name, spec in specs.items():
            rows = product_rows if name == "products" else self.reader.read(spec)
            results[name] = self.validator.validate_dataset(spec, rows, product_ids)
        missing_relationships = self.report_builder._missing_relationships(results)
        scores = {
            "products": self.scorer.dataset_score(results["products"]),
            "images": self.scorer.dataset_score(results["images"], missing_relationships.get("images", 0)),
            "reviews": self.scorer.dataset_score(results["reviews"], missing_relationships.get("reviews", 0)),
            "market": self.scorer.dataset_score(results["market"], missing_relationships.get("market", 0)),
            "product_intelligence": self.scorer.dataset_score(
                results["product_intelligence"], missing_relationships.get("product_intelligence", 0)
            ),
            "master": self.scorer.dataset_score(results["master"]),
        }
        manifest_report = self.validator.validate_manifest(self.config.manifest_path, "06_knowledge_integration_service")
        taxonomy_report = self.validator.validate_taxonomy(self.config.taxonomy_dir)
        reports = self.report_builder.build(results, scores, manifest_report, taxonomy_report)
        self.exporter.write_reports(reports)
        self.manifest_updater.update(reports["dataset_health"]["overall_score"])
        LOGGER.info(
            "Dataset Quality Service finished",
            extra={"dryrun_overall_score": reports["dataset_health"]["overall_score"]},
        )
        return self.config.reports_dir

    def _specs(self) -> dict[str, DatasetSpec]:
        schemas = self.config.schemas_dir
        return {
            "products": DatasetSpec("products", self.config.products_csv_path, schemas / "products_schema.json", "product_id", False),
            "images": DatasetSpec("images", self.config.image_metadata_path, schemas / "images_schema.json", "image_id"),
            "reviews": DatasetSpec("reviews", self.config.reviews_csv_path, schemas / "reviews_schema.json", "review_id"),
            "market": DatasetSpec("market", self.config.market_csv_path, schemas / "market_schema.json", "market_record_id"),
            "product_intelligence": DatasetSpec(
                "product_intelligence",
                self.config.product_intelligence_csv_path,
                schemas / "product_intelligence_schema.json",
                "intelligence_record_id",
            ),
            "master": DatasetSpec("master", self.config.master_products_csv_path, schemas / "master_products_schema.json", "product_id", False),
        }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate DryRunAI datasets and generate quality reports.")
    parser.add_argument("--products", type=Path, default=None)
    parser.add_argument("--images", type=Path, default=None)
    parser.add_argument("--reviews", type=Path, default=None)
    parser.add_argument("--market", type=Path, default=None)
    parser.add_argument("--product-intelligence", type=Path, default=None)
    parser.add_argument("--master", type=Path, default=None)
    parser.add_argument("--config", type=Path, default=None)
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
        "master": resolve_project_path(args.master, Path(), bootstrap_root) if args.master else None,
    }
    config = DatasetQualityConfig.load(args.config, overrides)
    log_path = configure_service_logging(
        config.service_name,
        config.logs_dir,
        max_bytes=config.logging.max_bytes,
        backup_count=config.logging.backup_count,
        console=config.logging.console,
    )
    LOGGER.info("Structured log initialized", extra={"dryrun_log_path": str(log_path)})
    output_dir = DatasetQualityPipeline(config).run()
    print(f"Dataset quality reports exported to: {output_dir}")

