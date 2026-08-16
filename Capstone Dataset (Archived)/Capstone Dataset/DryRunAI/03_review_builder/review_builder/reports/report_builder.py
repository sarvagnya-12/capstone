from __future__ import annotations

from collections import Counter
from statistics import mean
from typing import Any

from review_builder.models import NormalizedReview


class ReviewReportBuilder:
    def build(
        self,
        accepted: list[NormalizedReview],
        rejected: list[NormalizedReview],
        duplicates: list[NormalizedReview],
        validation_report: dict[str, Any],
        execution_time: float,
    ) -> dict[str, dict[str, Any]]:
        exported_reviews = accepted
        ratings = [review.rating for review in exported_reviews if review.rating is not None]
        reviews_per_product = Counter(review.product_id for review in exported_reviews if review.product_id)
        reviews_per_source = Counter(review.source for review in exported_reviews if review.source)
        summary = {
            "total_reviews": len(exported_reviews),
            "reviews_per_product": dict(sorted(reviews_per_product.items())),
            "reviews_per_source": dict(sorted(reviews_per_source.items())),
            "average_rating": round(mean(ratings), 4) if ratings else None,
            "duplicate_reviews": len(duplicates),
            "rejected_reviews": len(rejected),
            "missing_product_links": len([review for review in rejected if "missing_product_id" in review.validation_errors]),
            "execution_time_seconds": round(execution_time, 4),
        }
        duplicate_report = {
            "duplicate_reviews": len(duplicates),
            "items": [
                {
                    "review_id": review.review_id,
                    "source": review.source,
                    "source_review_id": review.source_review_id,
                    "product_id": review.product_id,
                }
                for review in duplicates
            ],
        }
        statistics = {
            "rating_counts": dict(Counter(str(review.rating) for review in exported_reviews if review.rating is not None)),
            "language_counts": dict(Counter(review.language for review in exported_reviews)),
            "status_counts": dict(Counter(review.status for review in accepted + rejected + duplicates)),
            "reviews_per_product": dict(sorted(reviews_per_product.items())),
            "reviews_per_source": dict(sorted(reviews_per_source.items())),
            "average_rating": summary["average_rating"],
            "execution_time_seconds": summary["execution_time_seconds"],
        }
        return {
            "review_summary": summary,
            "validation_report": validation_report,
            "duplicate_report": duplicate_report,
            "statistics": statistics,
        }

