from __future__ import annotations

from collections import defaultdict
from typing import Any

from knowledge_integration_service.models import DatasetBundle, MasterProduct


class KnowledgeIntegrator:
    def integrate(self, bundle: DatasetBundle) -> list[MasterProduct]:
        images = self._group(bundle.images)
        reviews = self._group(bundle.reviews)
        market = self._group(bundle.market)
        intelligence = self._group(bundle.product_intelligence)
        master_products: list[MasterProduct] = []
        seen: set[str] = set()
        for product in bundle.products:
            product_id = product.get("product_id", "").strip()
            if product_id in seen:
                continue
            seen.add(product_id)
            image_refs = self._refs(images.get(product_id, []), "image_id", "images")
            review_refs = self._refs(reviews.get(product_id, []), "review_id", "reviews")
            market_refs = self._refs(market.get(product_id, []), "market_record_id", "market")
            intelligence_refs = self._refs(intelligence.get(product_id, []), "intelligence_record_id", "product_intelligence")
            provenance = self._provenance(product, bundle.dataset_paths)
            master_products.append(
                MasterProduct(
                    product_id=product_id,
                    brand=product.get("brand") or None,
                    model=product.get("model") or None,
                    category=product.get("category") or None,
                    subcategory=product.get("subcategory") or None,
                    gender=product.get("gender") or None,
                    retail_price=product.get("retail_price") or None,
                    release_year=product.get("release_year") or None,
                    primary_color=product.get("primary_color") or None,
                    secondary_color=product.get("secondary_color") or None,
                    material=product.get("material") or None,
                    source=product.get("source") or None,
                    source_url=product.get("source_url") or None,
                    image_refs=image_refs,
                    review_refs=review_refs,
                    market_record_refs=market_refs,
                    product_intelligence_refs=intelligence_refs,
                    provenance=provenance,
                    relationship_counts={
                        "images": len(image_refs),
                        "reviews": len(review_refs),
                        "market_records": len(market_refs),
                        "product_intelligence_records": len(intelligence_refs),
                    },
                )
            )
        return master_products

    @staticmethod
    def _group(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
        grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in rows:
            product_id = str(row.get("product_id", "")).strip()
            if product_id:
                grouped[product_id].append(row)
        return grouped

    @staticmethod
    def _refs(rows: list[dict[str, Any]], id_field: str, dataset: str) -> list[dict[str, Any]]:
        refs: list[dict[str, Any]] = []
        seen: set[str] = set()
        for row in rows:
            ref_id = str(row.get(id_field, "")).strip()
            if not ref_id or ref_id in seen:
                continue
            seen.add(ref_id)
            refs.append(
                {
                    "id": ref_id,
                    "dataset": dataset,
                    "source": row.get("source"),
                    "source_url": row.get("source_url"),
                    "collection_timestamp": row.get("download_timestamp") or row.get("collected_at") or row.get("last_updated"),
                }
            )
        return refs

    @staticmethod
    def _provenance(product: dict[str, Any], dataset_paths: dict[str, str | None]) -> dict[str, Any]:
        return {
            "core_product": {
                "dataset": "products",
                "dataset_path": dataset_paths.get("products"),
                "source": product.get("source"),
                "source_url": product.get("source_url"),
                "collection_timestamp": None,
            },
            "relationships": {
                "images_dataset": dataset_paths.get("images"),
                "reviews_dataset": dataset_paths.get("reviews"),
                "market_dataset": dataset_paths.get("market"),
                "product_intelligence_dataset": dataset_paths.get("product_intelligence"),
            },
        }

