from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class ProductLink:
    product_id: str
    brand: str | None
    source_url: str | None


@dataclass(slots=True)
class RawIntelligenceRecord:
    source: str
    product_id: str | None
    brand: str | None
    source_url: str | None
    brand_description: str | None
    brand_mission: str | None
    brand_values: str | None
    campaign_name: str | None
    campaign_description: str | None
    campaign_theme: str | None
    marketing_strategy: str | None
    target_age_min: Any
    target_age_max: Any
    target_gender: str | None
    target_income_segment: str | None
    target_region: str | None
    target_lifestyle: str | None
    brand_positioning: str | None
    brand_ambassador: str | None
    tagline: str | None
    product_family: str | None
    parent_company: str | None
    country_of_origin: str | None
    launch_region: str | None
    distribution_channels: str | None
    sustainability_notes: str | None
    competitor_products: str | None
    competitor_brands: str | None
    collected_at: Any
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class IntelligenceRecord:
    intelligence_record_id: str
    product_id: str | None
    brand: str | None
    source: str
    source_url: str | None
    brand_description: str | None
    brand_mission: str | None
    brand_values: str | None
    campaign_name: str | None
    campaign_description: str | None
    campaign_theme: str | None
    marketing_strategy: str | None
    target_age_min: int | None
    target_age_max: int | None
    target_gender: str | None
    target_income_segment: str | None
    target_region: str | None
    target_lifestyle: str | None
    brand_positioning: str | None
    brand_ambassador: str | None
    tagline: str | None
    product_family: str | None
    parent_company: str | None
    country_of_origin: str | None
    launch_region: str | None
    distribution_channels: str | None
    sustainability_notes: str | None
    competitor_products: str | None
    competitor_brands: str | None
    collected_at: str | None
    status: str
    duplicate_key: str
    validation_errors: list[str] = field(default_factory=list)

    def row(self) -> dict[str, Any]:
        return {
            "intelligence_record_id": self.intelligence_record_id,
            "product_id": self.product_id,
            "brand": self.brand,
            "source": self.source,
            "source_url": self.source_url,
            "brand_description": self.brand_description,
            "brand_mission": self.brand_mission,
            "brand_values": self.brand_values,
            "campaign_name": self.campaign_name,
            "campaign_description": self.campaign_description,
            "campaign_theme": self.campaign_theme,
            "marketing_strategy": self.marketing_strategy,
            "target_age_min": self.target_age_min,
            "target_age_max": self.target_age_max,
            "target_gender": self.target_gender,
            "target_income_segment": self.target_income_segment,
            "target_region": self.target_region,
            "target_lifestyle": self.target_lifestyle,
            "brand_positioning": self.brand_positioning,
            "brand_ambassador": self.brand_ambassador,
            "tagline": self.tagline,
            "product_family": self.product_family,
            "parent_company": self.parent_company,
            "country_of_origin": self.country_of_origin,
            "launch_region": self.launch_region,
            "distribution_channels": self.distribution_channels,
            "sustainability_notes": self.sustainability_notes,
            "competitor_products": self.competitor_products,
            "competitor_brands": self.competitor_brands,
            "collected_at": self.collected_at,
            "status": self.status,
        }

