from __future__ import annotations

from typing import Any

from knowledge_integration_service.models import DatasetBundle, MasterProduct


class MasterReportBuilder:
    def build(
        self,
        bundle: DatasetBundle,
        products: list[MasterProduct],
        invalid_products: list[MasterProduct],
        validation_report: dict[str, Any],
        execution_time: float,
    ) -> dict[str, dict[str, Any]]:
        images_linked = sum(product.relationship_counts.get("images", 0) for product in products)
        reviews_linked = sum(product.relationship_counts.get("reviews", 0) for product in products)
        market_linked = sum(product.relationship_counts.get("market_records", 0) for product in products)
        intelligence_linked = sum(product.relationship_counts.get("product_intelligence_records", 0) for product in products)
        missing_relationships = {
            "images": len([product for product in products if product.relationship_counts.get("images", 0) == 0]),
            "reviews": len([product for product in products if product.relationship_counts.get("reviews", 0) == 0]),
            "market": len([product for product in products if product.relationship_counts.get("market_records", 0) == 0]),
            "product_intelligence": len(
                [product for product in products if product.relationship_counts.get("product_intelligence_records", 0) == 0]
            ),
        }
        duplicate_relationships = {
            "images": self._duplicate_refs(bundle.images, "image_id"),
            "reviews": self._duplicate_refs(bundle.reviews, "review_id"),
            "market": self._duplicate_refs(bundle.market, "market_record_id"),
            "product_intelligence": self._duplicate_refs(bundle.product_intelligence, "intelligence_record_id"),
        }
        merge_report = {
            "products_integrated": len(products),
            "invalid_master_products": len(invalid_products),
            "input_rows": {
                "products": len(bundle.products),
                "images": len(bundle.images),
                "reviews": len(bundle.reviews),
                "market": len(bundle.market),
                "product_intelligence": len(bundle.product_intelligence),
            },
            "execution_time_seconds": round(execution_time, 4),
        }
        relationship_report = {
            "products_integrated": len(products),
            "images_linked": images_linked,
            "reviews_linked": reviews_linked,
            "market_records_linked": market_linked,
            "product_intelligence_records_linked": intelligence_linked,
            "missing_relationships": missing_relationships,
            "broken_relationships": validation_report["broken_relationships"],
            "duplicate_relationships": duplicate_relationships,
            "execution_time_seconds": round(execution_time, 4),
        }
        master_statistics = {
            "products_integrated": len(products),
            "images_linked": images_linked,
            "reviews_linked": reviews_linked,
            "market_records_linked": market_linked,
            "product_intelligence_records_linked": intelligence_linked,
            "execution_time_seconds": round(execution_time, 4),
        }
        return {
            "merge_report": merge_report,
            "relationship_report": relationship_report,
            "master_statistics": master_statistics,
            "validation_report": validation_report,
        }

    @staticmethod
    def _duplicate_refs(rows: list[dict], id_field: str) -> int:
        seen: set[str] = set()
        duplicates = 0
        for row in rows:
            ref_id = str(row.get(id_field, "")).strip()
            if not ref_id:
                continue
            if ref_id in seen:
                duplicates += 1
            seen.add(ref_id)
        return duplicates
