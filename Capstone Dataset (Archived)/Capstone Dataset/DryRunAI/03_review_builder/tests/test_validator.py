from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from review_builder.config import ReviewBuilderConfig
from review_builder.models import NormalizedReview
from review_builder.validators import ReviewValidator


class ValidatorTests(unittest.TestCase):
    def test_rejects_duplicate_and_invalid(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "config.json"
            config_path.write_text('{"reviews_root": "' + temp_dir.replace("\\", "\\\\") + '"}', encoding="utf-8")
            config = ReviewBuilderConfig.load(config_path)
            base = NormalizedReview(
                review_id="REV-1",
                product_id="DRY-SNK-000001",
                source="amazon",
                source_url=None,
                source_review_id="A1",
                review_title=None,
                review_text="Good",
                rating=5.0,
                review_date=None,
                reviewer_name=None,
                verified_purchase=None,
                helpful_votes=None,
                language="en",
                collected_at="now",
                status="normalized",
                duplicate_key="same",
            )
            accepted, rejected, duplicates, _ = ReviewValidator(config).validate([base, base])
            self.assertEqual(len(accepted), 1)
            self.assertEqual(len(rejected), 0)
            self.assertEqual(len(duplicates), 1)


if __name__ == "__main__":
    unittest.main()

