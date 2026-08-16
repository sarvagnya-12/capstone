from __future__ import annotations

from collections import Counter

from review_builder.config import ReviewBuilderConfig
from review_builder.models import NormalizedReview


class ReviewValidator:
    def __init__(self, config: ReviewBuilderConfig) -> None:
        self.config = config

    def validate(self, reviews: list[NormalizedReview]) -> tuple[list[NormalizedReview], list[NormalizedReview], list[NormalizedReview], dict]:
        accepted: list[NormalizedReview] = []
        rejected: list[NormalizedReview] = []
        duplicates: list[NormalizedReview] = []
        seen: set[str] = set()
        missing_counter: Counter[str] = Counter()
        for review in reviews:
            errors = self._errors(review)
            if review.duplicate_key in seen:
                errors.append("duplicate_review")
            if errors:
                review.validation_errors = errors
                review.status = "duplicate" if "duplicate_review" in errors else "rejected"
                if review.status == "duplicate":
                    duplicates.append(review)
                else:
                    rejected.append(review)
                for error in errors:
                    missing_counter[error] += 1
                continue
            seen.add(review.duplicate_key)
            review.status = "accepted"
            accepted.append(review)
        report = {
            "reviews_checked": len(reviews),
            "reviews_accepted": len(accepted),
            "reviews_rejected": len(rejected),
            "duplicate_reviews": len(duplicates),
            "error_counts": dict(missing_counter),
            "rejected_reviews": [
                {
                    "review_id": item.review_id,
                    "source": item.source,
                    "source_review_id": item.source_review_id,
                    "errors": item.validation_errors,
                }
                for item in rejected
            ],
        }
        return accepted, rejected, duplicates, report

    def _errors(self, review: NormalizedReview) -> list[str]:
        errors: list[str] = []
        if not review.review_text:
            errors.append("missing_review_text")
        if not review.product_id:
            errors.append("missing_product_id")
        if review.rating is None or not (self.config.rating.min <= review.rating <= self.config.rating.max):
            errors.append("invalid_rating")
        if review.language.lower() not in self.config.supported_languages:
            errors.append("unsupported_language")
        return errors

