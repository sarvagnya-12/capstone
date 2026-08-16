from __future__ import annotations

from pathlib import Path

from market_service.collectors.common import as_text, first_value, read_rows
from market_service.models import RawMarketRecord
from shared.collectors import BaseCollector


class BaseMarketCollector(BaseCollector):
    service_name = "market_service"
    source_name: str
    market_type = "Retail"
    default_price_type = "Retail"

    FIELD_ALIASES = {
        "source": ("source", "retailer", "brand", "marketplace"),
        "source_product_id": ("source_product_id", "sku", "asin", "style_id", "product_sku"),
        "source_url": ("source_url", "product_url", "url", "listing_url"),
        "product_id": ("product_id", "dryrun_product_id"),
        "market_type": ("market_type",),
        "price_type": ("price_type", "price_kind"),
        "currency": ("currency",),
        "price": ("price", "amount", "retail_price", "msrp"),
        "availability": ("availability", "available"),
        "stock_status": ("stock_status", "stock", "inventory_status"),
        "release_date": ("release_date", "launch_date"),
        "region": ("region", "country", "market"),
        "last_updated": ("last_updated", "timestamp", "updated_at", "collected_at"),
    }

    def collect(self, input_path: Path) -> list[RawMarketRecord]:
        records: list[RawMarketRecord] = []
        for row in read_rows(input_path):
            row_source = as_text(first_value(row, self.FIELD_ALIASES["source"]))
            if row_source and self._slug(row_source) != self.source_name:
                continue
            records.append(self._record(row))
        return records

    def _record(self, row: dict) -> RawMarketRecord:
        return RawMarketRecord(
            source=self.source_name,
            source_product_id=as_text(first_value(row, self.FIELD_ALIASES["source_product_id"])),
            source_url=as_text(first_value(row, self.FIELD_ALIASES["source_url"])),
            product_id=as_text(first_value(row, self.FIELD_ALIASES["product_id"])),
            market_type=as_text(first_value(row, self.FIELD_ALIASES["market_type"])) or self.market_type,
            price_type=as_text(first_value(row, self.FIELD_ALIASES["price_type"])) or self.default_price_type,
            currency=as_text(first_value(row, self.FIELD_ALIASES["currency"])),
            price=first_value(row, self.FIELD_ALIASES["price"]),
            availability=as_text(first_value(row, self.FIELD_ALIASES["availability"])),
            stock_status=as_text(first_value(row, self.FIELD_ALIASES["stock_status"])),
            release_date=first_value(row, self.FIELD_ALIASES["release_date"]),
            region=as_text(first_value(row, self.FIELD_ALIASES["region"])),
            last_updated=first_value(row, self.FIELD_ALIASES["last_updated"]),
            metadata=dict(row),
        )

    @staticmethod
    def _slug(value: str) -> str:
        return value.strip().lower().replace(" ", "_").replace("-", "_")

