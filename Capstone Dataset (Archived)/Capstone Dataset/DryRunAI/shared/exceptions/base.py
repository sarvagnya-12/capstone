from __future__ import annotations


class DryRunAIError(Exception):
    """Base exception for DryRunAI services."""


class ValidationError(DryRunAIError):
    """Raised when validation fails."""


class InvalidProductError(ValidationError):
    """Raised when product data is invalid."""


class ImageDownloadError(DryRunAIError):
    """Raised when an image cannot be downloaded or copied."""


class DuplicateAssetError(DryRunAIError):
    """Raised when an asset hash already exists."""

