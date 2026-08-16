from __future__ import annotations

from pathlib import Path

from shared.validation import validate_image_file


class ImageAssetValidator:
    def __init__(self, supported_formats: set[str]) -> None:
        self.supported_formats = supported_formats

    def validate(self, path: Path) -> tuple[int, int, str]:
        return validate_image_file(path, self.supported_formats)

