from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from catalog_builder.models import NormalizedProduct


class CatalogExporter:
    def __init__(self, output_dir: Path, reports_dir: Path, schema_path: Path) -> None:
        self.output_dir = output_dir
        self.reports_dir = reports_dir
        self.schema_path = schema_path
        self.product_columns = self._load_product_columns(schema_path)

    def next_version_dir(self) -> tuple[Path, Path, int]:
        existing = []
        for path in self.output_dir.glob("catalog_v*"):
            if path.is_dir() and path.name.removeprefix("catalog_v").isdigit():
                existing.append(int(path.name.removeprefix("catalog_v")))
        version = max(existing, default=0) + 1
        output_version_dir = self.output_dir / f"catalog_v{version}"
        reports_version_dir = self.reports_dir / f"catalog_v{version}"
        output_version_dir.mkdir(parents=True, exist_ok=False)
        reports_version_dir.mkdir(parents=True, exist_ok=False)
        return output_version_dir, reports_version_dir, version

    def write_products(self, path: Path, products: list[NormalizedProduct]) -> None:
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=self.product_columns, extrasaction="ignore")
            writer.writeheader()
            for product in products:
                writer.writerow(product.output_row())

    @staticmethod
    def write_json(path: Path, payload: dict[str, Any]) -> None:
        path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

    @staticmethod
    def _load_product_columns(schema_path: Path) -> list[str]:
        schema = json.loads(schema_path.read_text(encoding="utf-8-sig"))
        columns = [column["name"] for column in schema["columns"]]
        if not columns:
            raise ValueError(f"Master product schema has no columns: {schema_path}")
        return columns
