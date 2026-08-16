from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from product_intelligence_service.config import ProductIntelligenceConfig
from product_intelligence_service.models import ProductLink, RawIntelligenceRecord
from product_intelligence_service.processors import IntelligenceProcessor


class IntelligenceProcessorTests(unittest.TestCase):
    def test_uses_product_brand_when_missing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "config.json"
            config_path.write_text('{"intelligence_root": "' + temp_dir.replace("\\", "\\\\") + '"}', encoding="utf-8")
            config = ProductIntelligenceConfig.load(config_path)
            processor = IntelligenceProcessor(config, {"DRY-SNK-1": ProductLink("DRY-SNK-1", "Nike", None)})
            record = processor.normalize(
                RawIntelligenceRecord(
                    source="wikipedia",
                    product_id="DRY-SNK-1",
                    brand=None,
                    source_url="https://example.com",
                    brand_description="  factual text ",
                    brand_mission=None,
                    brand_values=None,
                    campaign_name=None,
                    campaign_description=None,
                    campaign_theme=None,
                    marketing_strategy="brand campaign",
                    target_age_min="18",
                    target_age_max="35",
                    target_gender="unisex",
                    target_income_segment=None,
                    target_region="us",
                    target_lifestyle="athletic",
                    brand_positioning=None,
                    brand_ambassador=None,
                    tagline=None,
                    product_family="air max",
                    parent_company=None,
                    country_of_origin="united states",
                    launch_region="US",
                    distribution_channels=None,
                    sustainability_notes=None,
                    competitor_products=None,
                    competitor_brands=None,
                    collected_at="2026-07-01",
                )
            )
            self.assertEqual(record.brand, "Nike")
            self.assertEqual(record.target_age_min, 18)
            self.assertEqual(record.marketing_strategy, "Brand Campaign")


if __name__ == "__main__":
    unittest.main()

