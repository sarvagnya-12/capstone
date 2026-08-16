from __future__ import annotations

from collections import Counter

from knowledge_integration_service.models import DatasetBundle, MasterProduct


class MasterValidator:
    def validate(self, bundle: DatasetBundle, products: list[MasterProduct]) -> tuple[list[MasterProduct], list[MasterProduct], dict]:
        valid_product_ids = {row.get("product_id") for row in bundle.products if row.get("product_id")}
        invalid: list[MasterProduct] = []
        accepted: list[MasterProduct] = []
        seen: set[str] = set()
        broken_relationships = self._broken_relationships(bundle, valid_product_ids)
        errors_counter: Counter[str] = Counter()
        for product in products:
            errors: list[str] = []
            if not product.product_id or product.product_id not in valid_product_ids:
                errors.append("broken_product_id")
            if product.product_id in seen:
                errors.append("duplicate_master_product")
            if not product.brand or not product.model or not product.category:
                errors.append("schema_violation")
            if errors:
                product.status = "invalid"
                product.validation_errors = errors
                invalid.append(product)
                for error in errors:
                    errors_counter[error] += 1
                continue
            seen.add(product.product_id)
            accepted.append(product)
        validation_report = {
            "master_products_checked": len(products),
            "master_products_valid": len(accepted),
            "master_products_invalid": len(invalid),
            "broken_relationships": broken_relationships,
            "error_counts": dict(errors_counter),
            "invalid_products": [
                {"product_id": product.product_id, "errors": product.validation_errors}
                for product in invalid
            ],
        }
        return accepted, invalid, validation_report

    @staticmethod
    def _broken_relationships(bundle: DatasetBundle, valid_product_ids: set[str]) -> dict[str, list[str]]:
        broken = {
            "images": sorted({row.get("product_id", "") for row in bundle.images if row.get("product_id") not in valid_product_ids}),
            "reviews": sorted({row.get("product_id", "") for row in bundle.reviews if row.get("product_id") not in valid_product_ids}),
            "market": sorted({row.get("product_id", "") for row in bundle.market if row.get("product_id") not in valid_product_ids}),
            "product_intelligence": sorted(
                {row.get("product_id", "") for row in bundle.product_intelligence if row.get("product_id") not in valid_product_ids}
            ),
        }
        return broken

