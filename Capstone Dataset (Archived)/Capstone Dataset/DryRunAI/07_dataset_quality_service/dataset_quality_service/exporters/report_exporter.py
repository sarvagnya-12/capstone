from __future__ import annotations

from pathlib import Path
from typing import Any

from shared.io import write_json
from shared.io.files import ensure_dir


class ReportExporter:
    def __init__(self, reports_dir: Path) -> None:
        self.reports_dir = reports_dir

    def prepare(self) -> None:
        ensure_dir(self.reports_dir)

    def write_reports(self, reports: dict[str, dict[str, Any]]) -> None:
        self.prepare()
        for name, payload in reports.items():
            write_json(self.reports_dir / f"{name}.json", payload)

