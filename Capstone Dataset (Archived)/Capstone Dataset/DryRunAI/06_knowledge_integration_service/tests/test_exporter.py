from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from knowledge_integration_service.exporters import MasterExporter
from knowledge_integration_service.models import MasterProduct


class MasterExporterTests(unittest.TestCase):
    def test_writes_csv_jsonl_and_parquet(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            schema = root / "schema.json"
            schema.write_text(
                json.dumps(
                    {
                        "columns": [
                            {"name": "product_id"},
                            {"name": "brand"},
                            {"name": "model"},
                            {"name": "category"},
                            {"name": "image_refs"},
                            {"name": "provenance"},
                            {"name": "relationship_counts"},
                            {"name": "status"},
                        ]
                    }
                ),
                encoding="utf-8",
            )
            exporter = MasterExporter(schema, root / "master", root / "quarantine", root / "reports")
            product = MasterProduct("DRY-SNK-1", "Nike", "Air", "Sneakers", None, None, None, None, None, None, None, "zappos", None)
            exporter.write_csv(root / "master.csv", [product])
            exporter.write_jsonl(root / "master.jsonl", [product])
            exporter.write_parquet(root / "master.parquet", [product])
            self.assertTrue((root / "master.csv").exists())
            self.assertTrue((root / "master.jsonl").exists())
            self.assertTrue((root / "master.parquet").exists())


if __name__ == "__main__":
    unittest.main()

