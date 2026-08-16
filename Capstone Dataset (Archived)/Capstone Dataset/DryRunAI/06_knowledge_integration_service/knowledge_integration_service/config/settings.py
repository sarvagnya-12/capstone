from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from shared.config import load_config
from shared.utils.paths import find_project_root, resolve_project_path


@dataclass(frozen=True, slots=True)
class ExportConfig:
    csv: bool
    parquet: bool
    jsonl: bool


@dataclass(frozen=True, slots=True)
class LoggingConfig:
    max_bytes: int
    backup_count: int
    console: bool


@dataclass(frozen=True, slots=True)
class KnowledgeIntegrationConfig:
    project_root: Path
    service_root: Path
    service_name: str
    products_csv_path: Path | None
    image_metadata_path: Path | None
    reviews_csv_path: Path | None
    market_csv_path: Path | None
    product_intelligence_csv_path: Path | None
    master_schema_path: Path
    master_dir: Path
    quarantine_dir: Path
    reports_dir: Path
    logs_dir: Path
    manifest_path: Path
    exports: ExportConfig
    logging: LoggingConfig

    @classmethod
    def load(cls, config_path: Path | None = None, overrides: dict[str, Path | None] | None = None) -> "KnowledgeIntegrationConfig":
        service_root = Path(__file__).resolve().parents[2]
        project_root = find_project_root(service_root)
        raw = load_config(service_root / "knowledge_integration_service" / "config" / "default_config.json", config_path)
        overrides = overrides or {}
        datasets_dir = project_root / "datasets"
        master_dir = resolve_project_path(raw.get("master_dir"), datasets_dir / "master", project_root)
        return cls(
            project_root=project_root,
            service_root=service_root,
            service_name=str(raw["service_name"]),
            products_csv_path=overrides.get("products") or _latest(datasets_dir / "versions", "catalog_v", "products.csv"),
            image_metadata_path=overrides.get("images") or _latest(datasets_dir / "processed", "catalog_v", "image_metadata.csv"),
            reviews_csv_path=overrides.get("reviews") or _latest(datasets_dir / "reviews" / "processed", "reviews_v", "reviews.csv"),
            market_csv_path=overrides.get("market") or _latest(datasets_dir / "market" / "processed", "market_v", "market.csv"),
            product_intelligence_csv_path=overrides.get("product_intelligence")
            or _latest(datasets_dir / "product_intelligence" / "processed", "product_intelligence_v", "product_intelligence.csv"),
            master_schema_path=resolve_project_path(raw.get("master_schema_path"), project_root / "schemas" / "master_products_schema.json", project_root),
            master_dir=master_dir,
            quarantine_dir=resolve_project_path(raw.get("quarantine_dir"), master_dir / "quarantine", project_root),
            reports_dir=resolve_project_path(raw.get("reports_dir"), master_dir / "reports", project_root),
            logs_dir=resolve_project_path(raw.get("logs_dir"), datasets_dir / "processed" / "logs", project_root),
            manifest_path=resolve_project_path(raw.get("manifest_path"), project_root / "project_manifest.json", project_root),
            exports=ExportConfig(
                csv=bool(raw["exports"]["csv"]),
                parquet=bool(raw["exports"]["parquet"]),
                jsonl=bool(raw["exports"]["jsonl"]),
            ),
            logging=LoggingConfig(
                max_bytes=int(raw["logging"]["max_bytes"]),
                backup_count=int(raw["logging"]["backup_count"]),
                console=bool(raw["logging"]["console"]),
            ),
        )


def _latest(parent: Path, prefix: str, filename: str) -> Path | None:
    versions = []
    for path in parent.glob(f"{prefix}*/{filename}"):
        suffix = path.parent.name.removeprefix(prefix)
        if suffix.isdigit():
            versions.append((int(suffix), path))
    if not versions:
        return None
    return sorted(versions)[-1][1]

