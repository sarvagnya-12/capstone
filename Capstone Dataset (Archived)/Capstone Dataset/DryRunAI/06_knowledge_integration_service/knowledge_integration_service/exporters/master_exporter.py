from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from knowledge_integration_service.models import MasterProduct
from shared.io import read_json, write_csv_rows, write_json
from shared.io.files import ensure_dir


class MasterExporter:
    def __init__(self, schema_path: Path, master_dir: Path, quarantine_dir: Path, reports_dir: Path) -> None:
        self.columns = [column["name"] for column in read_json(schema_path)["columns"]]
        self.master_dir = master_dir
        self.quarantine_dir = quarantine_dir
        self.reports_dir = reports_dir

    def ensure_dirs(self) -> None:
        ensure_dir(self.master_dir)
        ensure_dir(self.quarantine_dir)
        ensure_dir(self.reports_dir)

    def write_csv(self, path: Path, products: list[MasterProduct]) -> None:
        write_csv_rows(path, [self._flat_row(product) for product in products], self.columns)

    def write_jsonl(self, path: Path, products: list[MasterProduct]) -> None:
        ensure_dir(path.parent)
        with path.open("w", encoding="utf-8") as handle:
            for product in products:
                handle.write(json.dumps(product.row(), ensure_ascii=True) + "\n")

    def write_parquet(self, path: Path, products: list[MasterProduct]) -> None:
        ensure_dir(path.parent)
        rows = [self._flat_row(product) for product in products]
        pd.DataFrame(rows, columns=self.columns).to_parquet(path, index=False)

    def write_quarantine(self, path: Path, products: list[MasterProduct]) -> None:
        self.write_csv(path, products)

    @staticmethod
    def write_json(path: Path, payload: dict[str, Any]) -> None:
        write_json(path, payload)

    @staticmethod
    def _flat_row(product: MasterProduct) -> dict[str, Any]:
        row = product.row()
        for field in ("image_refs", "review_refs", "market_record_refs", "product_intelligence_refs", "provenance", "relationship_counts"):
            row[field] = json.dumps(row[field], ensure_ascii=True, sort_keys=True)
        return row

