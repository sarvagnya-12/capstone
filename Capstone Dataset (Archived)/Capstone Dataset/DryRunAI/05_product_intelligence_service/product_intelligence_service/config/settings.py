from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from shared.config import load_config
from shared.utils.paths import find_project_root, resolve_project_path


@dataclass(frozen=True, slots=True)
class LoggingConfig:
    max_bytes: int
    backup_count: int
    console: bool


@dataclass(frozen=True, slots=True)
class ProductIntelligenceConfig:
    project_root: Path
    service_root: Path
    service_name: str
    products_schema_path: Path
    intelligence_schema_path: Path
    products_csv_path: Path | None
    intelligence_input_path: Path | None
    intelligence_root: Path
    raw_dir: Path
    processed_dir: Path
    metadata_dir: Path
    quarantine_dir: Path
    reports_dir: Path
    versions_dir: Path
    logs_dir: Path
    manifest_path: Path
    collector_plugins: list[str]
    supported_collectors: set[str]
    supported_regions: set[str]
    supported_countries: set[str]
    logging: LoggingConfig

    @classmethod
    def load(
        cls,
        config_path: Path | None = None,
        products_csv_path: Path | None = None,
        intelligence_input_path: Path | None = None,
    ) -> "ProductIntelligenceConfig":
        service_root = Path(__file__).resolve().parents[2]
        project_root = find_project_root(service_root)
        raw = load_config(service_root / "product_intelligence_service" / "config" / "default_config.json", config_path)
        intelligence_root = resolve_project_path(raw.get("intelligence_root"), project_root / "datasets" / "product_intelligence", project_root)
        products_path = products_csv_path or _latest_products_csv(project_root / "datasets" / "versions")
        return cls(
            project_root=project_root,
            service_root=service_root,
            service_name=str(raw["service_name"]),
            products_schema_path=resolve_project_path(raw.get("products_schema_path"), project_root / "schemas" / "products_schema.json", project_root),
            intelligence_schema_path=resolve_project_path(
                raw.get("intelligence_schema_path"), project_root / "schemas" / "product_intelligence_schema.json", project_root
            ),
            products_csv_path=products_path,
            intelligence_input_path=intelligence_input_path,
            intelligence_root=intelligence_root,
            raw_dir=resolve_project_path(raw.get("raw_dir"), intelligence_root / "raw", project_root),
            processed_dir=resolve_project_path(raw.get("processed_dir"), intelligence_root / "processed", project_root),
            metadata_dir=resolve_project_path(raw.get("metadata_dir"), intelligence_root / "metadata", project_root),
            quarantine_dir=resolve_project_path(raw.get("quarantine_dir"), intelligence_root / "quarantine", project_root),
            reports_dir=resolve_project_path(raw.get("reports_dir"), intelligence_root / "reports", project_root),
            versions_dir=resolve_project_path(raw.get("versions_dir"), intelligence_root / "versions", project_root),
            logs_dir=resolve_project_path(raw.get("logs_dir"), project_root / "datasets" / "processed" / "logs", project_root),
            manifest_path=resolve_project_path(raw.get("manifest_path"), project_root / "project_manifest.json", project_root),
            collector_plugins=list(raw["collector_plugins"]),
            supported_collectors={str(item).lower() for item in raw["supported_collectors"]},
            supported_regions={str(item) for item in raw["supported_regions"]},
            supported_countries={str(item) for item in raw["supported_countries"]},
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

