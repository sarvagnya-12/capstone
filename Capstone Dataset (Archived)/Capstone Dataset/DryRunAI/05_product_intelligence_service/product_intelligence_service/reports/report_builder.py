from __future__ import annotations

from collections import Counter
from typing import Any

from product_intelligence_service.models import IntelligenceRecord


class IntelligenceReportBuilder:
    def build(
        self,
        products_processed: int,
        accepted: list[IntelligenceRecord],
        rejected: list[IntelligenceRecord],
        duplicates: list[IntelligenceRecord],
        validation_report: dict[str, Any],
        execution_time: float,
    ) -> dict[str, dict[str, Any]]:
        summary = {
            "products_processed": products_processed,
            "records_collected": len(accepted) + len(rejected) + len(duplicates),
            "records_exported": len(accepted),
            "campaigns_collected": len([record for record in accepted if record.campaign_name]),
            "brands_covered": sorted({record.brand for record in accepted if record.brand}),
            "ambassadors_collected": len([record for record in accepted if record.brand_ambassador]),
            "marketing_strategies": dict(Counter(record.marketing_strategy for record in accepted if record.marketing_strategy)),
            "target_audiences": {
                "gender": dict(Counter(record.target_gender for record in accepted if record.target_gender)),
                "lifestyle": dict(Counter(record.target_lifestyle for record in accepted if record.target_lifestyle)),
                "region": dict(Counter(record.target_region for record in accepted if record.target_region)),
            },
            "countries_covered": sorted({record.country_of_origin for record in accepted if record.country_of_origin}),
            "sources_used": dict(Counter(record.source for record in accepted)),
            "duplicate_records": len(duplicates),
            "rejected_records": len(rejected),
            "execution_time_seconds": round(execution_time, 4),
        }
        duplicate_report = {
            "duplicate_records": len(duplicates),
            "items": [
                {
                    "intelligence_record_id": record.intelligence_record_id,
                    "product_id": record.product_id,
                    "brand": record.brand,
                    "campaign_name": record.campaign_name,
                    "source": record.source,
                }
                for record in duplicates
            ],
        }
        statistics = {
            "brand_counts": dict(Counter(record.brand for record in accepted if record.brand)),
            "source_counts": summary["sources_used"],
            "campaign_theme_counts": dict(Counter(record.campaign_theme for record in accepted if record.campaign_theme)),
            "marketing_strategy_counts": summary["marketing_strategies"],
            "country_counts": dict(Counter(record.country_of_origin for record in accepted if record.country_of_origin)),
            "status_counts": dict(Counter(record.status for record in accepted + rejected + duplicates)),
            "execution_time_seconds": summary["execution_time_seconds"],
        }
        return {
            "product_intelligence_summary": summary,
            "validation_report": validation_report,
            "duplicate_report": duplicate_report,
            "statistics": statistics,
        }

