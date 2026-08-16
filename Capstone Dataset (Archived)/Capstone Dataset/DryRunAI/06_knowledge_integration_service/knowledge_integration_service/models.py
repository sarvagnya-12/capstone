from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class DatasetBundle:
    products: list[dict[str, Any]]
    images: list[dict[str, Any]]
    reviews: list[dict[str, Any]]
    market: list[dict[str, Any]]
    product_intelligence: list[dict[str, Any]]
    dataset_paths: dict[str, str | None]


@dataclass(slots=True)
class MasterProduct:
    product_id: str
    brand: str | None
    model: str | None
    category: str | None
    subcategory: str | None
    gender: str | None
    retail_price: str | None
    release_year: str | None
    primary_color: str | None
    secondary_color: str | None
    material: str | None
    source: str | None
    source_url: str | None
    image_refs: list[dict[str, Any]] = field(default_factory=list)
    review_refs: list[dict[str, Any]] = field(default_factory=list)
    market_record_refs: list[dict[str, Any]] = field(default_factory=list)
    product_intelligence_refs: list[dict[str, Any]] = field(default_factory=list)
    provenance: dict[str, Any] = field(default_factory=dict)
    relationship_counts: dict[str, int] = field(default_factory=dict)
    status: str = "integrated"
    validation_errors: list[str] = field(default_factory=list)

    def row(self) -> dict[str, Any]:
        return {
            "product_id": self.product_id,
            "brand": self.brand,
            "model": self.model,
            "category": self.category,
            "subcategory": self.subcategory,
            "gender": self.gender,
            "retail_price": self.retail_price,
            "release_year": self.release_year,
            "primary_color": self.primary_color,
            "secondary_color": self.secondary_color,
            "material": self.material,
            "source": self.source,
            "source_url": self.source_url,
            "image_refs": self.image_refs,
            "review_refs": self.review_refs,
            "market_record_refs": self.market_record_refs,
            "product_intelligence_refs": self.product_intelligence_refs,
            "provenance": self.provenance,
            "relationship_counts": self.relationship_counts,
            "status": self.status,
        }

