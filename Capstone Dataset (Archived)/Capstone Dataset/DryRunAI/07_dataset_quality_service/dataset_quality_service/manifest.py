from __future__ import annotations

from pathlib import Path

from shared.io import read_json, write_json
from shared.utils.time import utc_now_iso


class ProjectManifestUpdater:
    def __init__(self, manifest_path: Path) -> None:
        self.manifest_path = manifest_path

    def update(self, health_score: int) -> None:
        if self.manifest_path.exists():
            manifest = read_json(self.manifest_path)
        else:
            manifest = {"completed_services": [], "last_updated_timestamp": None}
        completed = set(manifest.get("completed_services", []))
        completed.add("07_dataset_quality_service")
        manifest["completed_services"] = sorted(completed)
        manifest["validation_timestamp"] = utc_now_iso()
        manifest["dataset_health_score"] = health_score
        manifest["last_updated_timestamp"] = utc_now_iso()
        write_json(self.manifest_path, manifest)

