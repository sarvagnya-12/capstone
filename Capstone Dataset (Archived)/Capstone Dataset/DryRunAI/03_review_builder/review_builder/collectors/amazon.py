from __future__ import annotations

from pathlib import Path

from review_builder.collectors.base import BaseReviewCollector
from review_builder.collectors.common import as_text, first_value, read_rows
from review_builder.models import RawReview


class AmazonReviewCollector(BaseReviewCollector):
    source_name = "amazon"
    auto_register = True

    FIELD_ALIASES = {
        "source_review_id": ("review_id", "reviewid", "id"),
        "source_product_id": ("asin", "parent_asin", "product_id", "source_product_id"),
        "source_url": ("source_url", "product_url", "url"),
        "product_id": ("dryrun_product_id", "product_id_dryrun"),
        "review_title": ("summary", "title", "review_title"),
        "review_text": ("reviewtext", "review_text", "text", "body"),
        "rating": ("overall", "rating", "stars"),
        "review_date": ("reviewtime", "unixreviewtime", "date", "review_date"),
        "reviewer_name": ("reviewername", "reviewer_name", "author"),
        "verified_purchase": ("verified", "verified_purchase"),
        "helpful_votes": ("helpful_votes", "vote", "helpful"),
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
