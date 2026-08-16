from __future__ import annotations

from market_service.collectors.base import BaseMarketCollector


class StockXCollector(BaseMarketCollector):
    source_name = "stockx"
    market_type = "Marketplace"
    default_price_type = "Resale"


class GoatCollector(BaseMarketCollector):
    source_name = "goat"
    market_type = "Marketplace"
    default_price_type = "Resale"

