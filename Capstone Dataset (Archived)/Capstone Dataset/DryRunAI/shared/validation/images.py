from __future__ import annotations

from pathlib import Path

from PIL import Image, UnidentifiedImageError

from shared.exceptions import ValidationError
from shared.validation.files import validate_existing_file


def validate_image_file(path: Path, supported_formats: set[str]) -> tuple[int, int, str]:
    validate_existing_file(path)
    try:
        with Image.open(path) as image:
            image.verify()
        with Image.open(path) as image:
            image_format = (image.format or "").upper()
            if image_format not in supported_formats:
                raise ValidationError(f"Unsupported image format '{image_format}' for {path}")
            width, height = image.size
    except UnidentifiedImageError as exc:
        raise ValidationError(f"Unreadable image: {path}") from exc
    if width <= 0 or height <= 0:
        raise ValidationError(f"Image has invalid dimensions: {path}")
    return width, height, image_format

