from __future__ import annotations

from market_service.collectors.base import BaseMarketCollector


class ZapposCollector(BaseMarketCollector):
    source_name = "zappos"
    market_type = "Retail"
    default_price_type = "Retail"


class FootLockerCollector(BaseMarketCollector):
    source_name = "foot_locker"
    market_type = "Retail"
    default_price_type = "Retail"


class JDSportsCollector(BaseMarketCollector):
    source_name = "jd_sports"
    market_type = "Retail"
    default_price_type = "Retail"

