from __future__ import annotations

from pathlib import Path

from product_intelligence_service.collectors.common import as_text, first_value, read_rows
from product_intelligence_service.models import RawIntelligenceRecord
from shared.collectors import BaseCollector


class BaseIntelligenceCollector(BaseCollector):
    service_name = "product_intelligence_service"
    source_name: str

    FIELD_ALIASES = {
        "source": ("source", "collector", "publisher"),
        "product_id": ("product_id", "dryrun_product_id"),
        "brand": ("brand", "brand_name"),
        "source_url": ("source_url", "url", "page_url"),
        "brand_description": ("brand_description", "description"),
        "brand_mission": ("brand_mission", "mission"),
        "brand_values": ("brand_values", "values"),
        "campaign_name": ("campaign_name",),
        "campaign_description": ("campaign_description",),
        "campaign_theme": ("campaign_theme",),
        "marketing_strategy": ("marketing_strategy", "strategy"),
        "target_age_min": ("target_age_min",),
        "target_age_max": ("target_age_max",),
        "target_gender": ("target_gender", "gender"),
        "target_income_segment": ("target_income_segment", "income_segment"),
        "target_region": ("target_region",),
        "target_lifestyle": ("target_lifestyle", "lifestyle"),
        "brand_positioning": ("brand_positioning", "positioning"),
        "brand_ambassador": ("brand_ambassador", "ambassador"),
        "tagline": ("tagline",),
        "product_family": ("product_family", "family"),
        "parent_company": ("parent_company",),
        "country_of_origin": ("country_of_origin", "country"),
        "launch_region": ("launch_region",),
        "distribution_channels": ("distribution_channels", "channels"),
        "sustainability_notes": ("sustainability_notes", "sustainability"),
        "competitor_products": ("competitor_products",),
        "competitor_brands": ("competitor_brands",),
        "collected_at": ("collected_at", "last_updated", "timestamp"),
    }

    def collect(self, input_path: Path) -> list[RawIntelligenceRecord]:
        records: list[RawIntelligenceRecord] = []
        for row in read_rows(input_path):
            row_source = as_text(first_value(row, self.FIELD_ALIASES["source"]))
            if row_source and self._slug(row_source) != self.source_name:
                continue
            records.append(self._record(row))
        return records

    def _record(self, row: dict) -> RawIntelligenceRecord:
        return RawIntelligenceRecord(
            source=self.source_name,
            product_id=as_text(first_value(row, self.FIELD_ALIASES["product_id"])),
            brand=as_text(first_value(row, self.FIELD_ALIASES["brand"])),
            source_url=as_text(first_value(row, self.FIELD_ALIASES["source_url"])),
            brand_description=as_text(first_value(row, self.FIELD_ALIASES["brand_description"])),
            brand_mission=as_text(first_value(row, self.FIELD_ALIASES["brand_mission"])),
            brand_values=as_text(first_value(row, self.FIELD_ALIASES["brand_values"])),
            campaign_name=as_text(first_value(row, self.FIELD_ALIASES["campaign_name"])),
            campaign_description=as_text(first_value(row, self.FIELD_ALIASES["campaign_description"])),
            campaign_theme=as_text(first_value(row, self.FIELD_ALIASES["campaign_theme"])),
            marketing_strategy=as_text(first_value(row, self.FIELD_ALIASES["marketing_strategy"])),
            target_age_min=first_value(row, self.FIELD_ALIASES["target_age_min"]),
            target_age_max=first_value(row, self.FIELD_ALIASES["target_age_max"]),
            target_gender=as_text(first_value(row, self.FIELD_ALIASES["target_gender"])),
            target_income_segment=as_text(first_value(row, self.FIELD_ALIASES["target_income_segment"])),
            target_region=as_text(first_value(row, self.FIELD_ALIASES["target_region"])),
            target_lifestyle=as_text(first_value(row, self.FIELD_ALIASES["target_lifestyle"])),
            brand_positioning=as_text(first_value(row, self.FIELD_ALIASES["brand_positioning"])),
            brand_ambassador=as_text(first_value(row, self.FIELD_ALIASES["brand_ambassador"])),
            tagline=as_text(first_value(row, self.FIELD_ALIASES["tagline"])),
            product_family=as_text(first_value(row, self.FIELD_ALIASES["product_family"])),
            parent_company=as_text(first_value(row, self.FIELD_ALIASES["parent_company"])),
            country_of_origin=as_text(first_value(row, self.FIELD_ALIASES["country_of_origin"])),
            launch_region=as_text(first_value(row, self.FIELD_ALIASES["launch_region"])),
            distribution_channels=as_text(first_value(row, self.FIELD_ALIASES["distribution_channels"])),
            sustainability_notes=as_text(first_value(row, self.FIELD_ALIASES["sustainability_notes"])),
            competitor_products=as_text(first_value(row, self.FIELD_ALIASES["competitor_products"])),
            competitor_brands=as_text(first_value(row, self.FIELD_ALIASES["competitor_brands"])),
            collected_at=first_value(row, self.FIELD_ALIASES["collected_at"]),
            metadata=dict(row),
        )

    @staticmethod
    def _slug(value: str) -> str:
        return value.strip().lower().replace(" ", "_").replace("-", "_")

