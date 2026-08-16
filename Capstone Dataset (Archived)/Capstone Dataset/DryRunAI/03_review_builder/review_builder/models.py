from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class ProductLink:
    product_id: str
    source: str | None
    source_product_id: str | None
    source_url: str | None


@dataclass(slots=True)
class RawReview:
    source: str
    source_review_id: str | None
    source_product_id: str | None
    source_url: str | None
    product_id: str | None
    review_title: str | None
    review_text: str | None
    rating: Any
    review_date: Any
    reviewer_name: str | None
    verified_purchase: Any
    helpful_votes: Any
    language: str | None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class NormalizedReview:
    review_id: str
    product_id: str | None
    source: str
    source_url: str | None
    source_review_id: str | None
    review_title: str | None
    review_text: str | None
    rating: float | None
    review_date: str | None
    reviewer_name: str | None
    verified_purchase: bool | None
    helpful_votes: int | None
    language: str
    collected_at: str
    status: str
    duplicate_key: str
    validation_errors: list[str] = field(default_factory=list)

    def row(self) -> dict[str, Any]:
        return {
            "review_id": self.review_id,
            "product_id": self.product_id,
            "source": self.source,
            "source_url": self.source_url,
            "source_review_id": self.source_review_id,
            "review_title": self.review_title,
            "review_text": self.review_text,
            "rating": self.rating,
            "review_date": self.review_date,
            "reviewer_name": self.reviewer_name,
            "verified_purchase": self.verified_purchase,
            "helpful_votes": self.helpful_votes,
            "language": self.language,
            "collected_at": self.collected_at,
            "status": self.status,
        }

