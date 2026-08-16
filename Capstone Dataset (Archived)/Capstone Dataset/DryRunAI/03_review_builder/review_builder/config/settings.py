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
class RatingConfig:
    min: float
    max: float


@dataclass(frozen=True, slots=True)
class ReviewBuilderConfig:
    project_root: Path
    service_root: Path
    service_name: str
    products_schema_path: Path
    reviews_schema_path: Path
    products_csv_path: Path | None
    reviews_input_path: Path | None
    reviews_root: Path
    raw_dir: Path
    processed_dir: Path
    metadata_dir: Path
    quarantine_dir: Path
    reports_dir: Path
    versions_dir: Path
    logs_dir: Path
    manifest_path: Path
    supported_sources: set[str]
    supported_languages: set[str]
    default_language: str
    rating: RatingConfig
    logging: LoggingConfig

    @classmethod
    def load(
        cls,
        config_path: Path | None = None,
        products_csv_path: Path | None = None,
        reviews_input_path: Path | None = None,
    ) -> "ReviewBuilderConfig":
        service_root = Path(__file__).resolve().parents[2]
        project_root = find_project_root(service_root)
        raw = load_config(service_root / "review_builder" / "config" / "default_config.json", config_path)
        reviews_root = resolve_project_path(raw.get("reviews_root"), project_root / "datasets" / "reviews", project_root)
        products_path = products_csv_path or _latest_products_csv(project_root / "datasets" / "versions")
        return cls(
            project_root=project_root,
            service_root=service_root,
            service_name=str(raw["service_name"]),
            products_schema_path=resolve_project_path(raw.get("products_schema_path"), project_root / "schemas" / "products_schema.json", project_root),
            reviews_schema_path=resolve_project_path(raw.get("reviews_schema_path"), project_root / "schemas" / "reviews_schema.json", project_root),
            products_csv_path=products_path,
            reviews_input_path=reviews_input_path,
            reviews_root=reviews_root,
            raw_dir=resolve_project_path(raw.get("raw_dir"), reviews_root / "raw", project_root),
            processed_dir=resolve_project_path(raw.get("processed_dir"), reviews_root / "processed", project_root),
            metadata_dir=resolve_project_path(raw.get("metadata_dir"), reviews_root / "metadata", project_root),
            quarantine_dir=resolve_project_path(raw.get("quarantine_dir"), reviews_root / "quarantine", project_root),
            reports_dir=resolve_project_path(raw.get("reports_dir"), reviews_root / "reports", project_root),
            versions_dir=resolve_project_path(raw.get("versions_dir"), reviews_root / "versions", project_root),
            logs_dir=resolve_project_path(raw.get("logs_dir"), project_root / "datasets" / "processed" / "logs", project_root),
            manifest_path=resolve_project_path(raw.get("manifest_path"), project_root / "project_manifest.json", project_root),
            supported_sources={str(item).lower() for item in raw["supported_sources"]},
            supported_languages={str(item).lower() for item in raw["supported_languages"]},
            default_language=str(raw["default_language"]).lower(),
            rating=RatingConfig(min=float(raw["rating"]["min"]), max=float(raw["rating"]["max"])),
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

