from __future__ import annotations

from pathlib import Path

from asset_manager.models import ProductRecord
from shared.collectors import BaseCollector
from shared.exceptions import ValidationError
from shared.io import read_csv_rows, read_json
from shared.validation import validate_existing_file, validate_required_columns


class ProductCatalogReader(BaseCollector):
    service_name = "asset_manager"
    source_name = "product_catalog"
    auto_register = False

    def __init__(self, product_schema_path: Path) -> None:
        self.product_schema_path = product_schema_path

    def collect(self, input_path: Path) -> list[ProductRecord]:
        return self.read(input_path)

    def read(self, products_csv_path: Path) -> list[ProductRecord]:
        validate_existing_file(products_csv_path)
        schema = read_json(self.product_schema_path)
        required = {column["name"] for column in schema["columns"] if column.get("required")}
        rows = read_csv_rows(products_csv_path)
        if not rows:
            return []
        validate_required_columns(set(rows[0]), required)
        products: list[ProductRecord] = []
        for row in rows:
            product_id = row.get("product_id", "").strip()
            if not product_id:
                raise ValidationError("Product row is missing product_id")
            products.append(
                ProductRecord(
                    product_id=product_id,
                    source=(row.get("source") or None),
                    source_url=(row.get("source_url") or None),
                    row=row,
                )
            )
        return products
