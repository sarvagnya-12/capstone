from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from market_service.config import MarketServiceConfig
from market_service.models import ProductMarketLink, RawMarketRecord
from market_service.processors import MarketProcessor


class MarketProcessorTests(unittest.TestCase):
    def test_normalizes_price_and_links_product(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "config.json"
            config_path.write_text('{"market_root": "' + temp_dir.replace("\\", "\\\\") + '"}', encoding="utf-8")
            config = MarketServiceConfig.load(config_path)
            processor = MarketProcessor(
                config,
                {"DRY-SNK-1": ProductMarketLink("DRY-SNK-1", "zappos", "Z1", "https://example.com/z1")},
                {},
                {},
            )
            record = processor.normalize(
                RawMarketRecord(
                    source="zappos",
                    source_product_id=None,
                    source_url=None,
                    product_id="DRY-SNK-1",
                    market_type="Retail",
                    price_type="Retail",
                    currency="usd",
                    price="$119.99",
                    availability="available",
                    stock_status="InStock",
                    release_date="01/02/2026",
                    region="us",
                    last_updated="2026-07-01",
                )
            )
            self.assertEqual(record.product_id, "DRY-SNK-1")
            self.assertEqual(record.currency, "USD")
            self.assertEqual(record.price, 119.99)
            self.assertEqual(record.release_date, "2026-01-02")


if __name__ == "__main__":
    unittest.main()

