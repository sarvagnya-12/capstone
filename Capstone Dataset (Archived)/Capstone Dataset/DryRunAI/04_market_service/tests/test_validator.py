from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from market_service.config import MarketServiceConfig
from market_service.models import MarketRecord
from market_service.validators import MarketValidator


class MarketValidatorTests(unittest.TestCase):
    def test_rejects_negative_price_and_duplicate(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "config.json"
            config_path.write_text('{"market_root": "' + temp_dir.replace("\\", "\\\\") + '"}', encoding="utf-8")
            config = MarketServiceConfig.load(config_path)
            valid = MarketRecord("MKT-1", "DRY-SNK-1", "zappos", "https://example.com", "Retail", "Retail", "USD", 10.0, "Available", None, None, "US", "2026-01-01T00:00:00+00:00", "normalized", "same")
            negative = MarketRecord("MKT-2", "DRY-SNK-1", "zappos", "https://example.com", "Retail", "Retail", "USD", -1.0, "Available", None, None, "US", "2026-01-01T00:00:00+00:00", "normalized", "other")
            accepted, rejected, duplicates, _ = MarketValidator(config).validate([valid, valid, negative])
            self.assertEqual(len(accepted), 1)
            self.assertEqual(len(duplicates), 1)
            self.assertEqual(len(rejected), 1)


if __name__ == "__main__":
    unittest.main()

