from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from market_service.collectors.retail import ZapposCollector


class MarketCollectorTests(unittest.TestCase):
    def test_collects_matching_source_rows(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "market.csv"
            path.write_text(
                "source,dryrun_product_id,price,currency,last_updated\nzappos,DRY-SNK-1,10,USD,2026-01-01\nnike,DRY-SNK-1,12,USD,2026-01-01\n",
                encoding="utf-8",
            )
            records = ZapposCollector().collect(path)
            self.assertEqual(len(records), 1)
            self.assertEqual(records[0].source, "zappos")


if __name__ == "__main__":
    unittest.main()

