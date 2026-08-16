from __future__ import annotations

import re
from datetime import UTC, datetime
from hashlib import sha256
from typing import Any

from review_builder.config import ReviewBuilderConfig
from review_builder.models import NormalizedReview, ProductLink, RawReview
from review_builder.processors.product_linker import ProductLinker
from shared.utils.time import utc_now_iso


class ReviewProcessor:
    def __init__(
        self,
        config: ReviewBuilderConfig,
        by_product_id: dict[str, ProductLink],
        by_source_product_id: dict[str, ProductLink],
        by_source_url: dict[str, ProductLink],
    ) -> None:
        self.config = config
        self.by_product_id = by_product_id
        self.by_source_product_id = by_source_product_id
        self.by_source_url = by_source_url

    def normalize(self, review: RawReview) -> NormalizedReview:
        product_id, source_url = self._link_product(review)
        review_text = self._normalize_text(review.review_text)
        source_review_id = self._normalize_text(review.source_review_id)
        duplicate_key = self.duplicate_key(review.source, source_review_id, review_text)
        return NormalizedReview(
            review_id=self._review_id(review.source, source_review_id, duplicate_key),
            product_id=product_id,
            source=review.source,
            source_url=source_url or review.source_url,
            source_review_id=source_review_id,
            review_title=self._normalize_text(review.review_title),
            review_text=review_text,
            rating=self._rating(review.rating),
            review_date=self._date(review.review_date),
            reviewer_name=self._normalize_text(review.reviewer_name),
            verified_purchase=self._bool(review.verified_purchase),
            helpful_votes=self._int(review.helpful_votes),
            language=(review.language or self.config.default_language).strip().lower(),
            collected_at=utc_now_iso(),
            status="normalized",
            duplicate_key=duplicate_key,
        )

    def _link_product(self, review: RawReview) -> tuple[str | None, str | None]:
        if review.product_id and review.product_id in self.by_product_id:
            link = self.by_product_id[review.product_id]
            return link.product_id, link.source_url
        if review.source_product_id:
            key = ProductLinker._key(review.source, review.source_product_id)
            if key in self.by_source_product_id:
                link = self.by_source_product_id[key]
                return link.product_id, link.source_url
        if review.source_url and review.source_url.strip().lower() in self.by_source_url:
            link = self.by_source_url[review.source_url.strip().lower()]
            return link.product_id, link.source_url
        return review.product_id, review.source_url

    @staticmethod
    def duplicate_key(source: str, source_review_id: str | None, review_text: str | None) -> str:
        normalized_text = re.sub(r"\s+", " ", review_text or "").strip().lower()
        readable = f"{source.lower()}::{(source_review_id or '').lower()}::{normalized_text}"
        return sha256(readable.encode("utf-8")).hexdigest()

    @staticmethod
    def _review_id(source: str, source_review_id: str | None, duplicate_key: str) -> str:
        stable = source_review_id or duplicate_key[:16]
        digest = sha256(f"{source}:{stable}:{duplicate_key}".encode("utf-8")).hexdigest()[:12].upper()
        return f"REV-{digest}"

    @staticmethod
    def _normalize_text(value: str | None) -> str | None:
        if value is None:
            return None
        text = str(value).replace("\r\n", "\n").replace("\r", "\n")
        text = re.sub(r"[ \t]+", " ", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        text = text.strip()
        return text or None

    @staticmethod
    def _rating(value: Any) -> float | None:
        if value in (None, ""):
            return None
        if isinstance(value, str):
            match = re.search(r"\d+(?:\.\d+)?", value)
            if not match:
                return None
            value = match.group(0)
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _date(value: Any) -> str | None:
        if value in (None, ""):
            return None
        if isinstance(value, (int, float)):
            return datetime.fromtimestamp(float(value), UTC).date().isoformat()
        text = str(value).strip()
        for fmt in ("%Y-%m-%d", "%m %d, %Y", "%m/%d/%Y", "%d-%m-%Y", "%B %d, %Y"):
            try:
                return datetime.strptime(text, fmt).date().isoformat()
            except ValueError:
                continue
        return text

    @staticmethod
    def _bool(value: Any) -> bool | None:
        if value in (None, ""):
            return None
        if isinstance(value, bool):
            return value
        text = str(value).strip().lower()
        if text in {"true", "1", "yes", "y", "verified"}:
            return True
        if text in {"false", "0", "no", "n"}:
            return False
        return None

    @staticmethod
    def _int(value: Any) -> int | None:
        if value in (None, ""):
            return None
        if isinstance(value, list) and len(value) >= 1:
            value = value[0]
        try:
            return int(float(str(value).replace(",", "").strip()))
        except ValueError:
            return None

