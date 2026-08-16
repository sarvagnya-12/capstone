from __future__ import annotations

from collections import Counter
from urllib.parse import urlparse

from catalog_builder.models import NormalizedProduct


class ProductValidator:
    REQUIRED_FIELDS = ("brand", "model", "category")

    def validate(self, products: list[NormalizedProduct]) -> tuple[list[NormalizedProduct], list[NormalizedProduct], dict]:
        valid: list[NormalizedProduct] = []
        rejected: list[NormalizedProduct] = []
        missing_counter: Counter[str] = Counter()
        for product in products:
            errors = [f"missing_{field}" for field in self.REQUIRED_FIELDS if not getattr(product, field)]
            if product.source_url and not self._is_valid_url(product.source_url):
                errors.append("invalid_source_url")
            product.validation_errors = errors
            if errors:
                product.status = "rejected"
                rejected.append(product)
                for error in errors:
                    missing_counter[error.removeprefix("missing_")] += 1
            else:
                valid.append(product)
        report = {
            "products_checked": len(products),
            "products_valid": len(valid),
            "products_rejected": len(rejected),
            "missing_required_fields": dict(missing_counter),
            "rejected_products": [
                {
                    "source": item.source,
                    "source_product_id": item.source_product_id,
                    "source_url": item.source_url,
                    "raw_name": item.raw_name,
                    "errors": item.validation_errors,
                }
                for item in rejected
            ],
        }
        return valid, rejected, report

    @staticmethod
    def _is_valid_url(value: str) -> bool:
        parsed = urlparse(value.strip())
        return parsed.scheme in {"http", "https"} and bool(parsed.netloc)
