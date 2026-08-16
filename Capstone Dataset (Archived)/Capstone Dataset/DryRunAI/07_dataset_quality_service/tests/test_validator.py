from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from dataset_quality_service.models import DatasetSpec
from dataset_quality_service.validators import QualityValidator


class QualityValidatorTests(unittest.TestCase):
    def test_detects_duplicates_and_broken_product_ids(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            schema = Path(temp_dir) / "schema.json"
            data = Path(temp_dir) / "data.csv"
            schema.write_text(
                json.dumps({"columns": [{"name": "review_id", "required": True}, {"name": "product_id", "required": True}]}),
                encoding="utf-8",
            )
            data.write_text("review_id,product_id\nREV-1,DRY-SNK-1\nREV-1,BAD\n", encoding="utf-8")
            rows = [{"review_id": "REV-1", "product_id": "DRY-SNK-1"}, {"review_id": "REV-1", "product_id": "BAD"}]
            result = QualityValidator().validate_dataset(DatasetSpec("reviews", data, schema, "review_id"), rows, {"DRY-SNK-1"})
            self.assertEqual(result.duplicate_ids, ["REV-1"])
            self.assertEqual(result.broken_product_ids, ["BAD"])


if __name__ == "__main__":
    unittest.main()

