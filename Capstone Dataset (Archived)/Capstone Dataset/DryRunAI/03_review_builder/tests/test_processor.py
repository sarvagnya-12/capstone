from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from review_builder.config import ReviewBuilderConfig
from review_builder.models import ProductLink, RawReview
from review_builder.processors import ProductLinker, ReviewProcessor


class ProcessorTests(unittest.TestCase):
    def test_processor_links_source_product_id(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "config.json"
            config_path.write_text('{"reviews_root": "' + temp_dir.replace("\\", "\\\\") + '"}', encoding="utf-8")
            config = ReviewBuilderConfig.load(config_path)
            link = ProductLink("DRY-SNK-000001", "amazon", "Z1", "https://example.com/z1")
            processor = ReviewProcessor(config, {}, {ProductLinker._key("amazon", "Z1"): link}, {})
            review = processor.normalize(
                RawReview(
                    source="amazon",
                    source_review_id="A1",
                    source_product_id="Z1",
                    source_url=None,
                    product_id=None,
                    review_title="  Nice ",
                    review_text="Good\r\nshoe",
                    rating="5 stars",
                    review_date="01/02/2026",
                    reviewer_name="Alex",
                    verified_purchase="true",
                    helpful_votes="2",
                    language=None,
                )
            )
            self.assertEqual(review.product_id, "DRY-SNK-000001")
            self.assertEqual(review.rating, 5.0)
            self.assertEqual(review.review_date, "2026-01-02")


if __name__ == "__main__":
    unittest.main()

