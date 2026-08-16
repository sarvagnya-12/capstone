from __future__ import annotations

import unittest

from knowledge_integration_service.models import DatasetBundle
from knowledge_integration_service.processors import KnowledgeIntegrator


class KnowledgeIntegratorTests(unittest.TestCase):
    def test_integrates_relationship_refs(self) -> None:
        bundle = DatasetBundle(
            products=[{"product_id": "DRY-SNK-1", "brand": "Nike", "model": "Air", "category": "Sneakers", "source": "zappos"}],
            images=[{"product_id": "DRY-SNK-1", "image_id": "IMG-1", "source": "zappos"}],
            reviews=[{"product_id": "DRY-SNK-1", "review_id": "REV-1", "source": "amazon"}],
            market=[{"product_id": "DRY-SNK-1", "market_record_id": "MKT-1", "source": "nike"}],
            product_intelligence=[{"product_id": "DRY-SNK-1", "intelligence_record_id": "INT-1", "source": "wikipedia"}],
            dataset_paths={"products": "products.csv", "images": None, "reviews": None, "market": None, "product_intelligence": None},
        )
        products = KnowledgeIntegrator().integrate(bundle)
        self.assertEqual(len(products), 1)
        self.assertEqual(products[0].relationship_counts["images"], 1)
        self.assertEqual(products[0].relationship_counts["reviews"], 1)
        self.assertEqual(products[0].relationship_counts["market_records"], 1)
        self.assertEqual(products[0].relationship_counts["product_intelligence_records"], 1)


if __name__ == "__main__":
    unittest.main()

