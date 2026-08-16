from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class MatchingConfig:
    high_confidence_threshold: float = 0.92
    medium_confidence_threshold: float = 0.78


@dataclass(frozen=True, slots=True)
class CatalogConfig:
    project_root: Path
    data_root: Path
    taxonomy_dir: Path
    raw_dir: Path
    normalized_dir: Path
    merged_dir: Path
    output_dir: Path
    reports_dir: Path
    logs_dir: Path
    id_registry_path: Path
    master_schema_path: Path
    category_code: str = "SNK"
    matching: MatchingConfig = MatchingConfig()

    @classmethod
    def load(cls, config_path: Path | None = None) -> "CatalogConfig":
        project_root = find_project_root(Path(__file__).resolve())
        default_data: dict[str, Any] = {}
        if config_path and config_path.exists():
            default_data = json.loads(config_path.read_text(encoding="utf-8-sig"))

        data_root = resolve_config_path(default_data.get("data_root"), project_root / "datasets", project_root)
        taxonomy_dir = resolve_config_path(default_data.get("taxonomy_dir"), project_root / "taxonomy", project_root)
        matching_data = default_data.get("matching", {})
        matching = MatchingConfig(
            high_confidence_threshold=float(matching_data.get("high_confidence_threshold", 0.92)),
            medium_confidence_threshold=float(matching_data.get("medium_confidence_threshold", 0.78)),
        )

        return cls(
            project_root=project_root,
            data_root=data_root,
            taxonomy_dir=taxonomy_dir,
            raw_dir=resolve_config_path(default_data.get("raw_dir"), data_root / "raw", project_root),
            normalized_dir=resolve_config_path(default_data.get("normalized_dir"), data_root / "normalized", project_root),
            merged_dir=resolve_config_path(default_data.get("merged_dir"), data_root / "merged", project_root),
            output_dir=resolve_config_path(default_data.get("output_dir"), data_root / "versions", project_root),
            reports_dir=resolve_config_path(default_data.get("reports_dir"), data_root / "processed" / "reports", project_root),
            logs_dir=resolve_config_path(default_data.get("logs_dir"), data_root / "processed" / "logs", project_root),
            id_registry_path=resolve_config_path(
                default_data.get("id_registry_path"), data_root / "processed" / "id_registry.json", project_root
            ),
            master_schema_path=resolve_config_path(
                default_data.get("master_schema_path"), project_root / "schemas" / "products_schema.json", project_root
            ),
            category_code=str(default_data.get("category_code", "SNK")),
            matching=matching,
        )

    def ensure_directories(self) -> None:
        for path in (
            self.raw_dir,
            self.normalized_dir,
            self.merged_dir,
            self.output_dir,
            self.reports_dir,
            self.logs_dir,
            self.taxonomy_dir,
            self.id_registry_path.parent,
        ):
            path.mkdir(parents=True, exist_ok=True)


def find_project_root(start: Path) -> Path:
    for path in (start, *start.parents):
        if (path / "schemas" / "products_schema.json").exists() and (path / "taxonomy").is_dir():
            return path
    raise FileNotFoundError("Could not locate DryRunAI project root from catalog builder settings.")


def resolve_config_path(value: Any, default: Path, project_root: Path) -> Path:
    if value in (None, ""):
        return default
    path = Path(value)
    if path.is_absolute():
        return path
    return project_root / path
