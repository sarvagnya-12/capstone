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
class QualityRules:
    missing_required_penalty: int
    duplicate_penalty: int
    broken_reference_penalty: int
    missing_dataset_penalty: int
    missing_relationship_penalty: int
    minimum_score: int
    maximum_score: int


@dataclass(frozen=True, slots=True)
class DatasetQualityConfig:
    project_root: Path
    service_root: Path
    service_name: str
    products_csv_path: Path | None
    image_metadata_path: Path | None
    reviews_csv_path: Path | None
    market_csv_path: Path | None
    product_intelligence_csv_path: Path | None
    master_products_csv_path: Path | None
    manifest_path: Path
    schemas_dir: Path
    taxonomy_dir: Path
    reports_dir: Path
    logs_dir: Path
    quality_rules: QualityRules
    logging: LoggingConfig

    @classmethod
    def load(cls, config_path: Path | None = None, overrides: dict[str, Path | None] | None = None) -> "DatasetQualityConfig":
        service_root = Path(__file__).resolve().parents[2]
        project_root = find_project_root(service_root)
        raw = load_config(service_root / "dataset_quality_service" / "config" / "default_config.json", config_path)
        overrides = overrides or {}
        datasets_dir = project_root / "datasets"
        rules = raw["quality_rules"]
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
            master_products_csv_path=overrides.get("master") or _latest(datasets_dir / "master", "master_v", "master_products.csv")
            or _direct(datasets_dir / "master" / "master_products.csv"),
            manifest_path=resolve_project_path(raw.get("manifest_path"), project_root / "project_manifest.json", project_root),
            schemas_dir=resolve_project_path(raw.get("schemas_dir"), project_root / "schemas", project_root),
            taxonomy_dir=resolve_project_path(raw.get("taxonomy_dir"), project_root / "taxonomy", project_root),
            reports_dir=resolve_project_path(raw.get("reports_dir"), datasets_dir / "quality" / "reports", project_root),
            logs_dir=resolve_project_path(raw.get("logs_dir"), datasets_dir / "processed" / "logs", project_root),
            quality_rules=QualityRules(
                missing_required_penalty=int(rules["missing_required_penalty"]),
                duplicate_penalty=int(rules["duplicate_penalty"]),
                broken_reference_penalty=int(rules["broken_reference_penalty"]),
                missing_dataset_penalty=int(rules["missing_dataset_penalty"]),
                missing_relationship_penalty=int(rules["missing_relationship_penalty"]),
                minimum_score=int(rules["minimum_score"]),
                maximum_score=int(rules["maximum_score"]),
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


def _direct(path: Path) -> Path | None:
    return path if path.exists() else None

