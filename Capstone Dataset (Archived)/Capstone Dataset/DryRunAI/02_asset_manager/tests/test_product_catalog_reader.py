from __future__ import annotations

import csv
import json
import tempfile
import unittest
from pathlib import Path

from asset_manager.collectors import ProductCatalogReader


class ProductCatalogReaderTests(unittest.TestCase):
    def test_reads_products_with_schema(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            schema_path = root / "schema.json"
            products_path = root / "products.csv"
            schema_path.write_text(
                json.dumps({"columns": [{"name": "product_id", "required": True}, {"name": "source", "required": True}]}),
                encoding="utf-8",
            )
            with products_path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=["product_id", "source", "source_url"])
                writer.writeheader()
                writer.writerow({"product_id": "DRY-SNK-000001", "source": "zappos", "source_url": ""})
            products = ProductCatalogReader(schema_path).read(products_path)
            self.assertEqual(products[0].product_id, "DRY-SNK-000001")


if __name__ == "__main__":
    unittest.main()

