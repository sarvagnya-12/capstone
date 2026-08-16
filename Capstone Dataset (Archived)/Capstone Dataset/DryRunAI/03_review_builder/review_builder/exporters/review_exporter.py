from __future__ import annotations

from pathlib import Path
from typing import Any

from review_builder.models import NormalizedReview
from shared.io import read_json, write_csv_rows, write_json
from shared.utils.paths import next_version_dir


class ReviewExporter:
    def __init__(self, reviews_schema_path: Path, versions_dir: Path, processed_dir: Path, quarantine_dir: Path, reports_dir: Path, metadata_dir: Path) -> None:
        self.columns = [column["name"] for column in read_json(reviews_schema_path)["columns"]]
        self.versions_dir = versions_dir
        self.processed_dir = processed_dir
        self.quarantine_dir = quarantine_dir
        self.reports_dir = reports_dir
        self.metadata_dir = metadata_dir

    def create_version_dirs(self) -> tuple[Path, Path, Path, Path, Path, int]:
        version_dir, version = next_version_dir(self.versions_dir, "reviews_v")
        processed_version_dir = self.processed_dir / f"reviews_v{version}"
        quarantine_version_dir = self.quarantine_dir / f"reviews_v{version}"
        reports_version_dir = self.reports_dir / f"reviews_v{version}"
        metadata_version_dir = self.metadata_dir / f"reviews_v{version}"
        for path in (processed_version_dir, quarantine_version_dir, reports_version_dir, metadata_version_dir):
            path.mkdir(parents=True, exist_ok=False)
        return version_dir, processed_version_dir, quarantine_version_dir, reports_version_dir, metadata_version_dir, version

    def write_reviews(self, path: Path, reviews: list[NormalizedReview]) -> None:
        write_csv_rows(path, [review.row() for review in reviews], self.columns)

    @staticmethod
    def write_json(path: Path, payload: dict[str, Any]) -> None:
        write_json(path, payload)

