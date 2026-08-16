from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from review_builder.collectors import AmazonReviewCollector


class CollectorTests(unittest.TestCase):
    def test_amazon_collector_reads_csv(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "reviews.csv"
            path.write_text("asin,review_id,reviewText,overall\nZ1,A1,Great,5\n", encoding="utf-8")
            reviews = AmazonReviewCollector().collect(path)
            self.assertEqual(len(reviews), 1)
            self.assertEqual(reviews[0].source_product_id, "Z1")
            self.assertEqual(reviews[0].review_text, "Great")


if __name__ == "__main__":
    unittest.main()

