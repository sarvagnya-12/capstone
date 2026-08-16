from __future__ import annotations

import unittest

from dataset_quality_service.config.settings import QualityRules
from dataset_quality_service.models import DatasetValidationResult
from dataset_quality_service.processors import QualityScorer


class QualityScorerTests(unittest.TestCase):
    def test_penalizes_issues(self) -> None:
        rules = QualityRules(3, 5, 7, 15, 2, 0, 100)
        result = DatasetValidationResult(
            name="reviews",
            rows=[],
            path="reviews.csv",
            row_count=1,
            missing_required_fields={"review_text": 1},
            duplicate_ids=["REV-1"],
            broken_product_ids=["BAD"],
        )
        self.assertEqual(QualityScorer(rules).dataset_score(result), 85)


if __name__ == "__main__":
    unittest.main()

