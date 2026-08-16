from __future__ import annotations

import shutil
from pathlib import Path

from asset_manager.config import AssetManagerConfig
from asset_manager.models import ImageMetadata, ImageReference
from asset_manager.validators import ImageAssetValidator
from shared.exceptions import DuplicateAssetError, ImageDownloadError, ValidationError
from shared.io import ensure_dir
from shared.utils.hashing import sha256_file
from shared.utils.time import utc_now_iso


class ImageProcessor:
    def __init__(self, config: AssetManagerConfig, validator: ImageAssetValidator) -> None:
        self.config = config
        self.validator = validator
        self._hashes: dict[str, str] = {}

    def process(self, reference: ImageReference, temp_path: Path, output_dir: Path, quarantine_dir: Path, index: int) -> ImageMetadata:
        timestamp = utc_now_iso()
        image_id = f"IMG-{index:06d}"
        try:
            width, height, image_format = self.validator.validate(temp_path)
            digest = sha256_file(temp_path)
            if digest in self._hashes:
                raise DuplicateAssetError(f"Duplicate image hash already stored as {self._hashes[digest]}")
            self._hashes[digest] = image_id
            file_size = temp_path.stat().st_size
            product_image_dir = ensure_dir(output_dir / reference.product_id / "images")
            extension = self.config.image_format_extensions.get(image_format, temp_path.suffix or ".bin")
            output_path = product_image_dir / f"{image_id}{extension}"
            shutil.move(str(temp_path), output_path)
            return ImageMetadata(
                image_id=image_id,
                product_id=reference.product_id,
                source=reference.source,
                source_url=reference.source_url,
                original_image_url=reference.original_image_url,
                image_type=reference.image_type,
                width=width,
                height=height,
                aspect_ratio=round(width / height, 6),
                file_size=file_size,
                sha256=digest,
                image_format=image_format,
                download_timestamp=timestamp,
                status="stored",
                original_filename=reference.original_filename,
                file_path=output_path,
            )
        except (DuplicateAssetError, ValidationError) as exc:
            rejected_path = self._quarantine(temp_path, quarantine_dir, image_id)
            return ImageMetadata(
                image_id=image_id,
                product_id=reference.product_id,
                source=reference.source,
                source_url=reference.source_url,
                original_image_url=reference.original_image_url,
                image_type=reference.image_type,
                width=None,
                height=None,
                aspect_ratio=None,
                file_size=rejected_path.stat().st_size if rejected_path.exists() else None,
                sha256=sha256_file(rejected_path) if rejected_path.exists() and rejected_path.stat().st_size > 0 else None,
                image_format=None,
                download_timestamp=timestamp,
                status="duplicate" if isinstance(exc, DuplicateAssetError) else "rejected",
                original_filename=reference.original_filename,
                file_path=rejected_path,
                error=str(exc),
            )
        except ImageDownloadError:
            raise

    @staticmethod
    def _quarantine(temp_path: Path, quarantine_dir: Path, image_id: str) -> Path:
        ensure_dir(quarantine_dir)
        target = quarantine_dir / f"{image_id}{temp_path.suffix or '.bin'}"
        if temp_path.exists():
            shutil.move(str(temp_path), target)
        return target
