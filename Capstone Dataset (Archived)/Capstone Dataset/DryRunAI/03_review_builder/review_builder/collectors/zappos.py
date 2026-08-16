from __future__ import annotations

from pathlib import Path

from review_builder.collectors.base import BaseReviewCollector
from review_builder.collectors.common import as_text, first_value, read_rows
from review_builder.models import RawReview


class ZapposReviewCollector(BaseReviewCollector):
    source_name = "zappos"
    auto_register = True

    FIELD_ALIASES = {
        "source_review_id": ("review_id", "id", "source_review_id"),
        "source_product_id": ("sku", "style_id", "product_id", "source_product_id"),
        "source_url": ("source_url", "product_url", "url"),
        "product_id": ("dryrun_product_id", "product_id_dryrun"),
        "review_title": ("review_title", "title", "summary"),
        "review_text": ("review_text", "text", "body", "content"),
        "rating": ("rating", "stars", "overall"),
        "review_date": ("review_date", "date", "created_at"),
        "reviewer_name": ("reviewer_name", "author", "nickname"),
        "verified_purchase": ("verified_purchase", "verified"),
        "helpful_votes": ("helpful_votes", "helpful", "votes"),
        "language": ("language", "lang"),
    }

    def collect(self, input_path: Path) -> list[RawReview]:
        reviews: list[RawReview] = []
        for row in read_rows(input_path):
            reviews.append(
                RawReview(
                    source=self.source_name,
                    source_review_id=as_text(first_value(row, self.FIELD_ALIASES["source_review_id"])),
                    source_product_id=as_text(first_value(row, self.FIELD_ALIASES["source_product_id"])),
                    source_url=as_text(first_value(row, self.FIELD_ALIASES["source_url"])),
                    product_id=as_text(first_value(row, self.FIELD_ALIASES["product_id"])),
                    review_title=as_text(first_value(row, self.FIELD_ALIASES["review_title"])),
                    review_text=as_text(first_value(row, self.FIELD_ALIASES["review_text"])),
                    rating=first_value(row, self.FIELD_ALIASES["rating"]),
                    review_date=first_value(row, self.FIELD_ALIASES["review_date"]),
                    reviewer_name=as_text(first_value(row, self.FIELD_ALIASES["reviewer_name"])),
                    verified_purchase=first_value(row, self.FIELD_ALIASES["verified_purchase"]),
                    helpful_votes=first_value(row, self.FIELD_ALIASES["helpful_votes"]),
                    language=as_text(first_value(row, self.FIELD_ALIASES["language"])),
                    metadata=dict(row),
                )
            )
        return reviews
