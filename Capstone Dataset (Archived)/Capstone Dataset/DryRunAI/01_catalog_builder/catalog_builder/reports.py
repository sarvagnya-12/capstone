from __future__ import annotations

from collections import Counter
from typing import Any

from catalog_builder.models import NormalizedProduct


class ReportBuilder:
    def build(
        self,
        imported_count: int,
        valid_products: list[NormalizedProduct],
        rejected_products: list[NormalizedProduct],
        duplicate_products: list[NormalizedProduct],
        validation_report: dict[str, Any],
        execution_time_seconds: float,
    ) -> dict[str, dict[str, Any]]:
        brands = Counter(product.brand for product in valid_products if product.brand)
        categories = Counter(product.category for product in valid_products if product.category)
        imported_products = valid_products + rejected_products + [
            product for product in duplicate_products if product.status == "duplicate_merged"
        ]
        sources = Counter(product.source for product in imported_products if product.source)
        missing_values = self._missing_values(valid_products + rejected_products)
        summary = {
            "products_imported": imported_count,
            "products_exported": len(valid_products),
            "products_rejected": len(rejected_products),
            "duplicates_removed": len([item for item in duplicate_products if item.status == "duplicate_merged"]),
            "manual_review_count": len([item for item in duplicate_products if item.status == "manual_review"]),
            "brands_found": sorted(brands),
            "categories_found": sorted(categories),
            "top_20_brands": self._top_counts(brands, 20),
            "top_categories": self._top_counts(categories, None),
            "missing_prices": missing_values["retail_price"],
            "missing_descriptions": self._missing_descriptions(valid_products + rejected_products),
            "missing_colors": sum(
                1 for product in valid_products + rejected_products if not product.primary_color and not product.secondary_color
            ),
            "missing_gender": missing_values["gender"],
            "products_per_source": dict(sorted(sources.items())),
            "missing_values": missing_values,
            "execution_time_seconds": round(execution_time_seconds, 4),
        }
        duplicate_report = {
            "duplicates_detected": len(duplicate_products),
            "items": [
                {
                    "source": item.source,
                    "source_product_id": item.source_product_id,
                    "product_id": item.product_id,
                    "duplicate_of": item.duplicate_of,
                    "confidence": round(item.confidence, 4),
                    "status": item.status,
                    "model": item.model,
                    "brand": item.brand,
                }
                for item in duplicate_products
            ],
        }
        statistics = {
            "brand_counts": dict(sorted(brands.items())),
            "category_counts": dict(sorted(categories.items())),
            "status_counts": dict(Counter(product.status for product in valid_products + rejected_products)),
            "source_counts": dict(Counter(product.source for product in valid_products + rejected_products)),
            "missing_values": missing_values,
            "execution_time_seconds": round(execution_time_seconds, 4),
        }
        return {
            "catalog_summary": summary,
            "validation_report": validation_report,
            "duplicate_report": duplicate_report,
            "statistics": statistics,
        }

    @staticmethod
    def _missing_values(products: list[NormalizedProduct]) -> dict[str, int]:
        fields = (
            "brand",
            "model",
            "category",
            "subcategory",
            "gender",
            "retail_price",
            "release_year",
            "primary_color",
            "secondary_color",
            "material",
            "source_url",
        )
        return {field: sum(1 for product in products if getattr(product, field) in (None, "")) for field in fields}

    @staticmethod
    def _top_counts(counter: Counter, limit: int | None) -> list[dict[str, int]]:
        items = counter.most_common(limit)
        return [{"name": str(name), "count": count} for name, count in items]

    @staticmethod
    def _missing_descriptions(products: list[NormalizedProduct]) -> int:
        return sum(1 for product in products if not product.description)
