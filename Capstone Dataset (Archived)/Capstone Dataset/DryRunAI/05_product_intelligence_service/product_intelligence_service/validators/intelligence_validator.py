from __future__ import annotations

from collections import Counter
from datetime import datetime
from urllib.parse import urlparse

from product_intelligence_service.config import ProductIntelligenceConfig
from product_intelligence_service.models import IntelligenceRecord


class IntelligenceValidator:
    def __init__(self, config: ProductIntelligenceConfig) -> None:
        self.config = config

    def validate(self, records: list[IntelligenceRecord]) -> tuple[list[IntelligenceRecord], list[IntelligenceRecord], list[IntelligenceRecord], dict]:
        accepted: list[IntelligenceRecord] = []
        rejected: list[IntelligenceRecord] = []
        duplicates: list[IntelligenceRecord] = []
        seen: set[str] = set()
        counter: Counter[str] = Counter()
        for record in records:
            errors = self._errors(record)
            if record.duplicate_key in seen:
                errors.append("duplicate_intelligence_record")
            if errors:
                record.validation_errors = errors
                record.status = "duplicate" if "duplicate_intelligence_record" in errors else "rejected"
                if record.status == "duplicate":
                    duplicates.append(record)
                else:
                    rejected.append(record)
                for error in errors:
                    counter[error] += 1
                continue
            seen.add(record.duplicate_key)
            record.status = "accepted"
            accepted.append(record)
        report = {
            "records_checked": len(records),
            "records_accepted": len(accepted),
            "records_rejected": len(rejected),
            "duplicate_records": len(duplicates),
            "error_counts": dict(counter),
            "rejected_records": [
                {
                    "intelligence_record_id": item.intelligence_record_id,
                    "product_id": item.product_id,
                    "brand": item.brand,
                    "source": item.source,
                    "errors": item.validation_errors,
                }
                for item in rejected
            ],
        }
        return accepted, rejected, duplicates, report

    def _errors(self, record: IntelligenceRecord) -> list[str]:
        errors: list[str] = []
        if not record.product_id:
            errors.append("missing_product_id")
        if not record.brand:
            errors.append("missing_brand")
        if record.source_url and not self._valid_url(record.source_url):
            errors.append("broken_source_url")
        if record.target_region and record.target_region not in self.config.supported_regions:
            errors.append("invalid_target_region")
        if record.launch_region and record.launch_region not in self.config.supported_regions:
            errors.append("invalid_launch_region")
        if record.country_of_origin and record.country_of_origin not in self.config.supported_countries:
            errors.append("invalid_country_name")
        if not record.collected_at:
            errors.append("missing_collected_at")
        elif not self._valid_datetime(record.collected_at):
            errors.append("invalid_collected_at")
        return errors

    @staticmethod
    def _valid_url(value: str) -> bool:
        parsed = urlparse(value.strip())
        return parsed.scheme in {"http", "https"} and bool(parsed.netloc)

    @staticmethod
    def _valid_datetime(value: str) -> bool:
        try:
            datetime.fromisoformat(value)
            return True
        except ValueError:
            return False

