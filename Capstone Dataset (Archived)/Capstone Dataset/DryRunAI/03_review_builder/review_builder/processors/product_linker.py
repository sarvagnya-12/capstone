from __future__ import annotations

from pathlib import Path

from review_builder.models import ProductLink
from shared.io import read_csv_rows, read_json
from shared.validation import validate_existing_file, validate_required_columns


class ProductLinker:
    def __init__(self, products_schema_path: Path) -> None:
        self.products_schema_path = products_schema_path

    def load(self, products_csv_path: Path) -> tuple[dict[str, ProductLink], dict[str, ProductLink], dict[str, ProductLink]]:
        validate_existing_file(products_csv_path)
        schema = read_json(self.products_schema_path)
        required = {column["name"] for column in schema["columns"] if column.get("required")}
        rows = read_csv_rows(products_csv_path)
        if rows:
            validate_required_columns(set(rows[0]), required)
        by_product_id: dict[str, ProductLink] = {}
        by_source_product_id: dict[str, ProductLink] = {}
        by_source_url: dict[str, ProductLink] = {}
        for row in rows:
            link = ProductLink(
                product_id=row.get("product_id", "").strip(),
                source=(row.get("source") or None),
                source_product_id=(row.get("source_product_id") or None),
                source_url=(row.get("source_url") or None),
            )
            if link.product_id:
                by_product_id[link.product_id] = link
            if link.source_product_id:
                by_source_product_id[self._key(link.source, link.source_product_id)] = link
            if link.source_url:
                by_source_url[link.source_url.strip().lower()] = link
        return by_product_id, by_source_product_id, by_source_url

    @staticmethod
    def _key(source: str | None, source_product_id: str) -> str:
        return f"{(source or '').lower()}::{source_product_id.lower()}"

