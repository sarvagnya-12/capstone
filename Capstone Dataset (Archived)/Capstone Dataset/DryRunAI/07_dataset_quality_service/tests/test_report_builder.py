from __future__ import annotations

import unittest

from dataset_quality_service.models import DatasetValidationResult
from dataset_quality_service.reports import QualityReportBuilder


class QualityReportBuilderTests(unittest.TestCase):
    def test_builds_dataset_health(self) -> None:
        results = {
            "products": DatasetValidationResult("products", [{"product_id": "P1"}], "products.csv", 1),
            "images": DatasetValidationResult("images", [], "images.csv", 0),
            "reviews": DatasetValidationResult("reviews", [], "reviews.csv", 0),
            "market": DatasetValidationResult("market", [], "market.csv", 0),
            "product_intelligence": DatasetValidationResult("product_intelligence", [], "pi.csv", 0),
            "master": DatasetValidationResult("master", [{"product_id": "P1"}], "master.csv", 1),
        }
        reports = QualityReportBuilder().build(results, {"products": 100, "images": 90, "reviews": 90, "market": 90, "product_intelligence": 90, "master": 100}, {}, {})
        self.assertEqual(reports["dataset_health"]["overall_score"], 93)
        self.assertEqual(reports["relationship_report"]["missing_relationships"]["reviews"], 1)


if __name__ == "__main__":
    unittest.main()

