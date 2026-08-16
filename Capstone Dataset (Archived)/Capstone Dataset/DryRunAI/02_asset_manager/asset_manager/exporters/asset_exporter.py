from __future__ import annotations

from pathlib import Path

from asset_manager.models import ImageMetadata
from shared.io import read_json, write_csv_rows, write_json
from shared.utils.paths import next_version_dir


class AssetExporter:
    def __init__(self, assets_dir: Path, processed_dir: Path, quarantine_dir: Path, images_schema_path: Path) -> None:
        self.assets_dir = assets_dir
        self.processed_dir = processed_dir
        self.quarantine_dir = quarantine_dir
        self.metadata_columns = [column["name"] for column in read_json(images_schema_path)["columns"]]

    def create_version_dirs(self) -> tuple[Path, Path, Path, int]:
        assets_version_dir, version = next_version_dir(self.assets_dir, "catalog_v")
        processed_version_dir = self.processed_dir / f"catalog_v{version}"
        quarantine_version_dir = self.quarantine_dir / f"catalog_v{version}"
        processed_version_dir.mkdir(parents=True, exist_ok=False)
        quarantine_version_dir.mkdir(parents=True, exist_ok=False)
        return assets_version_dir, processed_version_dir, quarantine_version_dir, version

    def write_metadata(self, path: Path, metadata: list[ImageMetadata]) -> None:
        write_csv_rows(path, [item.row() for item in metadata], self.metadata_columns)

    @staticmethod
    def write_product_metadata(path: Path, product_id: str, metadata: list[ImageMetadata]) -> None:
        write_json(
            path,
            {
                "product_id": product_id,
                "assets": [item.row() for item in metadata if item.product_id == product_id and item.status == "stored"],
            },
        )

    @staticmethod
    def write_json(path: Path, payload: dict) -> None:
        write_json(path, payload)
