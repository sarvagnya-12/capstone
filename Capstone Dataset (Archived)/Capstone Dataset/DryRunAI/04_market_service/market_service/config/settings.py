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
class MarketServiceConfig:
    project_root: Path
    service_root: Path
    service_name: str
    products_schema_path: Path
    market_schema_path: Path
    products_csv_path: Path | None
    market_input_path: Path | None
    market_root: Path
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
    supported_currencies: set[str]
    supported_regions: set[str]
    default_region: str
    default_availability: str
    default_market_type: str
    default_price_type: str
    logging: LoggingConfig

    @classmethod
    def load(
        cls,
        config_path: Path | None = None,
        products_csv_path: Path | None = None,
        market_input_path: Path | None = None,
    ) -> "MarketServiceConfig":
        service_root = Path(__file__).resolve().parents[2]
        project_root = find_project_root(service_root)
        raw = load_config(service_root / "market_service" / "config" / "default_config.json", config_path)
        market_root = resolve_project_path(raw.get("market_root"), project_root / "datasets" / "market", project_root)
        products_path = products_csv_path or _latest_products_csv(project_root / "datasets" / "versions")
        return cls(
            project_root=project_root,
            service_root=service_root,
            service_name=str(raw["service_name"]),
            products_schema_path=resolve_project_path(raw.get("products_schema_path"), project_root / "schemas" / "products_schema.json", project_root),
            market_schema_path=resolve_project_path(raw.get("market_schema_path"), project_root / "schemas" / "market_schema.json", project_root),
            products_csv_path=products_path,
            market_input_path=market_input_path,
            market_root=market_root,
            raw_dir=resolve_project_path(raw.get("raw_dir"), market_root / "raw", project_root),
            processed_dir=resolve_project_path(raw.get("processed_dir"), market_root / "processed", project_root),
            metadata_dir=resolve_project_path(raw.get("metadata_dir"), market_root / "metadata", project_root),
            quarantine_dir=resolve_project_path(raw.get("quarantine_dir"), market_root / "quarantine", project_root),
            reports_dir=resolve_project_path(raw.get("reports_dir"), market_root / "reports", project_root),
            versions_dir=resolve_project_path(raw.get("versions_dir"), market_root / "versions", project_root),
            logs_dir=resolve_project_path(raw.get("logs_dir"), project_root / "datasets" / "processed" / "logs", project_root),
            manifest_path=resolve_project_path(raw.get("manifest_path"), project_root / "project_manifest.json", project_root),
            collector_plugins=list(raw["collector_plugins"]),
            supported_collectors={str(item).lower() for item in raw["supported_collectors"]},
            supported_currencies={str(item).upper() for item in raw["supported_currencies"]},
            supported_regions={str(item) for item in raw["supported_regions"]},
            default_region=str(raw["default_region"]),
            default_availability=str(raw["default_availability"]),
            default_market_type=str(raw["default_market_type"]),
            default_price_type=str(raw["default_price_type"]),
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

