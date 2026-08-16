from __future__ import annotations

from pathlib import Path

from product_intelligence_service.models import ProductLink
from shared.io import read_csv_rows, read_json
from shared.validation import validate_existing_file, validate_required_columns


class ProductIntelligenceLinker:
    def __init__(self, products_schema_path: Path) -> None:
        self.products_schema_path = products_schema_path

    def load(self, products_csv_path: Path) -> dict[str, ProductLink]:
        validate_existing_file(products_csv_path)
        schema = read_json(self.products_schema_path)
        required = {column["name"] for column in schema["columns"] if column.get("required")}
        rows = read_csv_rows(products_csv_path)
        if rows:
            validate_required_columns(set(rows[0]), required)
        products: dict[str, ProductLink] = {}
        for row in rows:
            product_id = row.get("product_id", "").strip()
            if product_id:
                products[product_id] = ProductLink(
                    product_id=product_id,
                    brand=(row.get("brand") or None),
                    source_url=(row.get("source_url") or None),
                )
        return products

