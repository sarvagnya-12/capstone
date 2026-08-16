from __future__ import annotations

from collections import Counter
from statistics import mean
from typing import Any

from market_service.models import MarketRecord


class MarketReportBuilder:
    def build(
        self,
        products_processed: int,
        accepted: list[MarketRecord],
        rejected: list[MarketRecord],
        duplicates: list[MarketRecord],
        validation_report: dict[str, Any],
        execution_time: float,
    ) -> dict[str, dict[str, Any]]:
        summary = {
            "products_processed": products_processed,
            "records_collected": len(accepted) + len(rejected) + len(duplicates),
            "records_exported": len(accepted),
            "average_msrp": self._average(accepted, "MSRP"),
            "average_retail_price": self._average(accepted, "Retail"),
            "average_resale_price": self._average(accepted, "Resale"),
            "missing_prices": len([record for record in accepted if record.price is None]),
            "missing_release_dates": len([record for record in accepted if record.release_date is None]),
            "products_per_region": dict(Counter(record.region for record in accepted if record.region)),
            "products_per_source": dict(Counter(record.source for record in accepted if record.source)),
            "duplicate_records": len(duplicates),
            "rejected_records": len(rejected),
            "execution_time_seconds": round(execution_time, 4),
        }
        duplicate_report = {
            "duplicate_records": len(duplicates),
            "items": [
                {
                    "market_record_id": record.market_record_id,
                    "product_id": record.product_id,
                    "source": record.source,
                    "price_type": record.price_type,
                    "last_updated": record.last_updated,
                }
                for record in duplicates
            ],
        }
        statistics = {
            "market_type_counts": dict(Counter(record.market_type for record in accepted)),
            "price_type_counts": dict(Counter(record.price_type for record in accepted)),
            "availability_counts": dict(Counter(record.availability for record in accepted)),
            "currency_counts": dict(Counter(record.currency for record in accepted if record.currency)),
            "region_counts": summary["products_per_region"],
            "source_counts": summary["products_per_source"],
            "execution_time_seconds": summary["execution_time_seconds"],
        }
        return {
            "market_summary": summary,
            "statistics": statistics,
            "validation_report": validation_report,
            "duplicate_report": duplicate_report,
        }

    @staticmethod
    def _average(records: list[MarketRecord], price_type: str) -> float | None:
        values = [record.price for record in records if record.price_type == price_type and record.price is not None]
        return round(mean(values), 4) if values else None

