from __future__ import annotations

import re
from datetime import UTC, datetime
from hashlib import sha256
from typing import Any

from product_intelligence_service.config import ProductIntelligenceConfig
from product_intelligence_service.models import IntelligenceRecord, ProductLink, RawIntelligenceRecord


class IntelligenceProcessor:
    def __init__(self, config: ProductIntelligenceConfig, products: dict[str, ProductLink]) -> None:
        self.config = config
        self.products = products

    def normalize(self, raw: RawIntelligenceRecord) -> IntelligenceRecord:
        product = self.products.get(raw.product_id or "")
        brand = self._text(raw.brand) or (product.brand if product else None)
        campaign_name = self._text(raw.campaign_name)
        source_url = self._text(raw.source_url)
        collected_at = self._datetime(raw.collected_at)
        duplicate_key = self.duplicate_key(raw.product_id, brand, campaign_name, raw.source)
        return IntelligenceRecord(
            intelligence_record_id=self._record_id(duplicate_key),
            product_id=raw.product_id,
            brand=brand,
            source=raw.source,
            source_url=source_url,
            brand_description=self._text(raw.brand_description),
            brand_mission=self._text(raw.brand_mission),
            brand_values=self._text(raw.brand_values),
            campaign_name=campaign_name,
            campaign_description=self._text(raw.campaign_description),
            campaign_theme=self._text(raw.campaign_theme),
            marketing_strategy=self._title(raw.marketing_strategy),
            target_age_min=self._int(raw.target_age_min),
            target_age_max=self._int(raw.target_age_max),
            target_gender=self._title(raw.target_gender),
            target_income_segment=self._text(raw.target_income_segment),
            target_region=self._region(raw.target_region),
            target_lifestyle=self._title(raw.target_lifestyle),
            brand_positioning=self._text(raw.brand_positioning),
            brand_ambassador=self._text(raw.brand_ambassador),
            tagline=self._text(raw.tagline),
            product_family=self._title(raw.product_family),
            parent_company=self._text(raw.parent_company),
            country_of_origin=self._country(raw.country_of_origin),
            launch_region=self._region(raw.launch_region),
            distribution_channels=self._text(raw.distribution_channels),
            sustainability_notes=self._text(raw.sustainability_notes),
            competitor_products=self._text(raw.competitor_products),
            competitor_brands=self._text(raw.competitor_brands),
            collected_at=collected_at,
            status="normalized",
            duplicate_key=duplicate_key,
        )

    @staticmethod
    def duplicate_key(product_id: str | None, brand: str | None, campaign_name: str | None, source: str) -> str:
        text = f"{product_id or ''}::{brand or ''}::{campaign_name or ''}::{source}".lower()
        return sha256(text.encode("utf-8")).hexdigest()

    @staticmethod
    def _record_id(duplicate_key: str) -> str:
        return f"INT-{duplicate_key[:12].upper()}"

    @staticmethod
    def _text(value: str | None) -> str | None:
        if value is None:
            return None
        text = re.sub(r"\s+", " ", str(value)).strip()
        return text or None

    @staticmethod
    def _title(value: str | None) -> str | None:
        text = IntelligenceProcessor._text(value)
        return text.title() if text else None

    def _region(self, value: str | None) -> str | None:
        text = self._text(value)
        if not text:
            return None
        for region in self.config.supported_regions:
            if text.lower() == region.lower():
                return region
        return text

    def _country(self, value: str | None) -> str | None:
        text = self._text(value)
        if not text:
            return None
        for country in self.config.supported_countries:
            if text.lower() == country.lower():
                return country
        return text

    @staticmethod
    def _int(value: Any) -> int | None:
        if value in (None, ""):
            return None
        try:
            return int(float(str(value).strip()))
        except ValueError:
            return None

    @staticmethod
    def _datetime(value: Any) -> str | None:
        if value in (None, ""):
            return None
        if isinstance(value, (int, float)):
            return datetime.fromtimestamp(float(value), UTC).isoformat()
        text = str(value).strip()
        for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
            try:
                parsed = datetime.strptime(text, fmt)
                if parsed.tzinfo is None:
                    parsed = parsed.replace(tzinfo=UTC)
                return parsed.isoformat()
            except ValueError:
                continue
        return text

