from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class DatasetSpec:
    name: str
    path: Path | None
    schema_path: Path
    id_field: str
    requires_product_id: bool = True


@dataclass(slots=True)
class DatasetValidationResult:
    name: str
    rows: list[dict[str, Any]]
    path: str | None
    row_count: int
    missing_path: bool = False
    missing_required_fields: dict[str, int] = field(default_factory=dict)
    duplicate_ids: list[str] = field(default_factory=list)
    schema_violations: list[str] = field(default_factory=list)
    broken_product_ids: list[str] = field(default_factory=list)
    missing_values: dict[str, int] = field(default_factory=dict)

    @property
    def issue_count(self) -> int:
        return (
            int(self.missing_path)
            + sum(self.missing_required_fields.values())
            + len(self.duplicate_ids)
            + len(self.schema_violations)
            + len(self.broken_product_ids)
        )

