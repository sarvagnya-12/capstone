from __future__ import annotations

from pathlib import Path

from shared.exceptions import ValidationError


def validate_existing_file(path: Path) -> None:
    if not path.exists() or not path.is_file():
        raise ValidationError(f"File does not exist: {path}")
    if path.stat().st_size == 0:
        raise ValidationError(f"File is zero bytes: {path}")

