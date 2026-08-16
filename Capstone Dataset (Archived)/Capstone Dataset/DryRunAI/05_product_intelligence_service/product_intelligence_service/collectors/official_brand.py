from __future__ import annotations

from product_intelligence_service.collectors.base import BaseIntelligenceCollector


class NikeCollector(BaseIntelligenceCollector):
    source_name = "nike"


class AdidasCollector(BaseIntelligenceCollector):
    source_name = "adidas"


class PumaCollector(BaseIntelligenceCollector):
    source_name = "puma"


class NewBalanceCollector(BaseIntelligenceCollector):
    source_name = "new_balance"


class AsicsCollector(BaseIntelligenceCollector):
    source_name = "asics"

