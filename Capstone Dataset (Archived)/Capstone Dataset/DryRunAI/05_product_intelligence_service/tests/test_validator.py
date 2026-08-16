from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from product_intelligence_service.config import ProductIntelligenceConfig
from product_intelligence_service.models import IntelligenceRecord
from product_intelligence_service.validators import IntelligenceValidator


class IntelligenceValidatorTests(unittest.TestCase):
    def test_rejects_duplicate_and_bad_url(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "config.json"
            config_path.write_text('{"intelligence_root": "' + temp_dir.replace("\\", "\\\\") + '"}', encoding="utf-8")
            config = ProductIntelligenceConfig.load(config_path)
            valid = IntelligenceRecord("INT-1", "DRY-SNK-1", "Nike", "nike", "https://example.com", None, None, None, "Campaign", None, None, None, None, None, None, None, "US", None, None, None, None, None, None, "United States", None, None, None, None, None, "2026-01-01T00:00:00+00:00", "normalized", "same")
            bad = IntelligenceRecord("INT-2", "DRY-SNK-1", "Nike", "nike", "bad-url", None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, "United States", None, None, None, None, None, "2026-01-01T00:00:00+00:00", "normalized", "other")
            accepted, rejected, duplicates, _ = IntelligenceValidator(config).validate([valid, valid, bad])
            self.assertEqual(len(accepted), 1)
            self.assertEqual(len(duplicates), 1)
            self.assertEqual(len(rejected), 1)


if __name__ == "__main__":
    unittest.main()

