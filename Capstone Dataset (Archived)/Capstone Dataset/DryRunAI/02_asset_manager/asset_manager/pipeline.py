from __future__ import annotations

import argparse
import logging
import shutil
import time
from pathlib import Path
from urllib.parse import urlparse

from asset_manager.collectors import ProductCatalogReader
from asset_manager.config import AssetManagerConfig
from asset_manager.exporters import AssetExporter
from asset_manager.models import ImageMetadata, ImageReference, ProductRecord
from asset_manager.processors import ImageProcessor
from asset_manager.processors.downloader import ImageDownloader
from asset_manager.reports import AssetReportBuilder
from asset_manager.validators import ImageAssetValidator
from shared.exceptions import ImageDownloadError
from shared.io import read_json
from shared.logging import configure_service_logging
from shared.utils.paths import resolve_project_path
from shared.utils.time import utc_now_iso

LOGGER = logging.getLogger(__name__)


class AssetManagerPipeline:
    def __init__(self, config: AssetManagerConfig) -> None:
        self.config = config
        self.reader = ProductCatalogReader(config.product_schema_path)
        self.downloader = ImageDownloader(config.download)
        self.validator = ImageAssetValidator(config.supported_image_formats)
        self.processor = ImageProcessor(config, self.validator)
        self.exporter = AssetExporter(config.assets_dir, config.processed_dir, config.quarantine_dir, config.images_schema_path)
        self.report_builder = AssetReportBuilder()
        self.image_types = self._load_image_types()

    def run(self) -> Path:
        if self.config.products_csv_path is None:
            raise FileNotFoundError("No products.csv found. Run Script 1 before running the Asset Manager.")
        start = time.perf_counter()
        LOGGER.info("Asset Manager started", extra={"dryrun_products_csv": str(self.config.products_csv_path)})
        products = self.reader.read(self.config.products_csv_path)
        references = self._collect_image_references(products)
        assets_version_dir, processed_version_dir, quarantine_version_dir, version = self.exporter.create_version_dirs()
        temp_dir = processed_version_dir / "tmp"
        temp_dir.mkdir(parents=True, exist_ok=True)

        metadata: list[ImageMetadata] = []
        for index, reference in enumerate(references, start=1):
            temp_path = temp_dir / f"download_{index:06d}{Path(reference.original_filename or 'image.bin').suffix or '.bin'}"
            try:
                self.downloader.fetch(reference.original_image_url, temp_path)
                metadata.append(self.processor.process(reference, temp_path, assets_version_dir, quarantine_version_dir, index))
            except ImageDownloadError as exc:
                metadata.append(self._download_error(reference, index, str(exc)))
                LOGGER.warning("Image skipped", extra={"dryrun_product_id": reference.product_id, "dryrun_error": str(exc)})

        for product in products:
            self.exporter.write_product_metadata(assets_version_dir / product.product_id / "metadata.json", product.product_id, metadata)
        self.exporter.write_metadata(processed_version_dir / "image_metadata.csv", metadata)
        reports = self.report_builder.build(
            products_processed=len(products),
            references_found=len(references),
            metadata=metadata,
            execution_time=time.perf_counter() - start,
        )
        for report_name, payload in reports.items():
            self.exporter.write_json(processed_version_dir / f"{report_name}.json", payload)

        if temp_dir.exists():
            shutil.rmtree(temp_dir)
        LOGGER.info(
            "Asset Manager finished",
            extra={
                "dryrun_version": version,
                "dryrun_products_processed": len(products),
                "dryrun_images_stored": len([item for item in metadata if item.status == "stored"]),
                "dryrun_execution_time_seconds": round(time.perf_counter() - start, 4),
            },
        )
        return processed_version_dir

    def _collect_image_references(self, products: list[ProductRecord]) -> list[ImageReference]:
        references: list[ImageReference] = []
        for product in products:
            for column in self.config.image_url_columns:
                image_url = (product.row.get(column) or "").strip()
                if not image_url:
                    continue
                references.append(
                    ImageReference(
                        product_id=product.product_id,
                        source=product.source,
                        source_url=product.source_url,
                        original_image_url=image_url,
                        image_type=self._image_type(product),
                        original_filename=Path(urlparse(image_url).path).name or None,
                    )
                )
        return references

    def _image_type(self, product: ProductRecord) -> str:
        for column in self.config.image_type_columns:
            value = (product.row.get(column) or "").strip()
            if value:
                normalized = value.lower()
                for canonical, aliases in self.image_types.items():
                    if normalized == canonical.lower() or normalized in {alias.lower() for alias in aliases}:
                        return canonical
        return self.config.default_image_type

    def _load_image_types(self) -> dict[str, list[str]]:
        taxonomy = read_json(self.config.taxonomy_image_types_path)
        return taxonomy.get("canonical", {})

    @staticmethod
    def _download_error(reference: ImageReference, index: int, error: str) -> ImageMetadata:
        return ImageMetadata(
            image_id=f"IMG-{index:06d}",
            product_id=reference.product_id,
            source=reference.source,
            source_url=reference.source_url,
            original_image_url=reference.original_image_url,
            image_type=reference.image_type,
            width=None,
            height=None,
            aspect_ratio=None,
            file_size=None,
            sha256=None,
            image_format=None,
            download_timestamp=utc_now_iso(),
            status="download_error",
            original_filename=reference.original_filename,
            error=error,
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Manage DryRunAI product assets.")
    parser.add_argument("--products", type=Path, default=None, help="Path to products.csv. Defaults to latest dataset version.")
    parser.add_argument("--config", type=Path, default=None, help="Optional Asset Manager config override.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    bootstrap_root = Path(__file__).resolve().parents[2]
    products_path = resolve_project_path(args.products, Path(), bootstrap_root) if args.products else None
    config = AssetManagerConfig.load(args.config, products_path)
    log_path = configure_service_logging(
        config.service_name,
        config.logs_dir,
        max_bytes=config.logging.max_bytes,
        backup_count=config.logging.backup_count,
        console=config.logging.console,
    )
    LOGGER.info("Structured log initialized", extra={"dryrun_log_path": str(log_path)})
    output_dir = AssetManagerPipeline(config).run()
    print(f"Asset metadata exported to: {output_dir}")
