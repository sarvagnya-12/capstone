from __future__ import annotations

import unittest

from knowledge_integration_service.models import DatasetBundle, MasterProduct
from knowledge_integration_service.validators import MasterValidator


class MasterValidatorTests(unittest.TestCase):
    def test_detects_broken_relationships(self) -> None:
        bundle = DatasetBundle(
            products=[{"product_id": "DRY-SNK-1"}],
            images=[{"product_id": "MISSING", "image_id": "IMG-1"}],
            reviews=[],
            market=[],
            product_intelligence=[],
            dataset_paths={},
        )
        product = MasterProduct(
            product_id="DRY-SNK-1",
            brand="Nike",
            model="Air",
            category="Sneakers",
            subcategory=None,
            gender=None,
            retail_price=None,
            release_year=None,
            primary_color=None,
            secondary_color=None,
            material=None,
            source="zappos",
            source_url=None,
        )
        accepted, invalid, report = MasterValidator().validate(bundle, [product])
        self.assertEqual(len(accepted), 1)
        self.assertEqual(len(invalid), 0)
        self.assertEqual(report["broken_relationships"]["images"], ["MISSING"])


if __name__ == "__main__":
    unittest.main()

