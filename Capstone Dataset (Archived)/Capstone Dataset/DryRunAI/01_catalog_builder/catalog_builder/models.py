from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class RawProduct:
    source: str
    source_product_id: str
    name: str | None = None
    brand: str | None = None
    category: str | None = None
    subcategory: str | None = None
    gender: str | None = None
    retail_price: float | None = None
    release_year: int | None = None
    primary_color: str | None = None
    secondary_color: str | None = None
    material: str | None = None
    description: str | None = None
    source_url: str | None = None
    image_url: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class NormalizedProduct:
    product_id: str | None
    brand: str | None
    model: str | None
    category: str | None
    subcategory: str | None
    gender: str | None
    retail_price: float | None
    release_year: int | None
    primary_color: str | None
    secondary_color: str | None
    material: str | None
    source_url: str | None
    source: str
    source_product_id: str
    confidence: float
    status: str
    fingerprint: str
    raw_name: str | None = None
    description: str | None = None
    validation_errors: list[str] = field(default_factory=list)
    duplicate_of: str | None = None

    def output_row(self) -> dict[str, Any]:
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
            "source_url": self.source_url,
            "source": self.source,
            "source_product_id": self.source_product_id,
            "confidence": round(self.confidence, 4),
            "status": self.status,
        }
