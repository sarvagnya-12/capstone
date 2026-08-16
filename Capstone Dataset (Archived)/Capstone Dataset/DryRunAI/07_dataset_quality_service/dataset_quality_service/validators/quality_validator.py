from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from dataset_quality_service.models import DatasetSpec, DatasetValidationResult
from shared.io import read_json


class QualityValidator:
    def validate_dataset(self, spec: DatasetSpec, rows: list[dict[str, Any]], product_ids: set[str]) -> DatasetValidationResult:
        if spec.path is None or not spec.path.exists():
            return DatasetValidationResult(name=spec.name, rows=[], path=str(spec.path) if spec.path else None, row_count=0, missing_path=True)
        schema = read_json(spec.schema_path)
        schema_columns = [column["name"] for column in schema.get("columns", [])]
        required = [column["name"] for column in schema.get("columns", []) if column.get("required")]
        actual_columns = set(rows[0].keys()) if rows else set(schema_columns)
        schema_violations = [f"missing_column:{column}" for column in schema_columns if column not in actual_columns]
        missing_required = {
            field: sum(1 for row in rows if row.get(field) in (None, ""))
            for field in required
            if field in actual_columns
        }
        duplicate_ids = self._duplicates(rows, spec.id_field)
        broken_product_ids = []
        if spec.requires_product_id:
            broken_product_ids = sorted({row.get("product_id", "") for row in rows if row.get("product_id") and row.get("product_id") not in product_ids})
        missing_values = {
            field: sum(1 for row in rows if row.get(field) in (None, ""))
            for field in actual_columns
        }
        return DatasetValidationResult(
            name=spec.name,
            rows=rows,
            path=str(spec.path),
            row_count=len(rows),
            missing_required_fields={key: value for key, value in missing_required.items() if value > 0},
            duplicate_ids=duplicate_ids,
            schema_violations=schema_violations,
            broken_product_ids=broken_product_ids,
            missing_values=missing_values,
        )

    def validate_manifest(self, manifest_path: Path, completed_service: str) -> dict[str, Any]:
        if not manifest_path.exists():
            return {"exists": False, "issues": ["missing_manifest"]}
        manifest = read_json(manifest_path)
        completed = set(manifest.get("completed_services", []))
        issues = []
        if completed_service not in completed:
            issues.append(f"missing_completed_service:{completed_service}")
        return {"exists": True, "issues": issues, "completed_services": sorted(completed)}

    def validate_taxonomy(self, taxonomy_dir: Path) -> dict[str, Any]:
        required = ["brands.json", "categories.json", "colors.json", "materials.json", "genders.json", "image_types.json", "stopwords.json", "synonyms.json"]
        missing = [name for name in required if not (taxonomy_dir / name).exists()]
        invalid_json = []
        for path in taxonomy_dir.glob("*.json"):
            try:
                json.loads(path.read_text(encoding="utf-8-sig"))
            except json.JSONDecodeError:
                invalid_json.append(path.name)
        return {"missing_taxonomy_files": missing, "invalid_taxonomy_json": invalid_json}

    @staticmethod
    def _duplicates(rows: list[dict[str, Any]], id_field: str) -> list[str]:
        values = [str(row.get(id_field, "")).strip() for row in rows if row.get(id_field)]
        counts = Counter(values)
        return sorted([value for value, count in counts.items() if count > 1])

