from __future__ import annotations

import re
from datetime import UTC, datetime
from hashlib import sha256
from typing import Any

from market_service.config import MarketServiceConfig
from market_service.models import MarketRecord, ProductMarketLink, RawMarketRecord
from market_service.processors.product_linker import MarketProductLinker


class MarketProcessor:
    def __init__(
        self,
        config: MarketServiceConfig,
        by_product_id: dict[str, ProductMarketLink],
        by_source_product_id: dict[str, ProductMarketLink],
        by_source_url: dict[str, ProductMarketLink],
    ) -> None:
        self.config = config
        self.by_product_id = by_product_id
        self.by_source_product_id = by_source_product_id
        self.by_source_url = by_source_url

    def normalize(self, raw: RawMarketRecord) -> MarketRecord:
        product_id, source_url = self._link_product(raw)
        last_updated = self._datetime(raw.last_updated)
        market_type = self._canonical(raw.market_type, self._market_types(), self.config.default_market_type)
        price_type = self._canonical(raw.price_type, self._price_types(), self.config.default_price_type)
        availability = self._canonical(raw.availability, self._availability(), self.config.default_availability)
        currency = raw.currency.strip().upper() if raw.currency else None
        region = self._region(raw.region)
        price = self._price(raw.price)
        release_date = self._date(raw.release_date)
        duplicate_key = self.duplicate_key(product_id, raw.source, price_type, last_updated)
        return MarketRecord(
            market_record_id=self._record_id(duplicate_key),
            product_id=product_id,
            source=raw.source,
            source_url=raw.source_url or source_url,
            market_type=market_type,
            price_type=price_type,
            currency=currency,
            price=price,
            availability=availability,
            stock_status=self._text(raw.stock_status),
            release_date=release_date,
            region=region,
            last_updated=last_updated,
            status="normalized",
            duplicate_key=duplicate_key,
        )

    def _link_product(self, raw: RawMarketRecord) -> tuple[str | None, str | None]:
        if raw.product_id and raw.product_id in self.by_product_id:
            link = self.by_product_id[raw.product_id]
            return link.product_id, link.source_url
        if raw.source_product_id:
            key = MarketProductLinker.key(raw.source, raw.source_product_id)
            if key in self.by_source_product_id:
                link = self.by_source_product_id[key]
                return link.product_id, link.source_url
        if raw.source_url and raw.source_url.strip().lower() in self.by_source_url:
            link = self.by_source_url[raw.source_url.strip().lower()]
            return link.product_id, link.source_url
        return raw.product_id, raw.source_url

    @staticmethod
    def duplicate_key(product_id: str | None, source: str, price_type: str, last_updated: str | None) -> str:
        return sha256(f"{product_id or ''}::{source.lower()}::{price_type}::{last_updated or ''}".encode("utf-8")).hexdigest()

    @staticmethod
    def _record_id(duplicate_key: str) -> str:
        return f"MKT-{duplicate_key[:12].upper()}"

    @staticmethod
    def _text(value: str | None) -> str | None:
        if value is None:
            return None
        text = re.sub(r"\s+", " ", str(value)).strip()
        return text or None

    @staticmethod
    def _price(value: Any) -> float | None:
        if value in (None, ""):
            return None
        try:
            return float(str(value).replace("$", "").replace(",", "").strip())
        except ValueError:
            return None

    @staticmethod
    def _date(value: Any) -> str | None:
        if value in (None, ""):
            return None
        text = str(value).strip()
        for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%d-%m-%Y", "%B %d, %Y"):
            try:
                return datetime.strptime(text, fmt).date().isoformat()
            except ValueError:
                continue
        return text

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

    def _region(self, value: str | None) -> str | None:
        if not value:
            return self.config.default_region
        normalized = value.strip()
        for region in self.config.supported_regions:
            if normalized.lower() == region.lower():
                return region
        return normalized

    @staticmethod
    def _canonical(value: str | None, allowed: set[str], default: str) -> str:
        if not value:
            return default
        normalized = value.strip().replace(" ", "")
        for option in allowed:
            if normalized.lower() == option.lower().replace(" ", ""):
                return option
        return value.strip()

    @staticmethod
    def _market_types() -> set[str]:
        return {"Official", "Retail", "Marketplace", "Resale", "Outlet", "Distributor"}

    @staticmethod
    def _price_types() -> set[str]:
        return {"MSRP", "Retail", "Discount", "Outlet", "Marketplace", "Resale"}

    @staticmethod
    def _availability() -> set[str]:
        return {"Available", "Limited", "OutOfStock", "Discontinued", "Unknown"}
