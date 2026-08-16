from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Iterable

from catalog_builder.collectors.base import BaseCollector
from catalog_builder.models import RawProduct


class ZapposCollector(BaseCollector):
    source_name = "zappos"
    auto_register = True

    FIELD_ALIASES: dict[str, tuple[str, ...]] = {
        "source_product_id": ("id", "product_id", "asin", "sku", "filename", "image", "image_path"),
        "name": ("name", "product_name", "title", "product_title"),
        "brand": ("brand", "brand_name", "maker"),
        "category": ("category", "category_name", "product_type", "class"),
        "subcategory": ("subcategory", "sub_category", "department", "style"),
        "gender": ("gender", "audience", "department"),
        "retail_price": ("retail_price", "price", "list_price", "msrp"),
        "release_year": ("release_year", "year"),
        "primary_color": ("primary_color", "color", "colorway", "colour"),
        "secondary_color": ("secondary_color", "secondary_colour"),
        "material": ("material", "upper_material", "materials"),
        "description": ("description", "desc", "product_description", "details"),
        "source_url": ("source_url", "product_url", "product_page_url", "page_url", "detail_url", "link", "url"),
        "image_url": ("image_url", "url", "image_path", "image"),
    }

    def collect(self, input_path: Path) -> list[RawProduct]:
        rows = list(self._read_rows(input_path))
        products: list[RawProduct] = []
        for index, row in enumerate(rows, start=1):
            normalized_row = {str(key).strip().lower(): value for key, value in row.items()}
            source_product_id = self._get(normalized_row, "source_product_id") or f"zappos-row-{index}"
            products.append(
                RawProduct(
                    source=self.source_name,
                    source_product_id=str(source_product_id),
                    name=self._string(normalized_row, "name"),
                    brand=self._string(normalized_row, "brand"),
                    category=self._string(normalized_row, "category"),
                    subcategory=self._string(normalized_row, "subcategory"),
                    gender=self._string(normalized_row, "gender"),
                    retail_price=self._float(self._get(normalized_row, "retail_price")),
                    release_year=self._int(self._get(normalized_row, "release_year")),
                    primary_color=self._string(normalized_row, "primary_color"),
                    secondary_color=self._string(normalized_row, "secondary_color"),
                    material=self._string(normalized_row, "material"),
                    description=self._string(normalized_row, "description"),
                    source_url=self._string(normalized_row, "source_url"),
                    image_url=self._string(normalized_row, "image_url"),
                    metadata=dict(row),
                )
            )
        return products

    def _read_rows(self, input_path: Path) -> Iterable[dict[str, Any]]:
        if input_path.is_dir():
            for file_path in sorted(input_path.rglob("*")):
                if file_path.suffix.lower() in {".csv", ".json", ".jsonl"}:
                    yield from self._read_rows(file_path)
            return
        suffix = input_path.suffix.lower()
        if suffix == ".csv":
            with input_path.open("r", encoding="utf-8-sig", newline="") as handle:
                yield from csv.DictReader(handle)
            return
        if suffix == ".jsonl":
            with input_path.open("r", encoding="utf-8") as handle:
                for line in handle:
                    if line.strip():
                        yield json.loads(line)
            return
        if suffix == ".json":
            data = json.loads(input_path.read_text(encoding="utf-8"))
            if isinstance(data, list):
                for row in data:
                    if isinstance(row, dict):
                        yield row
            elif isinstance(data, dict):
                items = data.get("products") or data.get("items") or []
                for row in items:
                    if isinstance(row, dict):
                        yield row
            return
        raise ValueError(f"Unsupported Zappos input format: {input_path}")

    def _get(self, row: dict[str, Any], field: str) -> Any:
        for alias in self.FIELD_ALIASES[field]:
            if alias in row and row[alias] not in (None, ""):
                return row[alias]
        return None

    def _string(self, row: dict[str, Any], field: str) -> str | None:
        value = self._get(row, field)
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    @staticmethod
    def _float(value: Any) -> float | None:
        if value in (None, ""):
            return None
        try:
            return float(str(value).replace("$", "").replace(",", "").strip())
        except ValueError:
            return None

    @staticmethod
    def _int(value: Any) -> int | None:
        if value in (None, ""):
            return None
        try:
            return int(float(str(value).strip()))
        except ValueError:
            return None
