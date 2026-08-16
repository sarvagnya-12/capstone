from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from review_builder.exporters import ReviewExporter


class ExporterTests(unittest.TestCase):
    def test_creates_version_dirs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            schema = root / "schema.json"
            schema.write_text(json.dumps({"columns": [{"name": "review_id"}]}), encoding="utf-8")
            exporter = ReviewExporter(
                schema,
                root / "versions",
                root / "processed",
                root / "quarantine",
                root / "reports",
                root / "metadata",
            )
            version_dir, processed_dir, quarantine_dir, reports_dir, metadata_dir, version = exporter.create_version_dirs()
            self.assertEqual(version, 1)
            self.assertTrue(version_dir.exists())
            self.assertTrue(processed_dir.exists())
            self.assertTrue(quarantine_dir.exists())
            self.assertTrue(reports_dir.exists())
            self.assertTrue(metadata_dir.exists())


if __name__ == "__main__":
    unittest.main()

