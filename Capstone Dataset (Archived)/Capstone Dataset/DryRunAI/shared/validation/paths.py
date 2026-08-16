from __future__ import annotations

from pathlib import Path

from shared.exceptions import ValidationError


def validate_directory(path: Path) -> None:
    if not path.exists() or not path.is_dir():
        raise ValidationError(f"Directory does not exist: {path}")

