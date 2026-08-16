from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class ProductRecord:
    product_id: str
    source: str | None
    source_url: str | None
    row: dict[str, str]


@dataclass(slots=True)
class ImageReference:
    product_id: str
    source: str | None
    source_url: str | None
    original_image_url: str
    image_type: str
    original_filename: str | None = None


@dataclass(slots=True)
class ImageMetadata:
    image_id: str
    product_id: str
    source: str | None
    source_url: str | None
    original_image_url: str
    image_type: str
    width: int | None
    height: int | None
    aspect_ratio: float | None
    file_size: int | None
    sha256: str | None
    image_format: str | None
    download_timestamp: str
    status: str
    original_filename: str | None
    file_path: Path | None = None
    error: str | None = None

    def row(self) -> dict[str, str | int | float | None]:
        return {
            "image_id": self.image_id,
            "product_id": self.product_id,
            "source": self.source,
            "source_url": self.source_url,
            "original_image_url": self.original_image_url,
            "image_type": self.image_type,
            "width": self.width,
            "height": self.height,
            "aspect_ratio": self.aspect_ratio,
            "file_size": self.file_size,
            "sha256": self.sha256,
            "image_format": self.image_format,
            "download_timestamp": self.download_timestamp,
            "status": self.status,
            "original_filename": self.original_filename,
        }

