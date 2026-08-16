from __future__ import annotations

from pathlib import Path

from dataset_quality_service.models import DatasetSpec
from shared.collectors import BaseCollector
from shared.io import read_csv_rows


class DatasetReader(BaseCollector):
    service_name = "dataset_quality_service"
    source_name = "dataset_outputs"
    auto_register = False

    def collect(self, input_path: Path) -> list[dict[str, str]]:
        return read_csv_rows(input_path)

    def read(self, spec: DatasetSpec) -> list[dict[str, str]]:
        if spec.path is None or not spec.path.exists():
            return []
        return self.collect(spec.path)

