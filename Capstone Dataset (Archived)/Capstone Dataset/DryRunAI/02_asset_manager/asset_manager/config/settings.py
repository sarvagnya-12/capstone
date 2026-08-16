from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from shared.config import load_config
from shared.utils.paths import find_project_root, resolve_project_path


@dataclass(frozen=True, slots=True)
class DownloadConfig:
    timeout_seconds: int
    retries: int
    user_agent: str


@dataclass(frozen=True, slots=True)
class LoggingConfig:
    max_bytes: int
    backup_count: int
    console: bool


@dataclass(frozen=True, slots=True)
class AssetManagerConfig:
    project_root: Path
    service_root: Path
    service_name: str
    product_schema_path: Path
    images_schema_path: Path
    products_csv_path: Path | None
    assets_dir: Path
    processed_dir: Path
    quarantine_dir: Path
    logs_dir: Path
    taxonomy_image_types_path: Path
    image_url_columns: list[str]
    image_type_columns: list[str]
    default_image_type: str
    supported_image_formats: set[str]
    image_format_extensions: dict[str, str]
    download: DownloadConfig
    logging: LoggingConfig

    @classmethod
    def load(cls, config_path: Path | None = None, products_csv_path: Path | None = None) -> "AssetManagerConfig":
        service_root = Path(__file__).resolve().parents[2]
        project_root = find_project_root(service_root)
        raw = load_config(service_root / "asset_manager" / "config" / "default_config.json", config_path)
        datasets_dir = project_root / "datasets"
        products_path = products_csv_path or _latest_products_csv(datasets_dir / "versions")
        return cls(
            project_root=project_root,
            service_root=service_root,
            service_name=str(raw["service_name"]),
            product_schema_path=resolve_project_path(raw.get("product_schema_path"), project_root / "schemas" / "products_schema.json", project_root),
            images_schema_path=resolve_project_path(raw.get("images_schema_path"), project_root / "schemas" / "images_schema.json", project_root),
            products_csv_path=products_path,
            assets_dir=resolve_project_path(raw.get("assets_dir"), datasets_dir / "assets", project_root),
            processed_dir=resolve_project_path(raw.get("processed_dir"), datasets_dir / "processed", project_root),
            quarantine_dir=resolve_project_path(raw.get("quarantine_dir"), datasets_dir / "quarantine", project_root),
            logs_dir=resolve_project_path(raw.get("logs_dir"), datasets_dir / "processed" / "logs", project_root),
            taxonomy_image_types_path=resolve_project_path(
                raw.get("taxonomy_image_types_path"), project_root / "taxonomy" / "image_types.json", project_root
            ),
            image_url_columns=list(raw["image_url_columns"]),
            image_type_columns=list(raw["image_type_columns"]),
            default_image_type=str(raw["default_image_type"]),
            supported_image_formats={str(item).upper() for item in raw["supported_image_formats"]},
            image_format_extensions={str(key).upper(): str(value) for key, value in raw["image_format_extensions"].items()},
            download=DownloadConfig(
                timeout_seconds=int(raw["download"]["timeout_seconds"]),
                retries=int(raw["download"]["retries"]),
                user_agent=str(raw["download"]["user_agent"]),
            ),
            logging=LoggingConfig(
                max_bytes=int(raw["logging"]["max_bytes"]),
                backup_count=int(raw["logging"]["backup_count"]),
                console=bool(raw["logging"]["console"]),
            ),
        )


def _latest_products_csv(versions_dir: Path) -> Path | None:
    versions = []
    for path in versions_dir.glob("catalog_v*/products.csv"):
        suffix = path.parent.name.removeprefix("catalog_v")
        if suffix.isdigit():
            versions.append((int(suffix), path))
    if not versions:
        return None
    return sorted(versions)[-1][1]
