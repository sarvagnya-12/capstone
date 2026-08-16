from __future__ import annotations

from pathlib import Path

from catalog_builder.models import RawProduct
from shared.collectors import BaseCollector as SharedBaseCollector


class BaseCollector(SharedBaseCollector):
    service_name = "catalog_builder"
    auto_register = False
    source_name: str

    def collect(self, input_path: Path) -> list[RawProduct]:
        """Read source data and return RawProduct rows."""
        raise NotImplementedError
