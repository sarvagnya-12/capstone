from __future__ import annotations

from shared.exceptions import ValidationError


def validate_required_columns(actual_columns: set[str], required_columns: set[str]) -> None:
    missing = sorted(required_columns - actual_columns)
    if missing:
        raise ValidationError(f"Missing required columns: {', '.join(missing)}")

