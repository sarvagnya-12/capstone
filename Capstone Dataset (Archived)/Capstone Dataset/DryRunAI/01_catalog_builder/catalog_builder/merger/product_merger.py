from __future__ import annotations

from catalog_builder.id_registry import ProductIdRegistry
from catalog_builder.matcher import DuplicateMatcher
from catalog_builder.models import NormalizedProduct


class ProductMerger:
    def __init__(self, matcher: DuplicateMatcher, id_registry: ProductIdRegistry) -> None:
        self.matcher = matcher
        self.id_registry = id_registry

    def merge(self, products: list[NormalizedProduct]) -> tuple[list[NormalizedProduct], list[NormalizedProduct]]:
        accepted: list[NormalizedProduct] = []
        duplicates: list[NormalizedProduct] = []
        for product in products:
            decision = self.matcher.classify(product, accepted)
            product.status = decision.status
            product.confidence = decision.confidence
            product.duplicate_of = decision.duplicate_of
            if decision.status == "duplicate_merged":
                product.product_id = decision.duplicate_of
                duplicates.append(product)
                self._fill_missing(accepted, product)
                continue
            product.product_id = self.id_registry.get_or_create(product.fingerprint)
            accepted.append(product)
            if decision.status == "manual_review":
                duplicates.append(product)
        return accepted, duplicates

    @staticmethod
    def _fill_missing(accepted: list[NormalizedProduct], duplicate: NormalizedProduct) -> None:
        target = next((item for item in accepted if item.product_id == duplicate.duplicate_of), None)
        if target is None:
            return
        for field_name in (
            "retail_price",
            "release_year",
            "primary_color",
            "secondary_color",
            "material",
            "subcategory",
            "source_url",
        ):
            if getattr(target, field_name) is None and getattr(duplicate, field_name) is not None:
                setattr(target, field_name, getattr(duplicate, field_name))
