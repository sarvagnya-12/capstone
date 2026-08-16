from __future__ import annotations

from collections import Counter
from typing import Any

from asset_manager.models import ImageMetadata


class AssetReportBuilder:
    def build(self, products_processed: int, references_found: int, metadata: list[ImageMetadata], execution_time: float) -> dict[str, Any]:
        status_counts = Counter(item.status for item in metadata)
        asset_summary = {
            "products_processed": products_processed,
            "image_references_found": references_found,
            "images_stored": status_counts.get("stored", 0),
            "images_rejected": status_counts.get("rejected", 0),
            "images_skipped": status_counts.get("skipped", 0),
            "duplicates_detected": status_counts.get("duplicate", 0),
            "execution_time_seconds": round(execution_time, 4),
        }
        validation_report = {
            "invalid_images": [self._item(item) for item in metadata if item.status == "rejected"],
        }
        download_report = {
            "downloaded": status_counts.get("stored", 0) + status_counts.get("duplicate", 0) + status_counts.get("rejected", 0),
            "skipped": status_counts.get("skipped", 0),
            "errors": [self._item(item) for item in metadata if item.status == "download_error"],
        }
        duplicate_report = {
            "duplicates_detected": status_counts.get("duplicate", 0),
            "items": [self._item(item) for item in metadata if item.status == "duplicate"],
        }
        return {
            "asset_summary": asset_summary,
            "validation_report": validation_report,
            "download_report": download_report,
            "duplicate_report": duplicate_report,
        }

    @staticmethod
    def _item(item: ImageMetadata) -> dict[str, Any]:
        return {
            "image_id": item.image_id,
            "product_id": item.product_id,
            "original_image_url": item.original_image_url,
            "status": item.status,
            "error": item.error,
        }

