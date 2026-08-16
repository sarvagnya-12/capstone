from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from product_intelligence_service.collectors.official_brand import NikeCollector


class IntelligenceCollectorTests(unittest.TestCase):
    def test_collects_matching_source(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "intelligence.csv"
            path.write_text("source,product_id,brand\nnike,DRY-SNK-1,Nike\nwikipedia,DRY-SNK-1,Nike\n", encoding="utf-8")
            records = NikeCollector().collect(path)
            self.assertEqual(len(records), 1)
            self.assertEqual(records[0].source, "nike")


if __name__ == "__main__":
    unittest.main()

