from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class ProductMarketLink:
    product_id: str
    source: str | None
    source_product_id: str | None
    source_url: str | None


@dataclass(slots=True)
class RawMarketRecord:
    source: str
    source_product_id: str | None
    source_url: str | None
    product_id: str | None
    market_type: str | None
    price_type: str | None
    currency: str | None
    price: Any
    availability: str | None
    stock_status: str | None
    release_date: Any
    region: str | None
    last_updated: Any
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class MarketRecord:
    market_record_id: str
    product_id: str | None
    source: str
    source_url: str | None
    market_type: str
    price_type: str
    currency: str | None
    price: float | None
    availability: str
    stock_status: str | None
    release_date: str | None
    region: str | None
    last_updated: str | None
    status: str
    duplicate_key: str
    validation_errors: list[str] = field(default_factory=list)

    def row(self) -> dict[str, Any]:
        return {
            "market_record_id": self.market_record_id,
            "product_id": self.product_id,
            "source": self.source,
            "source_url": self.source_url,
            "market_type": self.market_type,
            "price_type": self.price_type,
            "currency": self.currency,
            "price": self.price,
            "availability": self.availability,
            "stock_status": self.stock_status,
            "release_date": self.release_date,
            "region": self.region,
            "last_updated": self.last_updated,
            "status": self.status,
        }
