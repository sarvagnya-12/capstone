from __future__ import annotations

from pathlib import Path

from knowledge_integration_service.models import DatasetBundle
from shared.collectors import BaseCollector
from shared.io import read_csv_rows


class DatasetCollector(BaseCollector):
    service_name = "knowledge_integration_service"
    source_name = "service_outputs"
    auto_register = False

    def collect(self, input_path: Path) -> list:
        raise NotImplementedError("Use collect_bundle for Knowledge Integration datasets.")

    def collect_bundle(
        self,
        products_csv_path: Path,
        image_metadata_path: Path | None,
        reviews_csv_path: Path | None,
        market_csv_path: Path | None,
        product_intelligence_csv_path: Path | None,
    ) -> DatasetBundle:
        return DatasetBundle(
            products=read_csv_rows(products_csv_path),
            images=self._optional_rows(image_metadata_path),
            reviews=self._optional_rows(reviews_csv_path),
            market=self._optional_rows(market_csv_path),
            product_intelligence=self._optional_rows(product_intelligence_csv_path),
            dataset_paths={
                "products": str(products_csv_path),
                "images": str(image_metadata_path) if image_metadata_path else None,
                "reviews": str(reviews_csv_path) if reviews_csv_path else None,
                "market": str(market_csv_path) if market_csv_path else None,
                "product_intelligence": str(product_intelligence_csv_path) if product_intelligence_csv_path else None,
            },
        )

    @staticmethod
    def _optional_rows(path: Path | None) -> list[dict[str, str]]:
        if path is None or not path.exists():
            return []
        return read_csv_rows(path)

