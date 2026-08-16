from __future__ import annotations

import unittest

from asset_manager.reports import AssetReportBuilder


class AssetReportBuilderTests(unittest.TestCase):
    def test_empty_report(self) -> None:
        reports = AssetReportBuilder().build(products_processed=2, references_found=0, metadata=[], execution_time=0.1)
        self.assertEqual(reports["asset_summary"]["products_processed"], 2)
        self.assertEqual(reports["asset_summary"]["images_stored"], 0)
        self.assertEqual(reports["duplicate_report"]["duplicates_detected"], 0)


if __name__ == "__main__":
    unittest.main()

