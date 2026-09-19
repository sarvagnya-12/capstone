from __future__ import annotations

from market_service.collectors.base import BaseMarketCollector


class AmazonCollector(BaseMarketCollector):
    """Market collector for Amazon marketplace listings.

    Follows the same one-class-per-source pattern as official.py / retail.py /
    marketplace.py: all parsing, aliasing and filtering already lives in
    BaseMarketCollector.collect(), so a source only needs to declare its name
    and how its prices should be typed.

    Priced rows are produced upstream by
    _ingestion_tools/prepare_amazon_catalog_rows.py from Amazon Reviews 2023
    product metadata. Price type is Retail (an Amazon listing price), not Resale
    as with StockX/GOAT.
    """

    source_name = "amazon"
    market_type = "Marketplace"
    default_price_type = "Retail"
