from __future__ import annotations

from pathlib import Path
from typing import Any

from product_intelligence_service.models import IntelligenceRecord
from shared.io import read_json, write_csv_rows, write_json
from shared.utils.paths import next_version_dir


class IntelligenceExporter:
    def __init__(
        self,
        schema_path: Path,
        versions_dir: Path,
        processed_dir: Path,
        quarantine_dir: Path,
        reports_dir: Path,
        metadata_dir: Path,
    ) -> None:
        self.columns = [column["name"] for column in read_json(schema_path)["columns"]]
        self.versions_dir = versions_dir
        self.processed_dir = processed_dir
        self.quarantine_dir = quarantine_dir
        self.reports_dir = reports_dir
        self.metadata_dir = metadata_dir

    def create_version_dirs(self) -> tuple[Path, Path, Path, Path, Path, int]:
        version_dir, version = next_version_dir(self.versions_dir, "product_intelligence_v")
        processed_version_dir = self.processed_dir / f"product_intelligence_v{version}"
        quarantine_version_dir = self.quarantine_dir / f"product_intelligence_v{version}"
        reports_version_dir = self.reports_dir / f"product_intelligence_v{version}"
        metadata_version_dir = self.metadata_dir / f"product_intelligence_v{version}"
        for path in (processed_version_dir, quarantine_version_dir, reports_version_dir, metadata_version_dir):
            path.mkdir(parents=True, exist_ok=False)
        return version_dir, processed_version_dir, quarantine_version_dir, reports_version_dir, metadata_version_dir, version

    def write_records(self, path: Path, records: list[IntelligenceRecord]) -> None:
        write_csv_rows(path, [record.row() for record in records], self.columns)

    @staticmethod
    def write_json(path: Path, payload: dict[str, Any]) -> None:
        write_json(path, payload)

