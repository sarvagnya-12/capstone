from __future__ import annotations

from pathlib import Path

from shared.logging import configure_service_logging


def configure_logging(logs_dir: Path) -> Path:
    return configure_service_logging(
        service_name="catalog_builder",
        logs_dir=logs_dir,
        max_bytes=1024 * 1024,
        backup_count=5,
        console=True,
    )
