from __future__ import annotations

from product_intelligence_service.collectors.base import BaseIntelligenceCollector


class WikipediaCollector(BaseIntelligenceCollector):
    source_name = "wikipedia"


class WikidataCollector(BaseIntelligenceCollector):
    source_name = "wikidata"


class TrustedPublicBrandResourcesCollector(BaseIntelligenceCollector):
    source_name = "trusted_public_brand_resources"

