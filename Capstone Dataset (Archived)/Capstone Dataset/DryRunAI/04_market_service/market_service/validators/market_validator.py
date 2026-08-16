from __future__ import annotations

from collections import Counter
from datetime import datetime
from urllib.parse import urlparse

from market_service.config import MarketServiceConfig
from market_service.models import MarketRecord


class MarketValidator:
    MARKET_TYPES = {"Official", "Retail", "Marketplace", "Resale", "Outlet", "Distributor"}
    PRICE_TYPES = {"MSRP", "Retail", "Discount", "Outlet", "Marketplace", "Resale"}
    AVAILABILITY = {"Available", "Limited", "OutOfStock", "Discontinued", "Unknown"}

    def __init__(self, config: MarketServiceConfig) -> None:
        self.config = config

    def validate(self, records: list[MarketRecord]) -> tuple[list[MarketRecord], list[MarketRecord], list[MarketRecord], dict]:
        accepted: list[MarketRecord] = []
        rejected: list[MarketRecord] = []
        duplicates: list[MarketRecord] = []
        seen: set[str] = set()
        errors_counter: Counter[str] = Counter()
        for record in records:
            errors = self._errors(record)
            if record.duplicate_key in seen:
                errors.append("duplicate_record")
            if errors:
                record.validation_errors = errors
                record.status = "duplicate" if "duplicate_record" in errors else "rejected"
                if record.status == "duplicate":
                    duplicates.append(record)
                else:
                    rejected.append(record)
                for error in errors:
                    errors_counter[error] += 1
                continue
            seen.add(record.duplicate_key)
            record.status = "accepted"
            accepted.append(record)
        report = {
            "records_checked": len(records),
            "records_accepted": len(accepted),
            "records_rejected": len(rejected),
            "duplicate_records": len(duplicates),
            "error_counts": dict(errors_counter),
            "rejected_records": [
                {
                    "market_record_id": item.market_record_id,
                    "product_id": item.product_id,
                    "source": item.source,
                    "errors": item.validation_errors,
                }
                for item in rejected
            ],
        }
        return accepted, rejected, duplicates, report

    def _errors(self, record: MarketRecord) -> list[str]:
        errors: list[str] = []
        if not record.product_id:
            errors.append("missing_product_id")
        if record.price is not None and record.price < 0:
            errors.append("negative_price")
        if record.currency is not None and record.currency not in self.config.supported_currencies:
            errors.append("invalid_currency")
        if record.release_date is not None and not self._valid_date(record.release_date):
            errors.append("invalid_release_date")
        if not record.last_updated:
            errors.append("missing_last_updated")
        elif not self._valid_datetime(record.last_updated):
            errors.append("invalid_last_updated")
        if record.source_url and not self._valid_url(record.source_url):
            errors.append("broken_source_url")
        if record.market_type not in self.MARKET_TYPES:
            errors.append("invalid_market_type")
        if record.price_type not in self.PRICE_TYPES:
            errors.append("invalid_price_type")
        if record.availability not in self.AVAILABILITY:
            errors.append("invalid_availability")
        return errors

    @staticmethod
    def _valid_url(value: str) -> bool:
        parsed = urlparse(value.strip())
        return parsed.scheme in {"http", "https"} and bool(parsed.netloc)

    @staticmethod
    def _valid_date(value: str) -> bool:
        try:
            datetime.strptime(value, "%Y-%m-%d")
            return True
        except ValueError:
            return False

    @staticmethod
    def _valid_datetime(value: str) -> bool:
        try:
            datetime.fromisoformat(value)
            return True
        except ValueError:
            return False
