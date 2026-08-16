from __future__ import annotations

from pathlib import Path

from shared.io import read_json, write_json
from shared.utils.time import utc_now_iso


class ProjectManifestUpdater:
    def __init__(self, manifest_path: Path) -> None:
        self.manifest_path = manifest_path

    def update(self, master_product_count: int, version: int) -> None:
        if self.manifest_path.exists():
            manifest = read_json(self.manifest_path)
        else:
            manifest = {"completed_services": [], "last_updated_timestamp": None}
        completed = set(manifest.get("completed_services", []))
        completed.add("06_knowledge_integration_service")
        manifest["completed_services"] = sorted(completed)
        manifest["master_dataset_version"] = version
        manifest["master_product_count"] = master_product_count
        manifest["last_updated_timestamp"] = utc_now_iso()
        write_json(self.manifest_path, manifest)

