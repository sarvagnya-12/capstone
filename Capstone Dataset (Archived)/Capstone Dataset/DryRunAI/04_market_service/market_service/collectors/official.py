from __future__ import annotations

from market_service.collectors.base import BaseMarketCollector


class NikeCollector(BaseMarketCollector):
    source_name = "nike"
    market_type = "Official"
    default_price_type = "MSRP"


class AdidasCollector(BaseMarketCollector):
    source_name = "adidas"
    market_type = "Official"
    default_price_type = "MSRP"


class PumaCollector(BaseMarketCollector):
    source_name = "puma"
    market_type = "Official"
    default_price_type = "MSRP"


class NewBalanceCollector(BaseMarketCollector):
    source_name = "new_balance"
    market_type = "Official"
    default_price_type = "MSRP"


class AsicsCollector(BaseMarketCollector):
    source_name = "asics"
    market_type = "Official"
    default_price_type = "MSRP"

